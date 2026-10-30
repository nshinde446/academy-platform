"""Weekly-Off / banked-leave balance (Teacher Portal Changes, WOF accrual).

The balance is **accrual-based**: a seeded opening balance (the client's "WOF
Till Sept 26" list) plus the extra days worked since — for each whole month
after the opening date, ``max(0, present_days − required)`` (required defaults to
24, config ``wof_required_days``). Present = full day 1 + half day 0.5, read from
the existing staff attendance so it matches the staff reports. Read-only; shown
on the teacher's Attendance screen.
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.attendance.models.attendance_models import StaffDailyAttendance
from app.modules.staff.models.staff_models import Staff
from app.modules.teacher.models.teacher_models import TeacherWofOpening
from app.modules.teacher_portal.services import config_service

_PRESENT = ("PRESENT", "LATE")


def _months_after(as_of: date, upto: date) -> list[tuple[int, int]]:
    """Whole months strictly after the opening month, up to and including the
    ``upto`` month. The opening already covers its own month."""
    out: list[tuple[int, int]] = []
    y, m = as_of.year, as_of.month
    # Start at the month after as_of.
    m += 1
    if m > 12:
        y, m = y + 1, 1
    while (y, m) <= (upto.year, upto.month):
        out.append((y, m))
        m += 1
        if m > 12:
            y, m = y + 1, 1
    return out


async def _present_days(
    session: AsyncSession, staff_id: uuid.UUID, branch_id: uuid.UUID, year: int, month: int
) -> float:
    lo = date(year, month, 1)
    hi = date(year + (month == 12), (month % 12) + 1, 1)
    rows = (await session.execute(
        select(StaffDailyAttendance.day_status).where(
            StaffDailyAttendance.staff_id == staff_id,
            StaffDailyAttendance.branch_id == branch_id,
            StaffDailyAttendance.attendance_date >= lo,
            StaffDailyAttendance.attendance_date < hi,
            StaffDailyAttendance.is_deleted == False,  # noqa: E712
        )
    )).scalars().all()
    full = sum(1 for s in rows if s in _PRESENT)
    half = sum(1 for s in rows if s == "HALF_DAY")
    return full + 0.5 * half


async def balance(session: AsyncSession, staff: Staff) -> dict | None:
    """The teacher's live WOF balance, or None when no opening has been seeded
    (WOF not tracked for this teacher yet)."""
    if staff.linked_teacher_id is None:
        return None
    opening = (await session.execute(
        select(TeacherWofOpening).where(
            TeacherWofOpening.teacher_id == staff.linked_teacher_id,
            TeacherWofOpening.is_deleted == False,  # noqa: E712
        )
    )).scalar_one_or_none()
    if opening is None:
        return None

    required = float(await config_service.get_value(session, "wof_required_days") or 24)
    accrued = 0.0
    today = date.today()
    for (y, m) in _months_after(opening.as_of_date, today):
        # Only count a month once it is fully over (don't accrue the running
        # month, where present days are still climbing).
        if (y, m) >= (today.year, today.month):
            continue
        present = await _present_days(session, staff.id, staff.branch_id, y, m)
        accrued += max(0.0, present - required)

    opening_val = float(opening.opening_balance)
    return {
        "opening": opening_val,
        "opening_as_of": opening.as_of_date.isoformat(),
        "accrued": round(accrued, 1),
        "balance": round(opening_val + accrued, 1),
        "required_days": required,
    }
