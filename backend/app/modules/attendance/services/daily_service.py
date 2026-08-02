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

from sqlalchemy import func, select
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


async def rebuild_after_ingest(
    session: AsyncSession,
    *,
    branch_id: uuid.UUID,
    affected: list[tuple[uuid.UUID, datetime]],
    tz_name: str | None = None,
) -> int:
    """Recompute Layer 1 for exactly the (student, local-day) cells touched by a
    fresh punch ingest. Cheaper and more precise than sweeping the branch.

    ``affected`` is the (student_id, punch_timestamp) pairs ingest returned. We
    fold them to distinct (student_id, local-day) and rebuild each once.
    Returns the number of day rows rebuilt. MANUAL rows are left untouched by
    ``rebuild_daily`` itself (decision 7)."""
    if not affected:
        return 0
    tz_name = tz_name or await branch_timezone(session, branch_id)
    cells: set[tuple[uuid.UUID, date]] = {
        (student_id, local_date_of(ts, tz_name)) for student_id, ts in affected
    }
    for student_id, day in cells:
        await rebuild_daily(
            session, student_id=student_id, branch_id=branch_id, day=day, tz_name=tz_name
        )
    # Layer 2 follows immediately, so a punch shows up on the lecture roster and
    # not only in the day register.
    await project_after_ingest(
        session, branch_id=branch_id, cells=cells, tz_name=tz_name
    )
    return len(cells)


async def project_after_ingest(
    session: AsyncSession,
    *,
    branch_id: uuid.UUID,
    cells: set[tuple[uuid.UUID, date]],
    tz_name: str,
) -> int:
    """Refresh the lecture rosters touched by an ingest (Layer 1 -> Layer 2).

    Scoped deliberately: only lectures on an affected local day, and only for
    batches an affected student actually belongs to — projecting the whole
    branch on every punch would be needlessly expensive. Returns the number of
    lectures projected.

    ``project_day_onto_lecture`` rewrites every student in the lecture's batch,
    so each lecture is projected once regardless of how many of its students
    punched. Manual marks are still never overwritten.
    """
    by_day: dict[date, set[uuid.UUID]] = {}
    for student_id, day in cells:
        by_day.setdefault(day, set()).add(student_id)

    projected = 0
    for day, student_ids in by_day.items():
        start, end = day_bounds(day, tz_name)
        batch_ids = list((await session.execute(
            select(StudentBatchMapping.batch_id)
            .where(
                StudentBatchMapping.student_id.in_(student_ids),
                StudentBatchMapping.is_deleted == False,
            )
            .distinct()
        )).scalars().all())
        if not batch_ids:
            continue

        lecture_ids = list((await session.execute(
            select(Lecture.id).where(
                Lecture.branch_id == branch_id,
                Lecture.batch_id.in_(batch_ids),
                Lecture.scheduled_start >= start,
                Lecture.scheduled_start < end,
                Lecture.is_deleted == False,
            )
        )).scalars().all())

        for lecture_id in lecture_ids:
            # marked_by=None — nobody marked this, the system derived it.
            await project_day_onto_lecture(
                session,
                lecture_id=lecture_id,
                branch_id=branch_id,
                current_user_id=None,
                tz_name=tz_name,
            )
            projected += 1
    return projected


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


async def daily_ledger(
    session: AsyncSession,
    *,
    branch_id: uuid.UUID,
    start: date,
    end: date,
) -> list[dict]:
    """Reference C — the immutable all-students daily ledger.

    One row per student per day that has a ``DailyAttendance`` record in the
    range, joined to the student's identity. Deliberately **batch-independent**:
    it reads only Layer-1 day facts, so a student's history is complete and
    unchanged by any later batch / subject / profile edit — the permanent record
    the institute reviews per candidate. Ordered by student, then date.
    """
    rows = (await session.execute(
        select(
            Student.id,
            Student.first_name,
            Student.last_name,
            Student.enrollment_number,
            DailyAttendance.attendance_date,
            DailyAttendance.first_in,
            DailyAttendance.last_out,
            DailyAttendance.day_status,
            DailyAttendance.signoff,
            DailyAttendance.source,
        )
        .join(DailyAttendance, DailyAttendance.student_id == Student.id)
        .where(
            DailyAttendance.branch_id == branch_id,
            DailyAttendance.attendance_date >= start,
            DailyAttendance.attendance_date <= end,
            DailyAttendance.is_deleted == False,
            Student.is_deleted == False,
        )
        .order_by(Student.first_name, Student.last_name, DailyAttendance.attendance_date)
    )).all()
    return [
        {
            "student_id": r.id,
            "name": f"{r.first_name} {r.last_name}".strip(),
            "enrollment_number": r.enrollment_number,
            "attendance_date": r.attendance_date,
            "first_in": r.first_in,
            "last_out": r.last_out,
            "day_status": r.day_status,
            "signoff": r.signoff,
            "source": r.source,
        }
        for r in rows
    ]


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


def _status_code(day_status: str | None) -> str:
    """Register cell: P (present), L (late), A (absent / no row)."""
    if day_status == "PRESENT":
        return "P"
    if day_status == "LATE":
        return "L"
    return "A"


async def _batch_working_dates(
    session: AsyncSession,
    branch_id: uuid.UUID,
    batch_id: uuid.UUID,
    start: date,
    end: date,
    tz_name: str,
) -> list[date]:
    """Local dates in range with >=1 scheduled lecture for the batch (the
    register's columns / the % denominator — decision 1)."""
    range_start, _ = day_bounds(start, tz_name)
    _, range_end = day_bounds(end, tz_name)
    starts = (await session.execute(
        select(Lecture.scheduled_start).where(
            Lecture.batch_id == batch_id,
            Lecture.branch_id == branch_id,
            Lecture.scheduled_start >= range_start,
            Lecture.scheduled_start < range_end,
            Lecture.is_deleted == False,
        )
    )).scalars().all()
    days = {local_date_of(s, tz_name) for s in starts}
    return sorted(d for d in days if start <= d <= end)


async def batch_matrix(
    session: AsyncSession,
    *,
    branch_id: uuid.UUID,
    batch_id: uuid.UUID,
    start: date,
    end: date,
    tz_name: str | None = None,
) -> dict:
    """Register matrix for one batch: students × working-day columns, each cell
    P/L/A, plus per-student % and per-day present totals.

    Columns are the *union* of scheduled-lecture days and any day a current batch
    member actually has an attendance record — so a real punch is never hidden
    just because no lecture was timetabled that day (e.g. a batch with no
    schedule, or a student moved into it). Absent-sweep rows only exist on
    scheduled days, so the union adds exactly the extra punch-days and nothing
    else."""
    tz_name = tz_name or await branch_timezone(session, branch_id)

    students = (await session.execute(
        select(Student)
        .join(StudentBatchMapping, StudentBatchMapping.student_id == Student.id)
        .where(
            StudentBatchMapping.batch_id == batch_id,
            StudentBatchMapping.is_deleted == False,
            Student.is_deleted == False,
        )
        .order_by(Student.first_name, Student.last_name)
    )).scalars().unique().all()
    student_ids = [s.id for s in students]

    scheduled = await _batch_working_dates(session, branch_id, batch_id, start, end, tz_name)
    attended: set[date] = set()
    if student_ids:
        attended = {
            d for d in (await session.execute(
                select(DailyAttendance.attendance_date).where(
                    DailyAttendance.student_id.in_(student_ids),
                    DailyAttendance.branch_id == branch_id,
                    DailyAttendance.attendance_date >= start,
                    DailyAttendance.attendance_date <= end,
                    DailyAttendance.day_status.in_(_PRESENT_STATUSES),
                    DailyAttendance.is_deleted == False,
                ).distinct()
            )).scalars().all()
        }
    dates = sorted(set(scheduled) | attended)

    by_student_date: dict[uuid.UUID, dict[date, str]] = {}
    if student_ids and dates:
        rows = (await session.execute(
            select(DailyAttendance).where(
                DailyAttendance.student_id.in_(student_ids),
                DailyAttendance.attendance_date >= dates[0],
                DailyAttendance.attendance_date <= dates[-1],
                DailyAttendance.is_deleted == False,
            )
        )).scalars().all()
        for r in rows:
            by_student_date.setdefault(r.student_id, {})[r.attendance_date] = (
                _status_code(r.day_status)
            )

    total_days = len(dates)
    student_rows = []
    day_present = {d: 0 for d in dates}
    for s in students:
        cells = []
        present = 0
        smap = by_student_date.get(s.id, {})
        for d in dates:
            code = smap.get(d, "A")
            cells.append(code)
            if code in ("P", "L"):
                present += 1
                day_present[d] += 1
        pct = round(present / total_days * 100, 1) if total_days else 0.0
        student_rows.append({
            "student_id": s.id,
            "name": f"{s.first_name} {s.last_name}".strip(),
            "enrollment_number": s.enrollment_number,
            "cells": cells,
            "present": present,
            "working_days": total_days,
            "attendance_pct": pct,
        })

    return {
        "batch_id": batch_id,
        "dates": dates,
        "students": student_rows,
        "day_present": [day_present[d] for d in dates],
        "student_count": len(students),
    }


async def branch_summary(
    session: AsyncSession,
    *,
    branch_id: uuid.UUID,
    start: date,
    end: date,
    tz_name: str | None = None,
) -> list[dict]:
    """One summary row per active batch in the branch: students, present/total
    slots, avg attendance %. Powers the all-batches report."""
    from app.modules.batch.models.batch_models import Batch

    tz_name = tz_name or await branch_timezone(session, branch_id)
    batches = (await session.execute(
        select(Batch)
        .where(Batch.branch_id == branch_id, Batch.is_deleted == False)
        .order_by(Batch.name)
    )).scalars().all()

    out = []
    for b in batches:
        m = await batch_matrix(
            session, branch_id=branch_id, batch_id=b.id,
            start=start, end=end, tz_name=tz_name,
        )
        total_slots = m["student_count"] * len(m["dates"])
        present = sum(r["present"] for r in m["students"])
        avg_pct = round(present / total_slots * 100, 1) if total_slots else 0.0
        out.append({
            "batch_id": b.id,
            "batch_name": b.name,
            "batch_code": b.code,
            "student_count": m["student_count"],
            "working_days": len(m["dates"]),
            "present": present,
            "total_slots": total_slots,
            "avg_pct": avg_pct,
        })
    return out


async def branch_defaulters(
    session: AsyncSession,
    *,
    branch_id: uuid.UUID,
    start: date,
    end: date,
    threshold: float = 75.0,
    tz_name: str | None = None,
) -> list[dict]:
    """Students whose range attendance % is below ``threshold`` (the board that
    surfaces the 75% eligibility rule).

    Aggregated across every active batch: a student in two batches has their
    present/working-day counts summed, so the % reflects their whole schedule
    rather than one batch. Built from ``batch_matrix`` so the numbers match the
    on-screen matrix exactly. Sorted worst-first. Students with zero working
    days in range are excluded (no denominator, not a defaulter)."""
    from app.modules.batch.models.batch_models import Batch

    tz_name = tz_name or await branch_timezone(session, branch_id)
    batches = (await session.execute(
        select(Batch)
        .where(Batch.branch_id == branch_id, Batch.is_deleted == False)
        .order_by(Batch.name)
    )).scalars().all()

    agg: dict[uuid.UUID, dict] = {}
    for b in batches:
        m = await batch_matrix(
            session, branch_id=branch_id, batch_id=b.id,
            start=start, end=end, tz_name=tz_name,
        )
        for r in m["students"]:
            a = agg.get(r["student_id"])
            if a is None:
                a = {
                    "student_id": r["student_id"],
                    "name": r["name"],
                    "enrollment_number": r["enrollment_number"],
                    "batches": [],
                    "present": 0,
                    "working_days": 0,
                }
                agg[r["student_id"]] = a
            a["present"] += r["present"]
            a["working_days"] += r["working_days"]
            if b.name not in a["batches"]:
                a["batches"].append(b.name)

    out = []
    for a in agg.values():
        wd = a["working_days"]
        if wd <= 0:
            continue
        pct = round(a["present"] / wd * 100, 1)
        if pct < threshold:
            out.append({**a, "attendance_pct": pct})

    out.sort(key=lambda x: (x["attendance_pct"], x["name"]))
    return out


async def branch_roster_attendance(
    session: AsyncSession,
    *,
    branch_id: uuid.UUID,
    student_ids: list[uuid.UUID],
    tz_name: str | None = None,
) -> dict[uuid.UUID, float]:
    """All-time canonical attendance % per student for the branch roster.

    Same definition as :func:`monthly_summary` (present working days /
    working days, decision 1) but batched over the whole roster and
    unbounded in time — the single source of truth for the roster/top-KPI
    attendance number so it can never drift from the biometric heatmap,
    defaulter board, or institute overview, all of which read Layer 1.

    A student not present here (no working days) gets no entry; the caller
    treats a missing student as 0.0.
    """
    if not student_ids:
        return {}
    tz_name = tz_name or await branch_timezone(session, branch_id)

    # student -> their batches (union of working days, matching monthly_summary
    # for the rare multi-batch student).
    student_batches: dict[uuid.UUID, set[uuid.UUID]] = {}
    all_batch_ids: set[uuid.UUID] = set()
    for sid, bid in (await session.execute(
        select(StudentBatchMapping.student_id, StudentBatchMapping.batch_id).where(
            StudentBatchMapping.student_id.in_(student_ids),
            StudentBatchMapping.is_deleted == False,
        )
    )).all():
        student_batches.setdefault(sid, set()).add(bid)
        all_batch_ids.add(bid)
    if not all_batch_ids:
        return {}

    # batch -> set of local working dates (>=1 scheduled lecture that day).
    batch_working: dict[uuid.UUID, set[date]] = {}
    for bid, start in (await session.execute(
        select(Lecture.batch_id, Lecture.scheduled_start).where(
            Lecture.batch_id.in_(all_batch_ids),
            Lecture.branch_id == branch_id,
            Lecture.is_deleted == False,
        )
    )).all():
        batch_working.setdefault(bid, set()).add(local_date_of(start, tz_name))

    # student -> set of present local dates (PRESENT / LATE).
    present_dates: dict[uuid.UUID, set[date]] = {}
    for sid, day in (await session.execute(
        select(DailyAttendance.student_id, DailyAttendance.attendance_date).where(
            DailyAttendance.student_id.in_(student_ids),
            DailyAttendance.branch_id == branch_id,
            DailyAttendance.day_status.in_(_PRESENT_STATUSES),
            DailyAttendance.is_deleted == False,
        )
    )).all():
        present_dates.setdefault(sid, set()).add(day)

    out: dict[uuid.UUID, float] = {}
    for sid in student_ids:
        working: set[date] = set()
        for bid in student_batches.get(sid, ()):  # noqa: SIM118 — set, not dict
            working |= batch_working.get(bid, set())
        if not working:
            continue
        present = len(working & present_dates.get(sid, set()))
        out[sid] = round(present / len(working) * 100, 1)
    return out


async def teacher_turnout_in_range(
    session: AsyncSession,
    *,
    branch_id: uuid.UUID,
    from_dt: datetime | None,
    to_dt: datetime | None,
    tz_name: str | None = None,
) -> dict[uuid.UUID, dict]:
    """Per effective-teacher student turnout over their completed lectures.

    A lecture's turnout = present students in its batch on that local day /
    batch size, read from Layer 1 ``DailyAttendance`` (PRESENT/LATE) — the same
    canonical present-basis as every other attendance %. Averaged across the
    teacher's completed lectures so it answers "how well-attended are this
    teacher's classes". Credited to the *effective* teacher
    (coalesce(actual_teacher_id, teacher_id)) so a substitute earns the turnout
    of the class they actually delivered — matching the productivity row.

    Returns ``{teacher_id: {"turnout_pct": float, "turnout_lectures": int}}``;
    a teacher whose lectures' batches have no enrolled students is omitted.
    """
    tz_name = tz_name or await branch_timezone(session, branch_id)

    effective_teacher = func.coalesce(
        Lecture.actual_teacher_id, Lecture.teacher_id
    )
    filters = [
        Lecture.branch_id == branch_id,
        Lecture.is_deleted == False,  # noqa: E712
        Lecture.lecture_status == "completed",
    ]
    if from_dt is not None:
        filters.append(Lecture.scheduled_start >= from_dt)
    if to_dt is not None:
        filters.append(Lecture.scheduled_start <= to_dt)

    lecture_rows = (await session.execute(
        select(effective_teacher, Lecture.batch_id, Lecture.scheduled_start).where(
            *filters
        )
    )).all()
    if not lecture_rows:
        return {}

    # (teacher, batch, local-date) per completed lecture.
    triples: list[tuple[uuid.UUID, uuid.UUID, date]] = []
    batch_ids: set[uuid.UUID] = set()
    dates: set[date] = set()
    for teacher_id, batch_id, scheduled_start in lecture_rows:
        if teacher_id is None or batch_id is None:
            continue
        d = local_date_of(scheduled_start, tz_name)
        triples.append((teacher_id, batch_id, d))
        batch_ids.add(batch_id)
        dates.add(d)
    if not triples:
        return {}

    # batch -> its active students (roster size + membership).
    batch_students: dict[uuid.UUID, set[uuid.UUID]] = {}
    for sid, bid in (await session.execute(
        select(StudentBatchMapping.student_id, StudentBatchMapping.batch_id).where(
            StudentBatchMapping.batch_id.in_(batch_ids),
            StudentBatchMapping.is_deleted == False,  # noqa: E712
        )
    )).all():
        batch_students.setdefault(bid, set()).add(sid)

    all_students = {s for members in batch_students.values() for s in members}
    # (student, date) present on that day, limited to the lecture days.
    present: set[tuple[uuid.UUID, date]] = set()
    if all_students:
        for sid, d in (await session.execute(
            select(DailyAttendance.student_id, DailyAttendance.attendance_date).where(
                DailyAttendance.student_id.in_(all_students),
                DailyAttendance.branch_id == branch_id,
                DailyAttendance.attendance_date.in_(dates),
                DailyAttendance.day_status.in_(_PRESENT_STATUSES),
                DailyAttendance.is_deleted == False,  # noqa: E712
            )
        )).all():
            present.add((sid, d))

    acc: dict[uuid.UUID, list[float]] = {}
    for teacher_id, batch_id, d in triples:
        roster = batch_students.get(batch_id, set())
        if not roster:
            continue
        present_count = sum(1 for s in roster if (s, d) in present)
        acc.setdefault(teacher_id, []).append(present_count / len(roster))

    return {
        tid: {
            "turnout_pct": round(sum(ratios) / len(ratios) * 100, 1),
            "turnout_lectures": len(ratios),
        }
        for tid, ratios in acc.items()
    }


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
    current_user_id: uuid.UUID | None,
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
