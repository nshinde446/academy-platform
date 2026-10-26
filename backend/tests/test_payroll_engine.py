"""Payroll — Slice 2 calculation engine + ledger.

Every worked example in the spec §3 and every row of its "More cases" table is a
test here (the spec says those examples *are* the automated test cases). Covers
the pure month computation, the carry-forward ledger (extra / compensation / cap
trim), the never-negative balance rule, and recompute-with-reversal after a past
attendance correction (§12).
"""

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.attendance.models.attendance_models import (
    LateFineSlab,
    StaffDailyAttendance,
)
from app.modules.attendance.services.daily_service import branch_timezone
from app.modules.attendance.time_utils import local_time_on
from app.modules.payroll.models.payroll_models import (
    CarryForwardLedger,
    ExtraDayRequest,
    PayrollMonthHoliday,
    PayrollMonthSettings,
    PayrollStaffMonth,
)
from app.modules.payroll.services import (
    calc_service,
    ledger_service,
    payroll_service,
)
from app.modules.staff.models.staff_models import Department, Staff

BRANCH = uuid.UUID("00000000-0000-0000-0000-000000000001")
USER = uuid.UUID("00000000-0000-0000-0000-000000000100")


# ── fixtures / helpers ───────────────────────────────────────────────────────

async def _staff(db: AsyncSession, emp_code: str = "91000") -> Staff:
    dept = Department(
        branch_id=BRANCH, name="MSA-Teachers", id_range_start=91000, id_range_end=91999
    )
    db.add(dept)
    await db.flush()
    s = Staff(
        branch_id=BRANCH, emp_code=emp_code, first_name="Asha", last_name="Rao",
        department_id=dept.id,
    )
    db.add(s)
    await db.flush()
    return s


async def _month(db: AsyncSession, year: int, month: int, required: float = 26) -> None:
    db.add(PayrollMonthSettings(
        branch_id=BRANCH, year=year, month=month, required_days=required,
        lifecycle="OPEN",
    ))
    await db.flush()


async def _attendance(
    db: AsyncSession, staff: Staff, year: int, month: int,
    *, full: int = 0, half: int = 0,
) -> None:
    """Lay down ``full`` PRESENT days and ``half`` HALF_DAY days on consecutive
    dates from the 1st. (Weekly-offs/holidays are irrelevant to the day count —
    only worked days credit.)"""
    day = 1
    for _ in range(full):
        db.add(StaffDailyAttendance(
            branch_id=BRANCH, staff_id=staff.id, attendance_date=date(year, month, day),
            day_status="PRESENT", signoff="COMPLETE", source="BIOMETRIC",
        ))
        day += 1
    for _ in range(half):
        db.add(StaffDailyAttendance(
            branch_id=BRANCH, staff_id=staff.id, attendance_date=date(year, month, day),
            day_status="HALF_DAY", signoff="COMPLETE", source="BIOMETRIC",
        ))
        day += 1
    await db.flush()


async def _compute(db, staff, year, month, *, balance_in, cap=5, holiday_treatment="credited"):
    return await calc_service.compute_month(
        db, staff=staff, branch_id=BRANCH, year=year, month=month,
        balance_in=balance_in, cap=cap, holiday_treatment=holiday_treatment,
    )


# ── pure computation: More cases table ───────────────────────────────────────

async def test_no_change_net_zero(db_session, seed_data):
    """§3 Example 3: required 26, worked 26 → net 0, no movement."""
    s = await _staff(db_session)
    await _month(db_session, 2026, 1, 26)
    await _attendance(db_session, s, 2026, 1, full=26)
    comp = await _compute(db_session, s, 2026, 1, balance_in=0)
    assert comp.credited_days == 26
    assert comp.net_days == 0
    assert comp.added == 0 and comp.balance_used == 0 and comp.uncovered_days == 0


async def test_half_days(db_session, seed_data):
    """More cases: 25 full + 2 half, required 26 → credited 26, net 0."""
    s = await _staff(db_session)
    await _month(db_session, 2026, 1, 26)
    await _attendance(db_session, s, 2026, 1, full=25, half=2)
    comp = await _compute(db_session, s, 2026, 1, balance_in=0)
    assert comp.present_days == 26.0
    assert comp.half_days == 2
    assert comp.credited_days == 26.0
    assert comp.net_days == 0.0


async def test_paid_holidays_credit(db_session, seed_data):
    """More cases: present 24, 2 paid holidays declared, required 26 → credited
    26, net 0."""
    s = await _staff(db_session)
    await _month(db_session, 2026, 1, 26)
    await _attendance(db_session, s, 2026, 1, full=24)
    # Two declared holidays on dates the staff did NOT work (later in the month).
    for d in (27, 28):
        db_session.add(PayrollMonthHoliday(
            branch_id=BRANCH, year=2026, month=1,
            holiday_date=date(2026, 1, d), title="Festival", kind="HOLIDAY",
        ))
    await db_session.flush()
    comp = await _compute(db_session, s, 2026, 1, balance_in=0)
    assert comp.present_days == 24.0
    assert comp.paid_leave_days == 2.0
    assert comp.credited_days == 26.0
    assert comp.net_days == 0.0


async def test_holiday_on_worked_day_counted_once(db_session, seed_data):
    """§12: a paid holiday on a day the staff actually worked is counted once —
    the worked credit stands, the holiday adds nothing."""
    s = await _staff(db_session)
    await _month(db_session, 2026, 1, 26)
    await _attendance(db_session, s, 2026, 1, full=26)  # worked the 1st..26th
    db_session.add(PayrollMonthHoliday(
        branch_id=BRANCH, year=2026, month=1,
        holiday_date=date(2026, 1, 5), title="Festival", kind="HOLIDAY",
    ))
    await db_session.flush()
    comp = await _compute(db_session, s, 2026, 1, balance_in=0)
    assert comp.paid_leave_days == 0.0
    assert comp.credited_days == 26.0


async def test_partial_cover(db_session, seed_data):
    """More cases: balance 2, shortfall 3 → used 2, uncovered 1."""
    s = await _staff(db_session)
    await _month(db_session, 2026, 1, 26)
    await _attendance(db_session, s, 2026, 1, full=23)  # net -3
    comp = await _compute(db_session, s, 2026, 1, balance_in=2)
    assert comp.net_days == -3
    assert comp.balance_used == 2
    assert comp.uncovered_days == 1
    assert comp.balance_out == 0


async def test_cap_trim(db_session, seed_data):
    """More cases: cap 5, balance 3, extra 4 → only 2 added, 2 trimmed."""
    s = await _staff(db_session)
    await _month(db_session, 2026, 1, 26)
    await _attendance(db_session, s, 2026, 1, full=30)  # net +4
    comp = await _compute(db_session, s, 2026, 1, balance_in=3, cap=5)
    assert comp.extra_days == 4
    assert comp.added == 2
    assert comp.trimmed == 2
    assert comp.balance_out == 5
    # A cap_trim ledger row is written alongside extra_added.
    await ledger_service.apply_computation(db_session, comp, branch_id=BRANCH, user_id=USER)
    rows = await ledger_service.month_entries(db_session, s.id, 2026, 1)
    kinds = {r.entry_type: float(r.days) for r in rows}
    assert kinds["extra_added"] == 2
    assert kinds["cap_trim"] == 2
    assert float(rows[-1].running_balance) == 5 or float(rows[0].running_balance) == 5


async def test_balance_never_negative(db_session, seed_data):
    """Shortfall with no balance → balance stays 0, the rest is uncovered."""
    s = await _staff(db_session)
    await _month(db_session, 2026, 1, 26)
    await _attendance(db_session, s, 2026, 1, full=24)  # net -2
    comp = await _compute(db_session, s, 2026, 1, balance_in=0)
    assert comp.balance_out == 0
    assert comp.uncovered_days == 2


# ── late fine total reuses the shared slab logic (§7) ────────────────────────

async def test_late_fine_total_sums_existing_fines(db_session, seed_data):
    """The monthly late-fine total is the sum of the existing daily fines, via the
    same slab functions the Staff Late Fine Report uses."""
    s = await _staff(db_session)
    s.shift_start = "08:00"
    await _month(db_session, 2026, 1, 26)
    for slab in (
        LateFineSlab(min_minutes=1, max_minutes=5, fine_amount=200, color_hex="#BDD7EE", label="1-5"),
        LateFineSlab(min_minutes=6, max_minutes=10, fine_amount=500, color_hex="#FFE699", label="6-10"),
        LateFineSlab(min_minutes=11, max_minutes=None, fine_amount=1000, color_hex="#F4B084", label="11+"),
    ):
        db_session.add(slab)
    await db_session.flush()

    tz = await branch_timezone(db_session, BRANCH)
    # Two days ~20 min late (top band) plus one on-time day.
    for d, late in ((1, True), (2, True), (3, False)):
        hh, mm = (8, 20) if late else (7, 55)
        db_session.add(StaffDailyAttendance(
            branch_id=BRANCH, staff_id=s.id, attendance_date=date(2026, 1, d),
            day_status="PRESENT", signoff="COMPLETE", source="BIOMETRIC",
            first_in=local_time_on(date(2026, 1, d), tz, hh, mm),
        ))
    await db_session.flush()
    comp = await _compute(db_session, s, 2026, 1, balance_in=0)
    assert comp.late_fine_total == 2000.0  # two late days in the 11+ band


# ── ledger integration: Example 1 (carry-forward then compensation) ──────────

async def test_example1_carry_then_compensate(db_session, seed_data):
    s = await _staff(db_session)
    await _month(db_session, 2026, 1, 26)
    await _month(db_session, 2026, 2, 26)
    await _attendance(db_session, s, 2026, 1, full=27)  # +1
    await _attendance(db_session, s, 2026, 2, full=25)  # -1

    m1 = await payroll_service.close_month(db_session, branch_id=BRANCH, year=2026, month=1, user_id=USER)
    assert float(m1[0].extra_days) == 1
    assert float(m1[0].balance_out) == 1
    assert await ledger_service.current_balance(db_session, s.id) == 1

    m2 = await payroll_service.close_month(db_session, branch_id=BRANCH, year=2026, month=2, user_id=USER)
    assert float(m2[0].balance_in) == 1
    assert float(m2[0].balance_out) == 0
    assert float(m2[0].uncovered_days) == 0
    # Ledger: +1 then -1.
    rows = (await db_session.execute(
        select(CarryForwardLedger).where(CarryForwardLedger.staff_id == s.id)
        .order_by(CarryForwardLedger.seq)
    )).scalars().all()
    assert [r.entry_type for r in rows] == ["extra_added", "compensation_used"]
    assert [float(r.running_balance) for r in rows] == [1, 0]


async def test_close_is_idempotent(db_session, seed_data):
    """§12 double-click: closing an already-CLOSED month writes no extra ledger
    rows."""
    s = await _staff(db_session)
    await _month(db_session, 2026, 1, 26)
    await _attendance(db_session, s, 2026, 1, full=27)
    await payroll_service.close_month(db_session, branch_id=BRANCH, year=2026, month=1, user_id=USER)
    await payroll_service.close_month(db_session, branch_id=BRANCH, year=2026, month=1, user_id=USER)
    rows = await ledger_service.month_entries(db_session, s.id, 2026, 1)
    assert len(rows) == 1  # a single extra_added, not two


# ── Example 2: shortfall made up through an approved request ──────────────────

async def test_example2_makeup_request(db_session, seed_data):
    s = await _staff(db_session)
    await _month(db_session, 2026, 1, 26)
    await _month(db_session, 2026, 2, 26)
    await _attendance(db_session, s, 2026, 1, full=25)  # shortfall 1, no balance

    m1 = await payroll_service.close_month(db_session, branch_id=BRANCH, year=2026, month=1, user_id=USER)
    assert float(m1[0].uncovered_days) == 1
    assert float(m1[0].balance_out) == 0

    # HR raises + Super Admin approves a 1-day make-up targeting month 2.
    db_session.add(ExtraDayRequest(
        branch_id=BRANCH, staff_id=s.id, source_year=2026, source_month=1,
        target_year=2026, target_month=2, shortfall_days=1,
        request_status="APPROVED", requested_by=USER, decided_by=USER,
    ))
    await db_session.flush()

    # Month 2: effective required becomes 27; working 27 → net 0.
    await _attendance(db_session, s, 2026, 2, full=27)
    comp = await calc_service.compute_month(
        db_session, staff=s, branch_id=BRANCH, year=2026, month=2,
        balance_in=0, cap=5,
    )
    assert comp.makeup_days == 1
    assert comp.effective_required == 27
    assert comp.credited_days == 27
    assert comp.net_days == 0


# ── Example / §12: corrected punch later → recompute with reversal ───────────

async def test_corrected_punch_recomputes_forward(db_session, seed_data):
    s = await _staff(db_session)
    await _month(db_session, 2026, 1, 26)
    await _month(db_session, 2026, 2, 26)
    await _attendance(db_session, s, 2026, 1, full=27)  # +1
    await _attendance(db_session, s, 2026, 2, full=26)  # net 0

    await payroll_service.close_month(db_session, branch_id=BRANCH, year=2026, month=1, user_id=USER)
    await payroll_service.close_month(db_session, branch_id=BRANCH, year=2026, month=2, user_id=USER)
    assert await ledger_service.current_balance(db_session, s.id) == 1

    # Correction: two of month 1's PRESENT days turn out to be absences
    # (worked 25, not 27). Soft-delete them.
    rows = (await db_session.execute(
        select(StaffDailyAttendance).where(
            StaffDailyAttendance.staff_id == s.id,
            StaffDailyAttendance.attendance_date >= date(2026, 1, 1),
            StaffDailyAttendance.attendance_date < date(2026, 2, 1),
        ).order_by(StaffDailyAttendance.attendance_date.desc()).limit(2)
    )).scalars().all()
    for r in rows:
        r.is_deleted = True
    await db_session.flush()

    await payroll_service.recompute_from(db_session, branch_id=BRANCH, year=2026, month=1, user_id=USER)

    # Month 1 now net -1 with no balance → uncovered 1, balance 0.
    m1 = (await db_session.execute(
        select(PayrollStaffMonth).where(
            PayrollStaffMonth.staff_id == s.id, PayrollStaffMonth.month == 1
        )
    )).scalar_one()
    assert float(m1.net_days) == -1
    assert float(m1.uncovered_days) == 1
    assert float(m1.balance_out) == 0
    # Final balance after reprocessing both months is 0 (month 2 net 0).
    assert await ledger_service.current_balance(db_session, s.id) == 0
    # A reversal row exists (append-only correction).
    kinds = {
        r.entry_type for r in (await db_session.execute(
            select(CarryForwardLedger).where(CarryForwardLedger.staff_id == s.id)
        )).scalars().all()
    }
    assert "reversal" in kinds
