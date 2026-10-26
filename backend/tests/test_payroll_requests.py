"""Payroll — Slice 4 extra-day request flow (§5).

A month that closes with an uncovered shortfall can be made up next month through
a request: raised by HR/Accounts/Branch Admin, approved by the Super Admin
(raiser ≠ approver), with full history. On approval the source month is flagged
deferred (not unpaid) and the target month's required days rise.
"""

import uuid
from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.attendance.models.attendance_models import StaffDailyAttendance
from app.modules.auth.models.auth_models import User, UserRole
from app.modules.auth.services.auth_service import hash_password
from app.modules.payroll.models.payroll_models import (
    ExtraDayRequest,
    PayrollStaffMonth,
)
from app.modules.payroll.services import request_service
from app.modules.staff.models.staff_models import Department, Staff

BRANCH = "00000000-0000-0000-0000-000000000001"
ADMIN_ROLE = uuid.UUID("00000000-0000-0000-0000-000000000010")


async def _staff(db: AsyncSession, *, full: int, year: int, month: int) -> Staff:
    dept = Department(branch_id=uuid.UUID(BRANCH), name="MSA-Teachers",
                      id_range_start=91000, id_range_end=91999)
    db.add(dept)
    await db.flush()
    s = Staff(branch_id=uuid.UUID(BRANCH), emp_code="91000", first_name="Asha",
              last_name="Rao", department_id=dept.id)
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


async def _second_admin(db: AsyncSession) -> User:
    u = User(
        email="admin2@test.com", password_hash=hash_password("Admin123!"),
        first_name="Second", last_name="Admin", status="active", is_deleted=False,
    )
    db.add(u)
    await db.flush()
    db.add(UserRole(user_id=u.id, role_id=ADMIN_ROLE, status="active", is_deleted=False))
    await db.commit()
    return u


async def _token(client, email, password):
    r = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return r.cookies["access_token"]


async def _close_short_month(client, tok, *, year, month, required):
    """Set up + close a month so the single staff has an uncovered shortfall."""
    await client.put(
        f"/api/v1/payroll/months/{year}/{month}?branch_id={BRANCH}",
        json={"required_days": required}, cookies={"access_token": tok},
    )
    await client.post(
        f"/api/v1/payroll/months/{year}/{month}/close?branch_id={BRANCH}",
        json={}, cookies={"access_token": tok},
    )


# ── raise guards ─────────────────────────────────────────────────────────────

async def test_teacher_cannot_raise(client, db_session, seed_data):
    s = await _staff(db_session, full=25, year=2026, month=4)
    admin = await _token(client, "admin@test.com", "Admin123!")
    await _close_short_month(client, admin, year=2026, month=4, required=26)
    teach = await _token(client, "teacher@test.com", "Teacher123!")
    r = await client.post(
        f"/api/v1/payroll/requests?branch_id={BRANCH}",
        json={"staff_id": str(s.id), "source_year": 2026, "source_month": 4, "shortfall_days": 1},
        cookies={"access_token": teach},
    )
    assert r.status_code == 403


async def test_raise_requires_uncovered_shortfall(client, db_session, seed_data):
    s = await _staff(db_session, full=26, year=2026, month=4)  # no shortfall
    admin = await _token(client, "admin@test.com", "Admin123!")
    await _close_short_month(client, admin, year=2026, month=4, required=26)
    r = await client.post(
        f"/api/v1/payroll/requests?branch_id={BRANCH}",
        json={"staff_id": str(s.id), "source_year": 2026, "source_month": 4, "shortfall_days": 1},
        cookies={"access_token": admin},
    )
    assert r.status_code == 422


# ── full approval flow (Example 2) ───────────────────────────────────────────

async def test_approve_defers_source_and_raises_target(client, db_session, seed_data):
    s = await _staff(db_session, full=25, year=2026, month=4)  # shortfall 1
    admin = await _token(client, "admin@test.com", "Admin123!")
    await _close_short_month(client, admin, year=2026, month=4, required=26)

    # Raise (as admin) then approve as a DIFFERENT super admin.
    await _second_admin(db_session)
    admin2 = await _token(client, "admin2@test.com", "Admin123!")

    r = await client.post(
        f"/api/v1/payroll/requests?branch_id={BRANCH}",
        json={"staff_id": str(s.id), "source_year": 2026, "source_month": 4, "shortfall_days": 1},
        cookies={"access_token": admin},
    )
    assert r.status_code == 200
    req_id = r.json()["id"]
    assert r.json()["target_month"] == 5

    ap = await client.post(
        f"/api/v1/payroll/requests/{req_id}/approve?branch_id={BRANCH}",
        json={}, cookies={"access_token": admin2},
    )
    assert ap.status_code == 200
    assert ap.json()["request_status"] == "APPROVED"

    # Source month now shows the day deferred, not uncovered.
    snap = (await db_session.execute(
        select(PayrollStaffMonth).where(
            PayrollStaffMonth.staff_id == s.id, PayrollStaffMonth.month == 4
        )
    )).scalar_one()
    assert float(snap.uncovered_days) == 0
    assert float(snap.deferred_days) == 1

    # Target month's effective required rises by 1 (preview picks up the make-up).
    for d in range(1, 28):
        db_session.add(StaffDailyAttendance(
            branch_id=uuid.UUID(BRANCH), staff_id=s.id,
            attendance_date=date(2026, 5, d), day_status="PRESENT",
            signoff="COMPLETE", source="BIOMETRIC",
        ))
    await db_session.commit()
    await client.put(
        f"/api/v1/payroll/months/2026/5?branch_id={BRANCH}",
        json={"required_days": 26}, cookies={"access_token": admin},
    )
    rep = await client.get(
        f"/api/v1/payroll/report?branch_id={BRANCH}&year=2026&month=5",
        cookies={"access_token": admin},
    )
    row = rep.json()["rows"][0]
    assert row["present_days"] == 27
    assert row["net_days"] == 0  # 27 worked vs 26+1 effective required


async def test_raiser_cannot_approve_own(client, db_session, seed_data):
    s = await _staff(db_session, full=25, year=2026, month=4)
    admin = await _token(client, "admin@test.com", "Admin123!")
    await _close_short_month(client, admin, year=2026, month=4, required=26)
    r = await client.post(
        f"/api/v1/payroll/requests?branch_id={BRANCH}",
        json={"staff_id": str(s.id), "source_year": 2026, "source_month": 4, "shortfall_days": 1},
        cookies={"access_token": admin},
    )
    req_id = r.json()["id"]
    ap = await client.post(
        f"/api/v1/payroll/requests/{req_id}/approve?branch_id={BRANCH}",
        json={}, cookies={"access_token": admin},
    )
    assert ap.status_code == 422


async def test_reject_leaves_unpaid(client, db_session, seed_data):
    s = await _staff(db_session, full=25, year=2026, month=4)
    admin = await _token(client, "admin@test.com", "Admin123!")
    await _close_short_month(client, admin, year=2026, month=4, required=26)
    await _second_admin(db_session)
    admin2 = await _token(client, "admin2@test.com", "Admin123!")

    r = await client.post(
        f"/api/v1/payroll/requests?branch_id={BRANCH}",
        json={"staff_id": str(s.id), "source_year": 2026, "source_month": 4, "shortfall_days": 1},
        cookies={"access_token": admin},
    )
    req_id = r.json()["id"]
    rj = await client.post(
        f"/api/v1/payroll/requests/{req_id}/reject?branch_id={BRANCH}",
        json={"note": "denied"}, cookies={"access_token": admin2},
    )
    assert rj.json()["request_status"] == "REJECTED"
    snap = (await db_session.execute(
        select(PayrollStaffMonth).where(
            PayrollStaffMonth.staff_id == s.id, PayrollStaffMonth.month == 4
        )
    )).scalar_one()
    assert float(snap.uncovered_days) == 1  # still unpaid
    assert float(snap.deferred_days) == 0


async def test_one_active_request_then_cancel_allows_new(client, db_session, seed_data):
    s = await _staff(db_session, full=24, year=2026, month=4)  # shortfall 2
    admin = await _token(client, "admin@test.com", "Admin123!")
    await _close_short_month(client, admin, year=2026, month=4, required=26)
    base = {"staff_id": str(s.id), "source_year": 2026, "source_month": 4, "shortfall_days": 1}

    r1 = await client.post(f"/api/v1/payroll/requests?branch_id={BRANCH}", json=base, cookies={"access_token": admin})
    assert r1.status_code == 200
    # Second active request for the same source month is rejected.
    r2 = await client.post(f"/api/v1/payroll/requests?branch_id={BRANCH}", json=base, cookies={"access_token": admin})
    assert r2.status_code == 409
    # Cancel the first (as its raiser) then a new one is allowed.
    c = await client.post(
        f"/api/v1/payroll/requests/{r1.json()['id']}/cancel?branch_id={BRANCH}",
        json={}, cookies={"access_token": admin},
    )
    assert c.json()["request_status"] == "CANCELLED"
    r3 = await client.post(f"/api/v1/payroll/requests?branch_id={BRANCH}", json=base, cookies={"access_token": admin})
    assert r3.status_code == 200


async def test_history_records_transitions(client, db_session, seed_data):
    s = await _staff(db_session, full=25, year=2026, month=4)
    admin = await _token(client, "admin@test.com", "Admin123!")
    await _close_short_month(client, admin, year=2026, month=4, required=26)
    await _second_admin(db_session)
    admin2 = await _token(client, "admin2@test.com", "Admin123!")
    r = await client.post(
        f"/api/v1/payroll/requests?branch_id={BRANCH}",
        json={"staff_id": str(s.id), "source_year": 2026, "source_month": 4, "shortfall_days": 1},
        cookies={"access_token": admin},
    )
    req_id = r.json()["id"]
    await client.post(
        f"/api/v1/payroll/requests/{req_id}/approve?branch_id={BRANCH}",
        json={"note": "ok"}, cookies={"access_token": admin2},
    )
    h = await client.get(
        f"/api/v1/payroll/requests/{req_id}/history?branch_id={BRANCH}",
        cookies={"access_token": admin},
    )
    statuses = [row["to_status"] for row in h.json()]
    assert statuses == ["PENDING", "APPROVED"]


# ── auto-expire (service unit) ───────────────────────────────────────────────

async def test_expire_covered(db_session, seed_data):
    """An active request whose source month no longer has an uncovered shortfall
    is auto-expired (§5)."""
    s = await _staff(db_session, full=25, year=2026, month=4)
    db_session.add(PayrollStaffMonth(
        branch_id=uuid.UUID(BRANCH), staff_id=s.id, year=2026, month=4,
        uncovered_days=0, deferred_days=0, lifecycle="CLOSED",
    ))
    db_session.add(ExtraDayRequest(
        branch_id=uuid.UUID(BRANCH), staff_id=s.id, source_year=2026, source_month=4,
        target_year=2026, target_month=5, shortfall_days=1,
        request_status="PENDING", requested_by=uuid.uuid4(),
    ))
    await db_session.flush()
    n = await request_service.expire_covered(
        db_session, branch_id=uuid.UUID(BRANCH), year=2026, month=4, user_id=None
    )
    assert n == 1
    req = (await db_session.execute(select(ExtraDayRequest))).scalar_one()
    assert req.request_status == "EXPIRED"
