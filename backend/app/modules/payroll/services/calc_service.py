"""Payroll month-end calculation (§2) — the pure engine.

For one staff member and one month it reads the existing attendance (Full day =
1, Half day = 0.5), the declared paid holidays/leaves, the approved make-up days
and the existing late fine, and returns the computed figures. It writes nothing
and changes neither attendance nor late fine (§2).

The ledger side-effects (adding extra to the carry-forward balance, consuming it
for a shortfall, cap trimming) live in :mod:`ledger_service`, which calls
:func:`compute_month` with the balance carried in.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.attendance.models.attendance_models import (
    LateFineSlab,
    StaffDailyAttendance,
)
from app.modules.attendance.services import daily_service
from app.modules.attendance.services import staff_late_fine_service as lf
from app.modules.attendance.time_utils import get_tz
from app.modules.payroll.models.payroll_models import (
    ExtraDayRequest,
    PayrollMonthHoliday,
    PayrollMonthSettings,
)
from app.modules.staff.models.staff_models import Staff

# day_status values that count as worked attendance (see StaffDailyAttendance).
_FULL_DAY_STATUSES = ("PRESENT", "LATE")
_HALF_DAY_STATUSES = ("HALF_DAY",)


@dataclass
class MonthComputation:
    """The computed payroll figures for one staff-month, before any ledger write.

    ``balance_in`` is supplied by the caller (the running carry-forward balance
    as of the start of this month). ``balance_out``/``balance_used``/``added``/
    ``trimmed`` describe what *would* happen to the balance; the actual ledger
    rows are written by :mod:`ledger_service`."""

    staff_id: uuid.UUID
    year: int
    month: int
    required_days: float
    makeup_days: float
    effective_required: float
    present_days: float
    half_days: int
    paid_leave_days: float
    credited_days: float
    net_days: float
    balance_in: float
    # Net > 0 branch.
    extra_days: float = 0.0
    added: float = 0.0
    trimmed: float = 0.0
    # Net < 0 branch.
    shortfall_days: float = 0.0
    balance_used: float = 0.0
    uncovered_days: float = 0.0
    balance_out: float = 0.0
    late_fine_total: float = 0.0
    missing_settings: bool = False
    worked_dates: set[date] = field(default_factory=set)


async def _month_settings(
    session: AsyncSession, branch_id: uuid.UUID, year: int, month: int
) -> PayrollMonthSettings | None:
    return (await session.execute(
        select(PayrollMonthSettings).where(
            PayrollMonthSettings.branch_id == branch_id,
            PayrollMonthSettings.year == year,
            PayrollMonthSettings.month == month,
            PayrollMonthSettings.is_deleted == False,  # noqa: E712
        )
    )).scalar_one_or_none()


async def _daily_rows(
    session: AsyncSession, staff_id: uuid.UUID, branch_id: uuid.UUID, year: int, month: int
) -> list[StaffDailyAttendance]:
    lo = date(year, month, 1)
    hi = date(year + (month == 12), (month % 12) + 1, 1)  # first of next month
    return list((await session.execute(
        select(StaffDailyAttendance).where(
            StaffDailyAttendance.staff_id == staff_id,
            StaffDailyAttendance.branch_id == branch_id,
            StaffDailyAttendance.attendance_date >= lo,
            StaffDailyAttendance.attendance_date < hi,
            StaffDailyAttendance.is_deleted == False,  # noqa: E712
        ).order_by(StaffDailyAttendance.attendance_date)
    )).scalars().all())


async def _holidays(
    session: AsyncSession, branch_id: uuid.UUID, year: int, month: int
) -> list[PayrollMonthHoliday]:
    return list((await session.execute(
        select(PayrollMonthHoliday).where(
            PayrollMonthHoliday.branch_id == branch_id,
            PayrollMonthHoliday.year == year,
            PayrollMonthHoliday.month == month,
            PayrollMonthHoliday.is_deleted == False,  # noqa: E712
        )
    )).scalars().all())


async def _approved_makeup(
    session: AsyncSession, staff_id: uuid.UUID, branch_id: uuid.UUID, year: int, month: int
) -> float:
    """Make-up days this month must absorb — the sum of shortfall_days from
    APPROVED extra-day requests whose *target* is this month (§5, Example 2)."""
    rows = (await session.execute(
        select(ExtraDayRequest.shortfall_days).where(
            ExtraDayRequest.staff_id == staff_id,
            ExtraDayRequest.branch_id == branch_id,
            ExtraDayRequest.target_year == year,
            ExtraDayRequest.target_month == month,
            ExtraDayRequest.request_status == "APPROVED",
            ExtraDayRequest.is_deleted == False,  # noqa: E712
        )
    )).scalars().all()
    return float(sum(float(r) for r in rows))


async def _late_fine_total(
    session: AsyncSession,
    staff: Staff,
    rows: list[StaffDailyAttendance],
    branch_id: uuid.UUID,
) -> float:
    """Sum of the existing daily late fines over the month (§7). Reuses the exact
    shared late-fine functions so the number matches the Staff Late Fine Report."""
    slabs = list((await session.execute(
        select(LateFineSlab).where(LateFineSlab.is_deleted == False)  # noqa: E712
        .order_by(LateFineSlab.min_minutes)
    )).scalars().all())
    if not slabs:
        return 0.0
    tz = get_tz(await daily_service.branch_timezone(session, branch_id))
    total = 0.0
    for d in rows:
        in_utc = d.first_in
        if in_utc is None:
            continue
        if in_utc.tzinfo is None:
            in_utc = in_utc.replace(tzinfo=timezone.utc)
        in_local = in_utc.astimezone(tz)
        mins = lf.late_minutes(lf.start_for_day(d.attendance_date, staff), in_local)
        fine, _ = lf.fine_for(mins, slabs)
        total += fine
    return round(total, 2)


def _apply_balance(
    net: float, balance_in: float, cap: float, *, allow_negative: bool
) -> dict[str, float]:
    """The balance arithmetic (§2/§3). Returns the movement for the net result.

    - net > 0 (EXTRA): add to balance up to the cap; the remainder is trimmed.
    - net < 0 (SHORTFALL): the balance covers it first (down to zero, never
      below unless allow_negative); the rest is uncovered.
    - net == 0: nothing moves, no entry (§3 Example 3)."""
    out = {
        "extra": 0.0, "added": 0.0, "trimmed": 0.0,
        "shortfall": 0.0, "balance_used": 0.0, "uncovered": 0.0,
        "balance_out": balance_in,
    }
    if net > 0:
        out["extra"] = net
        room = max(0.0, cap - balance_in)
        added = min(net, room)
        out["added"] = added
        out["trimmed"] = net - added
        out["balance_out"] = balance_in + added
    elif net < 0:
        shortfall = -net
        out["shortfall"] = shortfall
        used = min(balance_in, shortfall)
        out["balance_used"] = used
        out["balance_out"] = balance_in - used
        remaining = shortfall - used
        if allow_negative and remaining > 0:
            out["balance_out"] = balance_in - used - remaining
            out["uncovered"] = 0.0
        else:
            out["uncovered"] = remaining
    return out


async def compute_month(
    session: AsyncSession,
    *,
    staff: Staff,
    branch_id: uuid.UUID,
    year: int,
    month: int,
    balance_in: float,
    cap: float,
    holiday_treatment: str = "credited",
    allow_negative: bool = False,
) -> MonthComputation:
    """The full month-end calculation for one staff member (§2). Pure — no writes."""
    settings = await _month_settings(session, branch_id, year, month)
    required = float(settings.required_days) if settings else 0.0

    rows = await _daily_rows(session, staff.id, branch_id, year, month)
    full = sum(1 for r in rows if r.day_status in _FULL_DAY_STATUSES)
    half = sum(1 for r in rows if r.day_status in _HALF_DAY_STATUSES)
    present_days = full + 0.5 * half
    worked_dates = {
        r.attendance_date
        for r in rows
        if r.day_status in _FULL_DAY_STATUSES + _HALF_DAY_STATUSES
    }

    # Paid leave/holiday credit — deduped by date, and never double-counting a
    # day the staff already worked ("counted once", §12).
    paid_leave_days = 0.0
    if holiday_treatment == "credited":
        seen: set[date] = set()
        for h in await _holidays(session, branch_id, year, month):
            if h.holiday_date in seen or h.holiday_date in worked_dates:
                continue
            seen.add(h.holiday_date)
            paid_leave_days += float(h.credit_days)

    makeup = await _approved_makeup(session, staff.id, branch_id, year, month)
    # "reduce_required" treatment lowers the target instead of crediting days.
    effective_required = required + makeup
    if holiday_treatment == "reduce_required":
        reduce_by = 0.0
        seen2: set[date] = set()
        for h in await _holidays(session, branch_id, year, month):
            if h.holiday_date in seen2:
                continue
            seen2.add(h.holiday_date)
            reduce_by += float(h.credit_days)
        effective_required = max(0.0, effective_required - reduce_by)

    credited = present_days + paid_leave_days
    net = credited - effective_required

    mv = _apply_balance(net, balance_in, cap, allow_negative=allow_negative)
    late_fine_total = await _late_fine_total(session, staff, rows, branch_id)

    return MonthComputation(
        staff_id=staff.id,
        year=year,
        month=month,
        required_days=required,
        makeup_days=makeup,
        effective_required=effective_required,
        present_days=present_days,
        half_days=half,
        paid_leave_days=paid_leave_days,
        credited_days=credited,
        net_days=net,
        balance_in=balance_in,
        extra_days=mv["extra"],
        added=mv["added"],
        trimmed=mv["trimmed"],
        shortfall_days=mv["shortfall"],
        balance_used=mv["balance_used"],
        uncovered_days=mv["uncovered"],
        balance_out=mv["balance_out"],
        late_fine_total=late_fine_total,
        missing_settings=settings is None,
        worked_dates=worked_dates,
    )
