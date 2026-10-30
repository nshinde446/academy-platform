"""Teacher leave — apply + balance + history (Teacher Portal Changes 2/3/4).

A teacher applies for typed leave (casual/sick/paid/lwp) from the portal; the
request starts ``pending`` and only blocks scheduling once the academic head
approves it. The teacher id is resolved from the session's staff link
(``staff.linked_teacher_id``) so a teacher can only ever file/cancel their own
leave. Balance per type = Quota − Used(approved) − Pending (LWP unlimited).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.services import audit_service
from app.modules.lectures.models.lecture_models import Holiday
from app.modules.staff.models.staff_models import Staff
from app.modules.teacher.models.teacher_models import (
    LeaveTypeQuota,
    Teacher,
    TeacherLeave,
)
from app.modules.teacher.repositories import teacher_repository
from app.modules.teacher_portal.services import config_service

LEAVE_TYPES = ("casual", "sick", "paid", "lwp")
QUOTA_TYPES = ("casual", "sick", "paid")  # lwp has no quota
_ACTIVE = ("pending", "approved")  # statuses that hold/consume balance


async def _staff(session: AsyncSession, staff_id: uuid.UUID) -> Staff:
    s = (await session.execute(
        select(Staff).where(Staff.id == staff_id, Staff.is_deleted == False)  # noqa: E712
    )).scalar_one_or_none()
    if s is None:
        raise HTTPException(status_code=404, detail="Staff record not found")
    return s


async def _teacher_for_staff(session: AsyncSession, staff_id: uuid.UUID) -> tuple[Teacher, Staff]:
    s = await _staff(session, staff_id)
    if s.linked_teacher_id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This account is not linked to a teaching record, so leave "
                   "cannot be applied here. Please contact the office.",
        )
    t = await teacher_repository.get_by_id(session, s.linked_teacher_id)
    if t is None:
        raise HTTPException(status_code=404, detail="Teacher record not found")
    return t, s


def _weekly_off_set(staff: Staff) -> set[int]:
    from app.core.config.settings import get_settings
    raw = staff.weekly_off_days if staff.weekly_off_days is not None else get_settings().STAFF_WEEKLY_OFF_DAYS
    return {int(p) for p in (raw or "").split(",") if p.strip().isdigit()}


async def _holidays(session: AsyncSession, branch_id: uuid.UUID, start: date, end: date) -> set[date]:
    return {
        h for (h,) in (await session.execute(
            select(Holiday.holiday_date).where(
                Holiday.branch_id == branch_id,
                Holiday.holiday_date >= start,
                Holiday.holiday_date <= end,
                Holiday.is_deleted == False,  # noqa: E712
            )
        )).all()
    }


def _count_days(start: date, end: date, half_day: bool, weekly_off: set[int], holidays: set[date]) -> float:
    """Leave day count — working days only (weekly offs + holidays excluded);
    a half-day leave is 0.5 (single date)."""
    if half_day:
        return 0.5
    n = 0
    d = start
    while d <= end:
        if d.weekday() not in weekly_off and d not in holidays:
            n += 1
        d += timedelta(days=1)
    return float(n)


def _row(leave: TeacherLeave, days: float | None = None) -> dict:
    return {
        "id": leave.id,
        "leave_type": leave.leave_type,
        "half_day": leave.half_day,
        "start_date": leave.start_date,
        "end_date": leave.end_date,
        "days": days,
        "reason": leave.reason,
        "status": leave.approval_status,
        "applied_on": leave.created_at.isoformat() if leave.created_at else None,
        "decided_at": leave.decided_at.isoformat() if leave.decided_at else None,
        "decision_note": leave.decision_note,
    }


async def apply_leave(
    session: AsyncSession,
    *,
    staff_id: uuid.UUID,
    user_id: uuid.UUID,
    leave_type: str,
    start_date: date,
    end_date: date,
    half_day: bool,
    reason: str | None,
    ip: str | None = None,
) -> dict:
    leave_type = (leave_type or "casual").lower()
    if leave_type not in LEAVE_TYPES:
        raise HTTPException(status_code=422, detail="Unknown leave type.")
    if end_date < start_date:
        raise HTTPException(status_code=422, detail="To date must not be before From date.")
    if half_day and start_date != end_date:
        raise HTTPException(status_code=422, detail="A half-day leave is a single date.")

    cfg = await config_service.get_config(session)
    if half_day and not cfg.get("leave_half_day_allowed", True):
        raise HTTPException(status_code=422, detail="Half-day leave is not allowed.")

    today = date.today()
    backdate = int(cfg.get("leave_backdate_days", 7) or 0)
    if start_date < today - timedelta(days=backdate):
        raise HTTPException(
            status_code=422,
            detail=f"Leave cannot start more than {backdate} days in the past.",
        )
    # Future bound — end of the academic year (approximated; client to confirm).
    if start_date > today + timedelta(days=365):
        raise HTTPException(status_code=422, detail="Leave is too far in the future.")

    t, s = await _teacher_for_staff(session, staff_id)

    # Overlap only against still-active (pending/approved) requests.
    existing = await teacher_repository.list_leaves(session, t.branch_id, teacher_id=t.id)
    for e in existing:
        if e.approval_status in _ACTIVE and e.start_date <= end_date and e.end_date >= start_date:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="You already have a leave request overlapping these dates.",
            )

    weekly_off = _weekly_off_set(s)
    holidays = await _holidays(session, t.branch_id, start_date, end_date)
    days = _count_days(start_date, end_date, half_day, weekly_off, holidays)
    if days <= 0:
        raise HTTPException(status_code=422, detail="No working days in the selected range.")

    # Quota check for paid types (Q4 default: block, suggest LWP).
    if leave_type in QUOTA_TYPES:
        bal = await _type_balance(session, t, s, leave_type, start_date.year)
        if bal["available"] is not None and days > bal["available"]:
            raise HTTPException(
                status_code=422,
                detail=(f"Not enough {leave_type} balance "
                        f"({bal['available']:g} left). Apply Leave Without Pay instead."),
            )

    leave = await teacher_repository.create_leave(
        session, teacher_id=t.id, branch_id=t.branch_id,
        start_date=start_date, end_date=end_date, reason=reason,
        approval_status="pending", requested_by=user_id,
        leave_type=leave_type, half_day=half_day,
    )
    await audit_service.log_action(
        session, user_id=user_id, action="CREATE", table_name="teacher_leaves",
        record_id=leave.id,
        new_values={"leave_request": True, "type": leave_type, "days": days, "status": "pending"},
        ip_address=ip, branch_id=t.branch_id,
    )
    return _row(leave, days)


async def _leaves_for_year(
    session: AsyncSession, teacher: Teacher, year: int
) -> list[TeacherLeave]:
    rows = await teacher_repository.list_leaves(session, teacher.branch_id, teacher_id=teacher.id)
    return [r for r in rows if r.start_date.year == year]


async def _type_balance(
    session: AsyncSession, teacher: Teacher, staff: Staff, leave_type: str, year: int
) -> dict:
    quota = (await session.execute(
        select(LeaveTypeQuota.quota_days).where(
            LeaveTypeQuota.branch_id == teacher.branch_id,
            LeaveTypeQuota.year == year,
            LeaveTypeQuota.leave_type == leave_type,
            LeaveTypeQuota.is_deleted == False,  # noqa: E712
        )
    )).scalar_one_or_none()
    quota_val = float(quota) if quota is not None else None

    weekly_off = _weekly_off_set(staff)
    used = pending = 0.0
    for lv in await _leaves_for_year(session, teacher, year):
        if lv.leave_type != leave_type or lv.approval_status not in _ACTIVE:
            continue
        hol = await _holidays(session, teacher.branch_id, lv.start_date, lv.end_date)
        d = _count_days(lv.start_date, lv.end_date, lv.half_day, weekly_off, hol)
        if lv.approval_status == "approved":
            used += d
        else:
            pending += d

    available = None if quota_val is None else round(quota_val - used - pending, 1)
    return {
        "leave_type": leave_type,
        "quota": quota_val,
        "used": round(used, 1),
        "pending": round(pending, 1),
        "available": available,
    }


async def balance(session: AsyncSession, staff_id: uuid.UUID, year: int) -> dict:
    """Per-type balance cards for the signed-in teacher (Change 3)."""
    t, s = await _teacher_for_staff(session, staff_id)
    return {
        "year": year,
        "types": [await _type_balance(session, t, s, lt, year) for lt in LEAVE_TYPES],
    }


async def my_leaves(
    session: AsyncSession,
    staff_id: uuid.UUID,
    *,
    year: int | None = None,
    month: int | None = None,
    status_filter: str | None = None,
) -> list[dict]:
    """My requests, newest first, with filters (Change 4)."""
    t, s = await _teacher_for_staff(session, staff_id)
    rows = await teacher_repository.list_leaves(session, t.branch_id, teacher_id=t.id)
    weekly_off = _weekly_off_set(s)
    out: list[dict] = []
    for r in sorted(rows, key=lambda x: (x.created_at or datetime.min.replace(tzinfo=timezone.utc)), reverse=True):
        if year is not None and r.start_date.year != year:
            continue
        if month is not None and r.start_date.month != month:
            continue
        if status_filter and r.approval_status != status_filter:
            continue
        hol = await _holidays(session, t.branch_id, r.start_date, r.end_date)
        out.append(_row(r, _count_days(r.start_date, r.end_date, r.half_day, weekly_off, hol)))
    return out


async def cancel_leave(
    session: AsyncSession, *, staff_id: uuid.UUID, leave_id: uuid.UUID, user_id: uuid.UUID,
    ip: str | None = None,
) -> None:
    t, _ = await _teacher_for_staff(session, staff_id)
    leave = await teacher_repository.get_leave_by_id(session, leave_id)
    if leave is None or leave.teacher_id != t.id:
        raise HTTPException(status_code=404, detail="Leave request not found")
    if leave.approval_status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only a pending request can be cancelled.",
        )
    # Keep the record in history (not deleted) — mark cancelled.
    leave.approval_status = "cancelled"
    leave.decided_by = user_id
    leave.decided_at = datetime.now(timezone.utc)
    await session.flush()
    await audit_service.log_action(
        session, user_id=user_id, action="UPDATE", table_name="teacher_leaves",
        record_id=leave.id, new_values={"approval_status": "cancelled"}, ip_address=ip,
        branch_id=t.branch_id,
    )


# ── admin: approve / reject ──────────────────────────────────────────────────

async def list_requests(
    session: AsyncSession, *, branch_id: uuid.UUID, status_filter: str | None = None,
) -> list[dict]:
    rows = await teacher_repository.list_leaves(session, branch_id, status=status_filter)
    out: list[dict] = []
    for r in rows:
        t = await teacher_repository.get_by_id(session, r.teacher_id)
        name = f"{t.first_name} {t.last_name}".strip() if t else "—"
        out.append({**_row(r), "teacher_id": r.teacher_id, "teacher_name": name})
    out.sort(key=lambda x: x["start_date"], reverse=True)
    return out


async def decide(
    session: AsyncSession, *, leave_id: uuid.UUID, approve: bool, actor_id: uuid.UUID,
    branch_id: uuid.UUID, note: str | None = None, ip: str | None = None,
) -> dict:
    leave = await teacher_repository.get_leave_by_id(session, leave_id)
    if leave is None or leave.branch_id != branch_id:
        raise HTTPException(status_code=404, detail="Leave request not found")
    if leave.approval_status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"This request is already {leave.approval_status}.",
        )
    leave.approval_status = "approved" if approve else "rejected"
    leave.decided_by = actor_id
    leave.decided_at = datetime.now(timezone.utc)
    leave.decision_note = note
    await session.flush()
    await audit_service.log_action(
        session, user_id=actor_id, action="UPDATE", table_name="teacher_leaves",
        record_id=leave.id, new_values={"approval_status": leave.approval_status}, ip_address=ip,
        branch_id=branch_id,
    )
    return _row(leave)
