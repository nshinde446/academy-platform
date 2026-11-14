"""Saturday / Sunday work flow (Point 5).

Three steps:
  1. Pre-approval — a senior picks the weekend date + the staff allowed to come.
  2. Work content — the teacher writes what they did in Teacher Login.
  3. Report & approval — the approver reviews and sets the Work Approved Status.

Time IN / Time OUT, the day status and worked minutes are **read** live from
``StaffDailyAttendance`` (the biometric twin), never duplicated here, so the
report always agrees with the attendance screen. An approved worked weekend
credits payroll naturally — a punched weekend day is PRESENT/HALF_DAY in
``StaffDailyAttendance`` and ``payroll.calc_service.compute_month`` already counts
it as an extra day; ``credit_days`` records that intended credit (1.0 / 0.5) for
the report and audit.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.attendance.models.attendance_models import StaffDailyAttendance
from app.modules.attendance.services import daily_service
from app.modules.attendance.time_utils import get_tz
from app.modules.audit.services import audit_service
from app.modules.staff.models.staff_models import Staff
from app.modules.teacher.models.teacher_models import WeekendWork

# Rule 3: minimum 5 hours of login time is required on a weekend work day.
MIN_WORK_MINUTES = 300

_FULL_DAY = ("PRESENT", "LATE")
_HALF_DAY = ("HALF_DAY",)

# The rules printed as a NOTE at the bottom of the report (Point 5, verbatim).
REPORT_RULES = [
    "Working on Saturdays/Sundays must be pre-approved.",
    "Work content/work done on the day needs to be shared.",
    "Minimum 5 hours of login time is required.",
    "Compulsory IN and OUT time should be punched in the biometric system.",
    "Failing to do so, the teacher will be marked ABSENT for the day. "
    "The decision is at the discretion of Management.",
]


def _is_weekend(d: date) -> bool:
    return d.weekday() >= 5  # Sat = 5, Sun = 6


def _credit_for(day_status: str | None, marked_absent: bool) -> float:
    if marked_absent:
        return 0.0
    if day_status in _FULL_DAY:
        return 1.0
    if day_status in _HALF_DAY:
        return 0.5
    return 0.0


def _day_code(day_status: str | None, marked_absent: bool) -> str:
    """Short status code for the report (Point 5): P = Present, HD = Half Day,
    A = Absent. (Leave 'L' is derivable from declared leave; not shown here.)"""
    if marked_absent:
        return "A"
    if day_status in _FULL_DAY:
        return "P"
    if day_status in _HALF_DAY:
        return "HD"
    return "A"


async def _staff_in_branch(
    session: AsyncSession, branch_id: uuid.UUID, staff_ids: list[uuid.UUID]
) -> dict[uuid.UUID, Staff]:
    if not staff_ids:
        return {}
    rows = (await session.execute(
        select(Staff).where(
            Staff.id.in_(staff_ids),
            Staff.branch_id == branch_id,
            Staff.is_deleted == False,  # noqa: E712
        )
    )).scalars().all()
    return {s.id: s for s in rows}


async def preapprove(
    session: AsyncSession,
    *,
    branch_id: uuid.UUID,
    staff_ids: list[uuid.UUID],
    work_date: date,
    user_id: uuid.UUID,
    ip: str | None = None,
) -> dict:
    """Step 1 — pre-approve a weekend date for a set of staff. Idempotent: a staff
    that already has a live row for the date is left as-is (skipped)."""
    if not _is_weekend(work_date):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Pre-approval is only for Saturdays and Sundays.",
        )
    staff_map = await _staff_in_branch(session, branch_id, staff_ids)
    existing = {
        r.staff_id
        for r in (await session.execute(
            select(WeekendWork).where(
                WeekendWork.branch_id == branch_id,
                WeekendWork.work_date == work_date,
                WeekendWork.is_deleted == False,  # noqa: E712
            )
        )).scalars().all()
    }
    created = 0
    for sid in staff_ids:
        if sid not in staff_map or sid in existing:
            continue
        session.add(WeekendWork(
            branch_id=branch_id,
            staff_id=sid,
            work_date=work_date,
            pre_approved_by=user_id,
            approval_status="PENDING",
            created_by=user_id,
        ))
        created += 1
    await session.flush()

    await audit_service.log_action(
        session, user_id=user_id, action="WEEKEND_PREAPPROVE",
        table_name="weekend_work", record_id=uuid.uuid4(),
        new_values={"work_date": str(work_date), "created": created},
        ip_address=ip, branch_id=branch_id,
    )
    return {"created": created, "skipped": len(staff_ids) - created}


async def _attendance_map(
    session: AsyncSession,
    branch_id: uuid.UUID,
    staff_ids: list[uuid.UUID],
    start: date,
    end: date,
) -> dict[tuple[uuid.UUID, date], StaffDailyAttendance]:
    if not staff_ids:
        return {}
    rows = (await session.execute(
        select(StaffDailyAttendance).where(
            StaffDailyAttendance.staff_id.in_(staff_ids),
            StaffDailyAttendance.branch_id == branch_id,
            StaffDailyAttendance.attendance_date >= start,
            StaffDailyAttendance.attendance_date <= end,
            StaffDailyAttendance.is_deleted == False,  # noqa: E712
        )
    )).scalars().all()
    return {(r.staff_id, r.attendance_date): r for r in rows}


def _local_hhmm(dt: datetime | None, tz) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(tz).strftime("%H:%M")


async def _build_rows(
    session: AsyncSession,
    branch_id: uuid.UUID,
    works: list[WeekendWork],
) -> list[dict]:
    if not works:
        return []
    staff_ids = list({w.staff_id for w in works})
    staff_map = {
        s.id: s for s in (await session.execute(
            select(Staff).where(Staff.id.in_(staff_ids))
        )).scalars().all()
    }
    lo = min(w.work_date for w in works)
    hi = max(w.work_date for w in works)
    att = await _attendance_map(session, branch_id, staff_ids, lo, hi)
    tz = get_tz(await daily_service.branch_timezone(session, branch_id))

    out: list[dict] = []
    for w in sorted(works, key=lambda x: (x.work_date, x.staff_id)):
        s = staff_map.get(w.staff_id)
        a = att.get((w.staff_id, w.work_date))
        day_status = a.day_status if a else None
        work_minutes = a.work_minutes if a else 0
        time_in = _local_hhmm(a.first_in if a else None, tz)
        time_out = _local_hhmm(a.last_out if a else None, tz)
        missing_punch = time_in is None or time_out is None
        warning = missing_punch or (work_minutes < MIN_WORK_MINUTES)
        name = f"{s.first_name} {s.last_name}".strip() if s else "—"
        out.append({
            "id": w.id,
            "staff_id": w.staff_id,
            "emp_code": s.emp_code if s else None,
            "name": name,
            "work_date": w.work_date,
            "day_code": _day_code(day_status, w.marked_absent),
            "time_in": time_in,
            "time_out": time_out,
            "work_minutes": work_minutes,
            "work_content": w.work_content,
            "approval_status": w.approval_status,
            "approval_note": w.approval_note,
            "marked_absent": w.marked_absent,
            "credit_days": float(w.credit_days),
            "warning": warning,
        })
    return out


async def report(
    session: AsyncSession,
    *,
    branch_id: uuid.UUID,
    start: date,
    end: date,
    staff_id: uuid.UUID | None = None,
    approval_status: str | None = None,
) -> dict:
    """The weekend-work report (Point 5) over a date range, optionally filtered by
    teacher and approval status. Rows carry biometric IN/OUT + the day code +
    content + approval + a warning flag, and the rules note for the footer."""
    q = select(WeekendWork).where(
        WeekendWork.branch_id == branch_id,
        WeekendWork.work_date >= start,
        WeekendWork.work_date <= end,
        WeekendWork.is_deleted == False,  # noqa: E712
    )
    if staff_id is not None:
        q = q.where(WeekendWork.staff_id == staff_id)
    if approval_status:
        q = q.where(WeekendWork.approval_status == approval_status)
    works = list((await session.execute(q)).scalars().all())
    rows = await _build_rows(session, branch_id, works)
    return {"rows": rows, "rules": REPORT_RULES}


async def list_for_teacher(
    session: AsyncSession,
    *,
    staff_id: uuid.UUID,
    start: date,
    end: date,
) -> list[dict]:
    """A teacher's own pre-approved weekend days in a range (for Teacher Login).
    Branch is taken from the rows themselves (all the teacher's own branch)."""
    works = list((await session.execute(
        select(WeekendWork).where(
            WeekendWork.staff_id == staff_id,
            WeekendWork.work_date >= start,
            WeekendWork.work_date <= end,
            WeekendWork.is_deleted == False,  # noqa: E712
        )
    )).scalars().all())
    if not works:
        return []
    return await _build_rows(session, works[0].branch_id, works)


async def submit_work_content(
    session: AsyncSession,
    *,
    staff_id: uuid.UUID,
    work_id: uuid.UUID,
    content: str,
    user_id: uuid.UUID,
    ip: str | None = None,
) -> dict:
    """Step 2 — the teacher writes/edits their work content. Only their own row,
    and only while it hasn't been approved yet."""
    w = (await session.execute(
        select(WeekendWork).where(
            WeekendWork.id == work_id,
            WeekendWork.staff_id == staff_id,
            WeekendWork.is_deleted == False,  # noqa: E712
        )
    )).scalar_one_or_none()
    if w is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Weekend work entry not found.",
        )
    if w.approval_status == "APPROVED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This entry is already approved and can't be edited.",
        )
    w.work_content = (content or "").strip() or None
    w.work_content_at = datetime.now(timezone.utc)
    w.updated_by = user_id
    await session.flush()
    rows = await _build_rows(session, w.branch_id, [w])
    return rows[0]


async def decide(
    session: AsyncSession,
    *,
    work_id: uuid.UUID,
    branch_id: uuid.UUID,
    approve: bool,
    note: str | None,
    user_id: uuid.UUID,
    ip: str | None = None,
) -> dict:
    """Step 3 — approve or reject. On approval the credited extra days are derived
    from the day's attendance status (unless management marked it absent)."""
    w = (await session.execute(
        select(WeekendWork).where(
            WeekendWork.id == work_id,
            WeekendWork.branch_id == branch_id,
            WeekendWork.is_deleted == False,  # noqa: E712
        )
    )).scalar_one_or_none()
    if w is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Weekend work entry not found.",
        )
    w.approval_status = "APPROVED" if approve else "REJECTED"
    w.approved_by = user_id
    w.approved_at = datetime.now(timezone.utc)
    w.approval_note = (note or "").strip() or None
    if approve:
        a = (await session.execute(
            select(StaffDailyAttendance).where(
                StaffDailyAttendance.staff_id == w.staff_id,
                StaffDailyAttendance.attendance_date == w.work_date,
                StaffDailyAttendance.is_deleted == False,  # noqa: E712
            )
        )).scalar_one_or_none()
        w.credit_days = _credit_for(a.day_status if a else None, w.marked_absent)
    else:
        w.credit_days = 0.0
    w.updated_by = user_id
    await session.flush()

    await audit_service.log_action(
        session, user_id=user_id,
        action="WEEKEND_APPROVE" if approve else "WEEKEND_REJECT",
        table_name="weekend_work", record_id=w.id,
        new_values={"status": w.approval_status, "credit_days": float(w.credit_days)},
        ip_address=ip, branch_id=branch_id,
    )
    rows = await _build_rows(session, branch_id, [w])
    return rows[0]


async def set_marked_absent(
    session: AsyncSession,
    *,
    work_id: uuid.UUID,
    branch_id: uuid.UUID,
    absent: bool,
    user_id: uuid.UUID,
    ip: str | None = None,
) -> dict:
    """Management override (Rule 5) — force the day ABSENT (or clear it). Keeps the
    credited days in sync when the entry is already approved."""
    w = (await session.execute(
        select(WeekendWork).where(
            WeekendWork.id == work_id,
            WeekendWork.branch_id == branch_id,
            WeekendWork.is_deleted == False,  # noqa: E712
        )
    )).scalar_one_or_none()
    if w is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Weekend work entry not found.",
        )
    w.marked_absent = absent
    if w.approval_status == "APPROVED":
        a = (await session.execute(
            select(StaffDailyAttendance).where(
                StaffDailyAttendance.staff_id == w.staff_id,
                StaffDailyAttendance.attendance_date == w.work_date,
                StaffDailyAttendance.is_deleted == False,  # noqa: E712
            )
        )).scalar_one_or_none()
        w.credit_days = _credit_for(a.day_status if a else None, absent)
    w.updated_by = user_id
    await session.flush()

    await audit_service.log_action(
        session, user_id=user_id, action="WEEKEND_MARK_ABSENT",
        table_name="weekend_work", record_id=w.id,
        new_values={"marked_absent": absent}, ip_address=ip, branch_id=branch_id,
    )
    rows = await _build_rows(session, branch_id, [w])
    return rows[0]
