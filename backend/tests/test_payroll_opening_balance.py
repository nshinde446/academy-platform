"""Payroll — client Point 1: Extra Days (off-day balance).

Covers the off-day balance model the client asked for on top of the carry-forward
engine: uncapped accrual, a balance that can go negative and carry forward, and
the opening-balance seeding (service + API) used to load pre-system history
before the first month. Also asserts the report's Opening / change / Closing
(``balance_change``) figures.
"""

import io
import uuid
from datetime import date

from openpyxl import Workbook
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.attendance.models.attendance_models import StaffDailyAttendance
from app.modules.payroll.models.payroll_models import (
    CarryForwardLedger,
    PayrollMonthSettings,
)
from app.modules.payroll.services import (
    config_service,
    ledger_service,
    opening_balance_service,
    payroll_service,
    report_service,
)
from app.modules.staff.models.staff_models import Department, Staff

BRANCH = "00000000-0000-0000-0000-000000000001"
BR = uuid.UUID(BRANCH)
USER = uuid.UUID("00000000-0000-0000-0000-000000000100")


# ── helpers ──────────────────────────────────────────────────────────────────

async def _staff(db: AsyncSession, emp_code: str = "91000") -> Staff:
    dept = (await db.execute(
        select(Department).where(Department.branch_id == BR)
    )).scalars().first()
    if dept is None:
        dept = Department(branch_id=BR, name="MSA", id_range_start=91000, id_range_end=91999)
        db.add(dept)
        await db.flush()
    s = Staff(branch_id=BR, emp_code=emp_code, first_name="Asha", last_name="Rao",
              department_id=dept.id)
    db.add(s)
    await db.flush()
    return s


async def _month(db: AsyncSession, year: int, month: int, required: float) -> None:
    db.add(PayrollMonthSettings(
        branch_id=BR, year=year, month=month, required_days=required, lifecycle="OPEN",
    ))
    await db.flush()


async def _present(db: AsyncSession, staff: Staff, year: int, month: int, n: int) -> None:
    for d in range(1, n + 1):
        db.add(StaffDailyAttendance(
            branch_id=BR, staff_id=staff.id, attendance_date=date(year, month, d),
            day_status="PRESENT", signoff="COMPLETE", source="BIOMETRIC",
        ))
    await db.flush()


async def _off_day_config(db: AsyncSession) -> None:
    """The client Point 1 model: uncapped balance that may go negative."""
    await config_service.set_values(
        db, {"carry_forward_cap": 0, "allow_negative_balance": True}, user_id=USER
    )
    await db.flush()


# ── uncapped accrual: the client's worked example ────────────────────────────

async def test_uncapped_accrual_carries_past_old_cap(db_session, seed_data):
    """Client example: required=24 (so 2 off days worked → +2), then +4 with no
    cap → closing 6 (the old cap of 5 would have trimmed it), then −1 → 5."""
    await _off_day_config(db_session)
    s = await _staff(db_session)
    # Oct: worked 26, required 24 → +2.
    await _month(db_session, 2026, 10, 24)
    await _present(db_session, s, 2026, 10, 26)
    m = await payroll_service.close_month(db_session, branch_id=BR, year=2026, month=10, user_id=USER)
    assert float(m[0].balance_out) == 2

    # Nov: worked 28, required 24 → +4, closing 6 (uncapped).
    await _month(db_session, 2026, 11, 24)
    await _present(db_session, s, 2026, 11, 28)
    m = await payroll_service.close_month(db_session, branch_id=BR, year=2026, month=11, user_id=USER)
    assert float(m[0].balance_in) == 2
    assert float(m[0].balance_out) == 6  # not trimmed to 5
    assert await ledger_service.current_balance(db_session, s.id) == 6

    # Dec: worked 23, required 24 → −1, closing 5.
    await _month(db_session, 2026, 12, 24)
    await _present(db_session, s, 2026, 12, 23)
    m = await payroll_service.close_month(db_session, branch_id=BR, year=2026, month=12, user_id=USER)
    assert float(m[0].balance_out) == 5
    assert float(m[0].uncovered_days) == 0


# ── negative balance carries forward through the ledger ──────────────────────

async def test_negative_balance_carries_forward(db_session, seed_data):
    await _off_day_config(db_session)
    s = await _staff(db_session)
    # Month 1: worked 22, required 24, no opening → −2 (balance goes negative).
    await _month(db_session, 2026, 1, 24)
    await _present(db_session, s, 2026, 1, 22)
    m1 = await payroll_service.close_month(db_session, branch_id=BR, year=2026, month=1, user_id=USER)
    assert float(m1[0].balance_out) == -2
    assert float(m1[0].uncovered_days) == 0
    # The ledger actually lands on −2 so it carries forward (the latent bug fix).
    assert await ledger_service.current_balance(db_session, s.id) == -2

    # Month 2: worked 25, required 24 → +1, so −2 + 1 = −1.
    await _month(db_session, 2026, 2, 24)
    await _present(db_session, s, 2026, 2, 25)
    m2 = await payroll_service.close_month(db_session, branch_id=BR, year=2026, month=2, user_id=USER)
    assert float(m2[0].balance_in) == -2
    assert float(m2[0].balance_out) == -1


# ── opening balance seeding ──────────────────────────────────────────────────

async def test_set_opening_balance_carries_into_first_month(db_session, seed_data):
    await _off_day_config(db_session)
    s = await _staff(db_session)
    # Seed 3 days of pre-system balance before January 2026.
    written = await opening_balance_service.set_opening_balances(
        db_session, branch_id=BR, effective_year=2026, effective_month=1,
        entries=[(s.id, 3.0)], user_id=USER,
    )
    assert written == 1
    # January carries in the opening 3; worked 24/required 24 → net 0 → still 3.
    bal_in = await ledger_service.balance_before(db_session, s.id, 2026, 1)
    assert bal_in == 3.0
    await _month(db_session, 2026, 1, 24)
    await _present(db_session, s, 2026, 1, 24)
    m = await payroll_service.close_month(db_session, branch_id=BR, year=2026, month=1, user_id=USER)
    assert float(m[0].balance_in) == 3
    assert float(m[0].balance_out) == 3
    # The seed is a single opening_balance ledger row.
    rows = (await db_session.execute(
        select(CarryForwardLedger).where(CarryForwardLedger.staff_id == s.id)
        .order_by(CarryForwardLedger.seq)
    )).scalars().all()
    assert rows[0].entry_type == "opening_balance"
    assert float(rows[0].running_balance) == 3


async def test_opening_balance_resetting_is_idempotent(db_session, seed_data):
    await _off_day_config(db_session)
    s = await _staff(db_session)
    await opening_balance_service.set_opening_balances(
        db_session, branch_id=BR, effective_year=2026, effective_month=1,
        entries=[(s.id, 3.0)], user_id=USER,
    )
    # Re-saving the same value writes nothing; a new value appends one adjustment.
    again = await opening_balance_service.set_opening_balances(
        db_session, branch_id=BR, effective_year=2026, effective_month=1,
        entries=[(s.id, 3.0)], user_id=USER,
    )
    assert again == 0
    changed = await opening_balance_service.set_opening_balances(
        db_session, branch_id=BR, effective_year=2026, effective_month=1,
        entries=[(s.id, 5.0)], user_id=USER,
    )
    assert changed == 1
    assert await ledger_service.balance_before(db_session, s.id, 2026, 1) == 5.0


async def test_opening_balance_blocked_after_month_closed(db_session, seed_data):
    from fastapi import HTTPException

    await _off_day_config(db_session)
    s = await _staff(db_session)
    await _month(db_session, 2026, 1, 24)
    await _present(db_session, s, 2026, 1, 24)
    await payroll_service.close_month(db_session, branch_id=BR, year=2026, month=1, user_id=USER)
    try:
        await opening_balance_service.set_opening_balances(
            db_session, branch_id=BR, effective_year=2026, effective_month=2,
            entries=[(s.id, 3.0)], user_id=USER,
        )
        assert False, "expected refusal once a month is finalised"
    except HTTPException as e:
        assert e.status_code == 409


# ── report Opening / change / Closing ────────────────────────────────────────

async def test_report_exposes_balance_change(db_session, seed_data):
    await _off_day_config(db_session)
    s = await _staff(db_session)
    await opening_balance_service.set_opening_balances(
        db_session, branch_id=BR, effective_year=2026, effective_month=1,
        entries=[(s.id, 2.0)], user_id=USER,
    )
    await _month(db_session, 2026, 1, 24)
    await _present(db_session, s, 2026, 1, 26)  # +2
    rep = await report_service.monthly_report(db_session, branch_id=BR, year=2026, month=1)
    row = rep["rows"][0]
    assert row["balance_in"] == 2            # Opening
    assert row["balance_change"] == 2        # This month (+/-)
    assert row["balance_out"] == 4           # Closing


# ── Excel import parsing ─────────────────────────────────────────────────────

async def test_import_parse_matches_and_flags(db_session, seed_data):
    s = await _staff(db_session, emp_code="91000")
    wb = Workbook()
    ws = wb.active
    ws.append(["emp_code", "opening_balance"])
    ws.append(["91000", 4])
    ws.append(["99999", 7])  # no such staff
    buf = io.BytesIO()
    wb.save(buf)
    out = await opening_balance_service.parse_import(
        db_session, branch_id=BR, file_bytes=buf.getvalue()
    )
    assert out["matched"] == [
        {"staff_id": str(s.id), "emp_code": "91000", "name": "Asha Rao", "opening_balance": 4.0}
    ]
    assert out["unmatched"] == ["99999"]
