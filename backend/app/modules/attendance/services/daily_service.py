"""Layer 1 — population day-attendance aggregation.

Turns raw punches into one ``DailyAttendance`` row per student per LOCAL day:

- ``first_in``  = first punch of the local day (sign-in)
- ``last_out``  = last punch (sign-off); NULL when only one punch -> signoff MISSING
- ``day_status``= PRESENT if first_in <= class-start + grace, else LATE; ABSENT if no punch
- ``source``    = BIOMETRIC (had punches) | SYSTEM (absent sweep)

Idempotent: re-running rebuilds the row from punches. A ``MANUAL`` row (a human
edit) is never overwritten. See docs/biometric-attendance-design.md §3.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config.settings import get_settings
from app.modules.attendance.models.attendance_models import (
    DailyAttendance,
    RawPunchLog,
)
from app.modules.attendance.repositories import attendance_repository
from app.modules.attendance.time_utils import (
    campus_window_on,
    class_start_on,
    day_bounds,
    local_date_of,
)
from app.modules.auth.models.auth_models import Branch
from app.modules.events.services import event_service
from app.modules.lectures.models.lecture_models import Lecture
from app.modules.lectures.repositories import lecture_repository
from app.modules.student.models.student_models import (
    Student,
    StudentBatchMapping,
)

# An attendance_records row written by a human is never overwritten by the
# automated projection (decision 7).
_MANUAL_SOURCES = {"MANUAL", "MANUAL_OVERRIDE"}


async def branch_timezone(session: AsyncSession, branch_id: uuid.UUID) -> str:
    """The branch's IANA timezone, or the configured default if unset."""
    tz = (await session.execute(
        select(Branch.timezone).where(Branch.id == branch_id)
    )).scalar_one_or_none()
    return tz or get_settings().DEFAULT_TIMEZONE


async def _get_row(
    session: AsyncSession, student_id: uuid.UUID, day: date
) -> DailyAttendance | None:
    return (await session.execute(
        select(DailyAttendance).where(
            DailyAttendance.student_id == student_id,
            DailyAttendance.attendance_date == day,
            DailyAttendance.is_deleted == False,
        )
    )).scalar_one_or_none()


async def _punches_for_day(
    session: AsyncSession,
    student_id: uuid.UUID,
    branch_id: uuid.UUID,
    start: datetime,
    end: datetime,
) -> list[RawPunchLog]:
    return list((await session.execute(
        select(RawPunchLog)
        .where(
            RawPunchLog.student_id == student_id,
            RawPunchLog.branch_id == branch_id,
            RawPunchLog.punch_timestamp >= start,
            RawPunchLog.punch_timestamp < end,
            RawPunchLog.is_deleted == False,
        )
        .order_by(RawPunchLog.punch_timestamp)
    )).scalars().all())


def _classify(
    punches: list[RawPunchLog], day: date, tz_name: str
) -> tuple[datetime | None, datetime | None, str, str, str]:
    """-> (first_in, last_out, day_status, signoff, source)."""
    if not punches:
        return None, None, "ABSENT", "NA", "SYSTEM"

    grace = timedelta(minutes=get_settings().ATTENDANCE_GRACE_PERIOD_MINUTES)
    cutoff = class_start_on(day, tz_name) + grace

    first_in = punches[0].punch_timestamp
    if first_in.tzinfo is None:
        first_in = first_in.replace(tzinfo=timezone.utc)

    day_status = "PRESENT" if first_in <= cutoff else "LATE"

    if len(punches) > 1:
        last_out = punches[-1].punch_timestamp
        if last_out.tzinfo is None:
            last_out = last_out.replace(tzinfo=timezone.utc)
        signoff = "COMPLETE"
    else:
        last_out = None       # punched in, never out
        signoff = "MISSING"

    return first_in, last_out, day_status, signoff, "BIOMETRIC"


async def rebuild_daily(
    session: AsyncSession,
    *,
    student_id: uuid.UUID,
    branch_id: uuid.UUID,
    day: date,
    tz_name: str | None = None,
) -> DailyAttendance:
    """Recompute a student's day row from punches. Idempotent; MANUAL-safe."""
    tz_name = tz_name or await branch_timezone(session, branch_id)

    existing = await _get_row(session, student_id, day)
    if existing is not None and existing.source == "MANUAL":
        return existing  # human edit wins — never clobbered (decision 7)

    start, end = day_bounds(day, tz_name)
    punches = await _punches_for_day(session, student_id, branch_id, start, end)
    first_in, last_out, day_status, signoff, source = _classify(punches, day, tz_name)

    if existing is None:
        existing = DailyAttendance(
            student_id=student_id,
            branch_id=branch_id,
            attendance_date=day,
        )
        session.add(existing)

    existing.first_in = first_in
    existing.last_out = last_out
    existing.day_status = day_status
    existing.signoff = signoff
    existing.source = source
    existing.is_deleted = False
    await session.flush()
    return existing


async def _scheduled_batch_ids(
    session: AsyncSession, branch_id: uuid.UUID, start: datetime, end: datetime
) -> list[uuid.UUID]:
    """Batches with >=1 scheduled lecture in the local day. Defines which
    students have a 'working day' (decision 1)."""
    return list((await session.execute(
        select(Lecture.batch_id)
        .where(
            Lecture.branch_id == branch_id,
            Lecture.scheduled_start >= start,
            Lecture.scheduled_start < end,
            Lecture.is_deleted == False,
        )
        .distinct()
    )).scalars().all())


async def run_absent_sweep(
    session: AsyncSession,
    *,
    branch_id: uuid.UUID,
    day: date,
    tz_name: str | None = None,
    notify: bool = True,
) -> list[DailyAttendance]:
    """End-of-day sweep: mark ABSENT every active student who has a scheduled
    lecture today (decision 1) but no DailyAttendance row, and emit a
    STUDENT_ABSENT event per student for parent notification (decision 5).

    Idempotent — students already having a row (present, late, or a prior
    sweep) are skipped, so re-running never double-marks or re-notifies.
    """
    tz_name = tz_name or await branch_timezone(session, branch_id)
    start, end = day_bounds(day, tz_name)

    batch_ids = await _scheduled_batch_ids(session, branch_id, start, end)
    if not batch_ids:
        return []  # no lectures today -> not a working day for anyone

    # Active students (enrolled this session, decision 3) in those batches.
    student_rows = (await session.execute(
        select(
            Student.id,
            Student.first_name,
            Student.last_name,
            Student.parent_mobile,
        )
        .join(StudentBatchMapping, StudentBatchMapping.student_id == Student.id)
        .where(
            StudentBatchMapping.batch_id.in_(batch_ids),
            StudentBatchMapping.is_deleted == False,
            Student.branch_id == branch_id,
            Student.status == "active",
            Student.is_deleted == False,
        )
        .distinct()
    )).all()
    if not student_rows:
        return []

    student_ids = [r[0] for r in student_rows]
    already = set((await session.execute(
        select(DailyAttendance.student_id).where(
            DailyAttendance.student_id.in_(student_ids),
            DailyAttendance.attendance_date == day,
            DailyAttendance.is_deleted == False,
        )
    )).scalars().all())

    created: list[DailyAttendance] = []
    for sid, first_name, last_name, parent_mobile in student_rows:
        if sid in already:
            continue
        row = DailyAttendance(
            student_id=sid,
            branch_id=branch_id,
            attendance_date=day,
            first_in=None,
            last_out=None,
            day_status="ABSENT",
            signoff="NA",
            source="SYSTEM",
        )
        session.add(row)
        created.append(row)

        if notify:
            await event_service.emit_event(
                session,
                event_type="STUDENT_ABSENT",
                branch_id=branch_id,
                student_id=sid,
                metadata={
                    "attendance_date": day.isoformat(),
                    "student_name": f"{first_name} {last_name}".strip(),
                    "recipient": parent_mobile or "",
                },
            )

    await session.flush()
    return created


# ── Reports (Layer 1) ──────────────────────────────────────────────────────

# A "working day" present-credit counts both on-time and late as attended.
_PRESENT_STATUSES = {"PRESENT", "LATE"}


async def student_timeline(
    session: AsyncSession,
    *,
    student_id: uuid.UUID,
    branch_id: uuid.UUID,
    start: date,
    end: date,
) -> list[DailyAttendance]:
    """Reference A — one student's day rows over a date range (newest first)."""
    return list((await session.execute(
        select(DailyAttendance)
        .where(
            DailyAttendance.student_id == student_id,
            DailyAttendance.branch_id == branch_id,
            DailyAttendance.attendance_date >= start,
            DailyAttendance.attendance_date <= end,
            DailyAttendance.is_deleted == False,
        )
        .order_by(DailyAttendance.attendance_date.desc())
    )).scalars().all())


async def classroom_register(
    session: AsyncSession,
    *,
    branch_id: uuid.UUID,
    batch_id: uuid.UUID,
    day: date,
) -> list[dict]:
    """Reference B — P/A roster for a batch on one day."""
    students = (await session.execute(
        select(Student)
        .join(StudentBatchMapping, StudentBatchMapping.student_id == Student.id)
        .where(
            StudentBatchMapping.batch_id == batch_id,
            StudentBatchMapping.is_deleted == False,
            Student.is_deleted == False,
        )
        .order_by(Student.first_name, Student.last_name)
    )).scalars().all()

    rows = {
        r.student_id: r
        for r in (await session.execute(
            select(DailyAttendance).where(
                DailyAttendance.attendance_date == day,
                DailyAttendance.branch_id == branch_id,
                DailyAttendance.is_deleted == False,
            )
        )).scalars().all()
    }

    register = []
    for s in students:
        row = rows.get(s.id)
        present = row is not None and row.day_status in _PRESENT_STATUSES
        register.append({
            "student_id": s.id,
            "name": f"{s.first_name} {s.last_name}".strip(),
            "enrollment_number": s.enrollment_number,
            "parent_mobile": s.parent_mobile,
            "mark": "P" if present else "A",
            "day_status": row.day_status if row else "ABSENT",
            "first_in": row.first_in if row else None,
            "last_out": row.last_out if row else None,
            "signoff": row.signoff if row else "NA",
        })
    return register


async def _student_batch_ids(
    session: AsyncSession, student_id: uuid.UUID
) -> list[uuid.UUID]:
    return list((await session.execute(
        select(StudentBatchMapping.batch_id).where(
            StudentBatchMapping.student_id == student_id,
            StudentBatchMapping.is_deleted == False,
        )
    )).scalars().all())


async def monthly_summary(
    session: AsyncSession,
    *,
    student_id: uuid.UUID,
    branch_id: uuid.UUID,
    start: date,
    end: date,
    tz_name: str | None = None,
) -> dict:
    """Attendance % = present working days / working days (decision 1).

    A working day is any date in range with >=1 scheduled lecture for one of the
    student's batches.
    """
    tz_name = tz_name or await branch_timezone(session, branch_id)
    range_start, _ = day_bounds(start, tz_name)
    _, range_end = day_bounds(end, tz_name)

    batch_ids = await _student_batch_ids(session, student_id)
    working_days: set[date] = set()
    if batch_ids:
        lecture_starts = (await session.execute(
            select(Lecture.scheduled_start).where(
                Lecture.batch_id.in_(batch_ids),
                Lecture.branch_id == branch_id,
                Lecture.scheduled_start >= range_start,
                Lecture.scheduled_start < range_end,
                Lecture.is_deleted == False,
            )
        )).scalars().all()
        for ls in lecture_starts:
            d = local_date_of(ls, tz_name)
            if start <= d <= end:
                working_days.add(d)

    present_days = 0
    if working_days:
        present_dates = set((await session.execute(
            select(DailyAttendance.attendance_date).where(
                DailyAttendance.student_id == student_id,
                DailyAttendance.branch_id == branch_id,
                DailyAttendance.day_status.in_(_PRESENT_STATUSES),
                DailyAttendance.is_deleted == False,
            )
        )).scalars().all())
        present_days = len(working_days & present_dates)

    total = len(working_days)
    pct = round(present_days / total * 100, 1) if total else 0.0
    return {
        "student_id": student_id,
        "working_days": total,
        "present_days": present_days,
        "absent_days": total - present_days,
        "attendance_pct": pct,
    }


# ── Layer 2 — project the day fact onto a lecture ──────────────────────────


def _aware(dt: datetime | None) -> datetime | None:
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def lecture_status_from_day(
    day_row: DailyAttendance | None,
    lecture_start: datetime,
    lecture_end: datetime,
    campus_close: datetime,
    grace: timedelta,
) -> str:
    """Project a student's whole-day presence onto one lecture window.

    PRESENT/LATE if the presence interval [first_in, effective_out] overlaps the
    lecture, else ABSENT. A MISSING sign-off is treated as "on campus through
    close" so the student still counts for lectures before they left.
    """
    if day_row is None or day_row.day_status == "ABSENT":
        return "ABSENT"

    first_in = _aware(day_row.first_in)
    if first_in is None:
        return "ABSENT"

    # MISSING punch-out -> presumed present until campus close.
    effective_out = _aware(day_row.last_out) or campus_close
    start = _aware(lecture_start)
    end = _aware(lecture_end)

    # No overlap with the lecture window.
    if first_in >= end or effective_out <= start:
        return "ABSENT"

    return "PRESENT" if first_in <= start + grace else "LATE"


async def project_day_onto_lecture(
    session: AsyncSession,
    *,
    lecture_id: uuid.UUID,
    branch_id: uuid.UUID,
    current_user_id: uuid.UUID,
    tz_name: str | None = None,
) -> list:
    """Write an ``attendance_records`` row for EVERY student in the lecture's
    batch — present and absent (decision 2) — by projecting their day fact.

    Feeds the existing per-lecture view unchanged: same table, same key, same
    status/source enums. Manual rows are never overwritten (decision 7).
    """
    lecture = await lecture_repository.get_by_id(session, lecture_id)
    if not lecture:
        return []

    tz_name = tz_name or await branch_timezone(session, branch_id)
    day = local_date_of(lecture.scheduled_start, tz_name)
    _, campus_close = campus_window_on(day, tz_name)
    grace = timedelta(minutes=get_settings().ATTENDANCE_GRACE_PERIOD_MINUTES)

    student_ids = list((await session.execute(
        select(StudentBatchMapping.student_id).where(
            StudentBatchMapping.batch_id == lecture.batch_id,
            StudentBatchMapping.is_deleted == False,
        )
    )).scalars().all())
    if not student_ids:
        return []

    day_rows = {
        r.student_id: r
        for r in (await session.execute(
            select(DailyAttendance).where(
                DailyAttendance.student_id.in_(student_ids),
                DailyAttendance.attendance_date == day,
                DailyAttendance.is_deleted == False,
            )
        )).scalars().all()
    }

    now = datetime.now(timezone.utc)
    results = []
    for sid in student_ids:
        existing = await attendance_repository.get_existing_attendance(
            session, sid, lecture_id
        )
        if existing is not None and existing.source in _MANUAL_SOURCES:
            results.append(existing)  # human mark wins — untouched
            continue

        row = day_rows.get(sid)
        att_status = lecture_status_from_day(
            row, lecture.scheduled_start, lecture.scheduled_end, campus_close, grace
        )
        src = "BIOMETRIC" if (row is not None and row.day_status != "ABSENT") else "SYSTEM"

        if existing is not None:
            rec = await attendance_repository.update_attendance_record(
                session, existing,
                attendance_status=att_status,
                marked_at=now,
                marked_by=current_user_id,
                source=src,
            )
        else:
            rec = await attendance_repository.create_attendance_record(
                session,
                student_id=sid,
                lecture_id=lecture_id,
                attendance_status=att_status,
                marked_at=now,
                marked_by=current_user_id,
                source=src,
                branch_id=branch_id,
            )
        results.append(rec)

    await session.flush()
    return results
