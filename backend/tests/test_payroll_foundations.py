"""Payroll — Slice 1 data foundations (migration 0069).

The six new payroll tables exist and behave, the seeded ``payroll_config``
carries the spec §8 defaults, the carry-forward ledger accepts appends, and the
settings endpoint enforces §9 roles (Super Admin writes; anyone views). The
calculation engine, month lifecycle and request flow arrive in later slices.
"""

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.payroll.models.payroll_models import (
    CarryForwardLedger,
    ExtraDayRequest,
    ExtraDayRequestHistory,
    PayrollMonthHoliday,
    PayrollMonthSettings,
    PayrollStaffMonth,
)
from app.modules.payroll.services import config_service
from app.modules.staff.models.staff_models import Department, Staff

BRANCH = uuid.UUID("00000000-0000-0000-0000-000000000001")


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


# ── config defaults ──────────────────────────────────────────────────────────

async def test_config_defaults_match_spec(db_session: AsyncSession, seed_data):
    """With nothing seeded in-session, get_config falls back to the §8 defaults."""
    cfg = await config_service.get_config(db_session)
    assert cfg["payroll_enabled"] is False
    assert cfg["carry_forward_cap"] == 5
    assert cfg["holiday_treatment"] == "credited"
    assert cfg["unapproved_shortfall"] == "unpaid"
    assert cfg["allow_negative_balance"] is False


async def test_is_enabled_false_by_default(db_session: AsyncSession, seed_data):
    assert await config_service.is_enabled(db_session) is False


async def test_set_values_persists_and_ignores_unknown(db_session: AsyncSession, seed_data):
    cfg = await config_service.set_values(
        db_session,
        {"carry_forward_cap": 7, "bogus_key": 1},
        user_id=seed_data["admin_user"].id,
    )
    assert cfg["carry_forward_cap"] == 7
    assert "bogus_key" not in cfg
    # Re-read to confirm it stuck.
    again = await config_service.get_config(db_session)
    assert again["carry_forward_cap"] == 7


# ── tables exist / behave ────────────────────────────────────────────────────

async def test_month_settings_roundtrip(db_session: AsyncSession, seed_data):
    row = PayrollMonthSettings(
        branch_id=BRANCH, year=2026, month=10, required_days=26, lifecycle="OPEN"
    )
    db_session.add(row)
    await db_session.flush()
    loaded = (await db_session.execute(
        select(PayrollMonthSettings).where(PayrollMonthSettings.id == row.id)
    )).scalar_one()
    assert float(loaded.required_days) == 26.0
    assert loaded.lifecycle == "OPEN"


async def test_holiday_credit_days_default(db_session: AsyncSession, seed_data):
    h = PayrollMonthHoliday(
        branch_id=BRANCH, year=2026, month=10,
        holiday_date=__import__("datetime").date(2026, 10, 2),
        title="Gandhi Jayanti", kind="HOLIDAY",
    )
    db_session.add(h)
    await db_session.flush()
    assert float(h.credit_days) == 1.0


async def test_staff_month_half_day_fraction(db_session: AsyncSession, seed_data):
    s = await _staff(db_session)
    row = PayrollStaffMonth(
        branch_id=BRANCH, staff_id=s.id, year=2026, month=10,
        required_days=26, present_days=25.5, half_days=1, credited_days=25.5,
        net_days=-0.5,
    )
    db_session.add(row)
    await db_session.flush()
    assert float(row.present_days) == 25.5
    assert float(row.net_days) == -0.5


async def test_staff_month_unique_per_staff_month(db_session: AsyncSession, seed_data):
    from sqlalchemy.exc import IntegrityError

    s = await _staff(db_session)
    db_session.add(PayrollStaffMonth(branch_id=BRANCH, staff_id=s.id, year=2026, month=10))
    await db_session.flush()
    db_session.add(PayrollStaffMonth(branch_id=BRANCH, staff_id=s.id, year=2026, month=10))
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_ledger_appends_running_balance(db_session: AsyncSession, seed_data):
    s = await _staff(db_session)
    e1 = CarryForwardLedger(
        branch_id=BRANCH, staff_id=s.id, year=2026, month=10,
        entry_type="extra_added", days=1, running_balance=1,
    )
    e2 = CarryForwardLedger(
        branch_id=BRANCH, staff_id=s.id, year=2026, month=11,
        entry_type="compensation_used", days=-1, running_balance=0,
    )
    db_session.add_all([e1, e2])
    await db_session.flush()
    rows = (await db_session.execute(
        select(CarryForwardLedger)
        .where(CarryForwardLedger.staff_id == s.id)
        .order_by(CarryForwardLedger.month)
    )).scalars().all()
    assert [e.entry_type for e in rows] == ["extra_added", "compensation_used"]
    assert float(rows[-1].running_balance) == 0.0


async def test_request_history_appendable(db_session: AsyncSession, seed_data):
    s = await _staff(db_session)
    req = ExtraDayRequest(
        branch_id=BRANCH, staff_id=s.id, source_year=2026, source_month=10,
        target_year=2026, target_month=11, shortfall_days=1,
        request_status="PENDING", requested_by=seed_data["admin_user"].id,
    )
    db_session.add(req)
    await db_session.flush()
    hist = ExtraDayRequestHistory(
        request_id=req.id, from_status=None, to_status="PENDING",
        changed_by=seed_data["admin_user"].id, note="raised",
    )
    db_session.add(hist)
    await db_session.flush()
    assert hist.to_status == "PENDING"


async def test_one_active_request_per_source_month(db_session: AsyncSession, seed_data):
    """The partial unique index allows only one PENDING/APPROVED request per
    staff per source month."""
    from sqlalchemy.exc import IntegrityError

    s = await _staff(db_session)
    common = dict(
        branch_id=BRANCH, staff_id=s.id, source_year=2026, source_month=10,
        target_year=2026, target_month=11, shortfall_days=1,
        requested_by=seed_data["admin_user"].id,
    )
    db_session.add(ExtraDayRequest(request_status="PENDING", **common))
    await db_session.flush()
    db_session.add(ExtraDayRequest(request_status="APPROVED", **common))
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_closed_request_frees_the_slot(db_session: AsyncSession, seed_data):
    """A REJECTED/CANCELLED request is outside the partial index, so a fresh
    request for the same source month is allowed."""
    s = await _staff(db_session)
    common = dict(
        branch_id=BRANCH, staff_id=s.id, source_year=2026, source_month=10,
        target_year=2026, target_month=11, shortfall_days=1,
        requested_by=seed_data["admin_user"].id,
    )
    db_session.add(ExtraDayRequest(request_status="REJECTED", **common))
    await db_session.flush()
    db_session.add(ExtraDayRequest(request_status="PENDING", **common))
    await db_session.flush()  # must not raise


# ── settings endpoint RBAC (§9) ──────────────────────────────────────────────

async def _token(client, email: str, password: str) -> str:
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return resp.cookies["access_token"]


@pytest.mark.usefixtures("seed_data")
async def test_get_config_any_authenticated_user(client):
    token = await _token(client, "teacher@test.com", "Teacher123!")
    resp = await client.get("/api/v1/payroll/config", cookies={"access_token": token})
    assert resp.status_code == 200
    assert resp.json()["payroll_enabled"] is False


async def test_get_config_unauthenticated_401(client):
    resp = await client.get("/api/v1/payroll/config")
    assert resp.status_code == 401


@pytest.mark.usefixtures("seed_data")
async def test_update_config_requires_super_admin(client):
    token = await _token(client, "teacher@test.com", "Teacher123!")
    resp = await client.put(
        "/api/v1/payroll/config",
        json={"carry_forward_cap": 9},
        cookies={"access_token": token},
    )
    assert resp.status_code == 403


@pytest.mark.usefixtures("seed_data")
async def test_update_config_super_admin_persists_and_audits(client, db_session):
    from app.modules.audit.models.audit_models import AuditLog

    token = await _token(client, "admin@test.com", "Admin123!")
    resp = await client.put(
        "/api/v1/payroll/config",
        json={"carry_forward_cap": 8, "payroll_enabled": True},
        cookies={"access_token": token},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["carry_forward_cap"] == 8
    assert body["payroll_enabled"] is True
    # A before/after audit row was written.
    rows = (await db_session.execute(
        select(AuditLog).where(AuditLog.table_name == "payroll_config")
    )).scalars().all()
    assert len(rows) >= 1
