"""Payroll — Slice 3 month setup, monthly report, staff ledger + RBAC (§7/§9).

Super Admin sets up and closes/locks/reopens a month; the report is a live
preview while OPEN and the frozen snapshot once CLOSED; the ledger shows the
balance trail. Role gates are enforced on every call (§9).
"""

import uuid
from datetime import date

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.attendance.models.attendance_models import StaffDailyAttendance
from app.modules.staff.models.staff_models import Department, Staff

BRANCH = "00000000-0000-0000-0000-000000000001"


async def _seed_staff(db: AsyncSession, *, full: int, year: int, month: int) -> Staff:
    dept = Department(
        branch_id=uuid.UUID(BRANCH), name="MSA-Teachers",
        id_range_start=91000, id_range_end=91999,
    )
    db.add(dept)
    await db.flush()
    s = Staff(
        branch_id=uuid.UUID(BRANCH), emp_code="91000", first_name="Asha",
        last_name="Rao", department_id=dept.id,
    )
    db.add(s)
    await db.flush()
    for d in range(1, full + 1):
        db.add(StaffDailyAttendance(
            branch_id=uuid.UUID(BRANCH), staff_id=s.id,
            attendance_date=date(year, month, d),
            day_status="PRESENT", signoff="COMPLETE", source="BIOMETRIC",
        ))
    await db.commit()
    return s


async def _token(client, email: str, password: str) -> str:
    r = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return r.cookies["access_token"]


def _admin(client):
    return _token(client, "admin@test.com", "Admin123!")


def _teacher(client):
    return _token(client, "teacher@test.com", "Teacher123!")


# ── month setup RBAC ─────────────────────────────────────────────────────────

@pytest.mark.usefixtures("seed_data")
async def test_set_month_requires_super_admin(client):
    tok = await _teacher(client)
    r = await client.put(
        f"/api/v1/payroll/months/2026/3?branch_id={BRANCH}",
        json={"required_days": 26}, cookies={"access_token": tok},
    )
    assert r.status_code == 403


@pytest.mark.usefixtures("seed_data")
async def test_super_admin_sets_and_reads_month(client):
    tok = await _admin(client)
    r = await client.put(
        f"/api/v1/payroll/months/2026/3?branch_id={BRANCH}",
        json={"required_days": 26, "notes": "March"}, cookies={"access_token": tok},
    )
    assert r.status_code == 200
    assert r.json()["lifecycle"] == "OPEN"
    assert r.json()["required_days"] == 26

    r2 = await client.get(
        f"/api/v1/payroll/months/2026/3?branch_id={BRANCH}", cookies={"access_token": tok}
    )
    assert r2.json()["required_days"] == 26


@pytest.mark.usefixtures("seed_data")
async def test_add_and_remove_holiday(client):
    tok = await _admin(client)
    await client.put(
        f"/api/v1/payroll/months/2026/3?branch_id={BRANCH}",
        json={"required_days": 26}, cookies={"access_token": tok},
    )
    r = await client.post(
        f"/api/v1/payroll/months/2026/3/holidays?branch_id={BRANCH}",
        json={"holiday_date": "2026-03-10", "title": "Holi", "kind": "HOLIDAY"},
        cookies={"access_token": tok},
    )
    assert r.status_code == 200
    holidays = r.json()["holidays"]
    assert len(holidays) == 1 and holidays[0]["title"] == "Holi"

    hid = holidays[0]["id"]
    r2 = await client.delete(
        f"/api/v1/payroll/months/2026/3/holidays/{hid}?branch_id={BRANCH}",
        cookies={"access_token": tok},
    )
    assert r2.status_code == 200
    assert r2.json()["holidays"] == []


@pytest.mark.usefixtures("seed_data")
async def test_holiday_date_must_be_in_month(client):
    tok = await _admin(client)
    await client.put(
        f"/api/v1/payroll/months/2026/3?branch_id={BRANCH}",
        json={"required_days": 26}, cookies={"access_token": tok},
    )
    r = await client.post(
        f"/api/v1/payroll/months/2026/3/holidays?branch_id={BRANCH}",
        json={"holiday_date": "2026-04-10", "title": "Wrong"},
        cookies={"access_token": tok},
    )
    assert r.status_code == 422


# ── report ───────────────────────────────────────────────────────────────────

async def test_report_preview_open_month(client, db_session, seed_data):
    await _seed_staff(db_session, full=27, year=2026, month=3)
    tok = await _admin(client)
    await client.put(
        f"/api/v1/payroll/months/2026/3?branch_id={BRANCH}",
        json={"required_days": 26}, cookies={"access_token": tok},
    )
    r = await client.get(
        f"/api/v1/payroll/report?branch_id={BRANCH}&year=2026&month=3",
        cookies={"access_token": tok},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["lifecycle"] == "OPEN"
    row = body["rows"][0]
    assert row["present_days"] == 27
    assert row["net_days"] == 1
    assert row["balance_out"] == 1  # preview reflects the +1 extra
    assert body["totals"]["staff_count"] == 1


async def test_report_requires_role(client, db_session, seed_data):
    await _seed_staff(db_session, full=26, year=2026, month=3)
    tok = await _teacher(client)
    r = await client.get(
        f"/api/v1/payroll/report?branch_id={BRANCH}&year=2026&month=3",
        cookies={"access_token": tok},
    )
    assert r.status_code == 403


# ── close / lock / reopen + ledger ───────────────────────────────────────────

async def test_close_then_report_uses_snapshot_and_ledger(client, db_session, seed_data):
    s = await _seed_staff(db_session, full=27, year=2026, month=3)
    tok = await _admin(client)
    await client.put(
        f"/api/v1/payroll/months/2026/3?branch_id={BRANCH}",
        json={"required_days": 26}, cookies={"access_token": tok},
    )
    r = await client.post(
        f"/api/v1/payroll/months/2026/3/close?branch_id={BRANCH}",
        json={}, cookies={"access_token": tok},
    )
    assert r.status_code == 200
    assert r.json()["lifecycle"] == "CLOSED"

    rep = await client.get(
        f"/api/v1/payroll/report?branch_id={BRANCH}&year=2026&month=3",
        cookies={"access_token": tok},
    )
    assert rep.json()["lifecycle"] == "CLOSED"
    assert rep.json()["rows"][0]["balance_out"] == 1

    led = await client.get(
        f"/api/v1/payroll/staff/{s.id}/ledger?branch_id={BRANCH}",
        cookies={"access_token": tok},
    )
    assert led.status_code == 200
    assert led.json()["current_balance"] == 1
    assert led.json()["rows"][0]["entry_type"] == "extra_added"


async def test_ledger_requires_role(client, db_session, seed_data):
    s = await _seed_staff(db_session, full=26, year=2026, month=3)
    tok = await _teacher(client)
    r = await client.get(
        f"/api/v1/payroll/staff/{s.id}/ledger?branch_id={BRANCH}",
        cookies={"access_token": tok},
    )
    assert r.status_code == 403


async def test_reopen_requires_reason(client, db_session, seed_data):
    await _seed_staff(db_session, full=26, year=2026, month=3)
    tok = await _admin(client)
    await client.put(
        f"/api/v1/payroll/months/2026/3?branch_id={BRANCH}",
        json={"required_days": 26}, cookies={"access_token": tok},
    )
    await client.post(
        f"/api/v1/payroll/months/2026/3/close?branch_id={BRANCH}",
        json={}, cookies={"access_token": tok},
    )
    # No reason → 422.
    r = await client.post(
        f"/api/v1/payroll/months/2026/3/reopen?branch_id={BRANCH}",
        json={}, cookies={"access_token": tok},
    )
    assert r.status_code == 422
    # With reason → OPEN.
    r2 = await client.post(
        f"/api/v1/payroll/months/2026/3/reopen?branch_id={BRANCH}",
        json={"reason": "correction"}, cookies={"access_token": tok},
    )
    assert r2.status_code == 200
    assert r2.json()["lifecycle"] == "OPEN"


async def test_edit_closed_month_needs_reason(client, db_session, seed_data):
    await _seed_staff(db_session, full=26, year=2026, month=3)
    tok = await _admin(client)
    await client.put(
        f"/api/v1/payroll/months/2026/3?branch_id={BRANCH}",
        json={"required_days": 26}, cookies={"access_token": tok},
    )
    await client.post(
        f"/api/v1/payroll/months/2026/3/close?branch_id={BRANCH}",
        json={}, cookies={"access_token": tok},
    )
    # Editing a closed month without a reason is rejected.
    r = await client.put(
        f"/api/v1/payroll/months/2026/3?branch_id={BRANCH}",
        json={"required_days": 25}, cookies={"access_token": tok},
    )
    assert r.status_code == 422
    # With a reason it succeeds and recomputes.
    r2 = await client.put(
        f"/api/v1/payroll/months/2026/3?branch_id={BRANCH}",
        json={"required_days": 25, "reason": "miscount"}, cookies={"access_token": tok},
    )
    assert r2.status_code == 200
    assert r2.json()["required_days"] == 25


async def test_cannot_lock_open_month(client, db_session, seed_data):
    await _seed_staff(db_session, full=26, year=2026, month=3)
    tok = await _admin(client)
    await client.put(
        f"/api/v1/payroll/months/2026/3?branch_id={BRANCH}",
        json={"required_days": 26}, cookies={"access_token": tok},
    )
    r = await client.post(
        f"/api/v1/payroll/months/2026/3/lock?branch_id={BRANCH}",
        json={}, cookies={"access_token": tok},
    )
    assert r.status_code == 422  # must close before lock
