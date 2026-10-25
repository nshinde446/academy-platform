"""Teacher Login — Slice 4: admin Teacher Accounts management.

Bulk-create (one-time temp passwords, idempotent), reset, unlock, disable/enable,
list — role-gated and audited. The created account can then log in.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models.auth_models import AuthEvent, User
from app.modules.staff.models.staff_models import Department, Staff

BRANCH = uuid.UUID("00000000-0000-0000-0000-000000000001")


async def _admin_cookie(client) -> dict:
    r = await client.post("/api/v1/auth/login", json={"email": "admin@test.com", "password": "Admin123!"})
    return {"access_token": r.cookies["access_token"]}


async def _teacher_staff(db: AsyncSession, emps: list[str]) -> list[Staff]:
    dept = Department(branch_id=BRANCH, name="MSA-Teachers", id_range_start=1, id_range_end=99)
    db.add(dept)
    await db.flush()
    out = []
    for e in emps:
        s = Staff(branch_id=BRANCH, emp_code=e, first_name=f"T{e}", last_name="Rao",
                  department_id=dept.id, shift_start="09:00")
        db.add(s)
        out.append(s)
    await db.flush()
    return out


async def test_bulk_create_issues_temp_passwords_once_and_is_idempotent(
    db_session: AsyncSession, seed_data, client
):
    await _teacher_staff(db_session, ["91200", "91201"])
    await db_session.flush()
    cookie = await _admin_cookie(client)

    r = await client.post(
        "/api/v1/admin/teacher-accounts/bulk-create",
        params={"branch_id": str(BRANCH)}, json={}, cookies=cookie,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["count"] == 2
    temps = {c["employee_code"]: c["temporary_password"] for c in body["created"]}
    assert set(temps) == {"91200", "91201"}
    assert all(len(p) >= 8 for p in temps.values())

    # Accounts exist, linked + must-change.
    users = (await db_session.execute(
        select(User).where(User.username.in_(["91200", "91201"]))
    )).scalars().all()
    assert len(users) == 2 and all(u.must_change_password for u in users)
    # account_created events written.
    ev = (await db_session.execute(
        select(AuthEvent).where(AuthEvent.event == "account_created")
    )).scalars().all()
    assert len(ev) >= 2

    # Re-run: nobody new (idempotent — existing accounts skipped).
    again = await client.post(
        "/api/v1/admin/teacher-accounts/bulk-create",
        params={"branch_id": str(BRANCH)}, json={}, cookies=cookie,
    )
    assert again.json()["count"] == 0

    # The temp password actually works to log in.
    login = await client.post(
        "/api/v1/auth/login", json={"username": "91200", "password": temps["91200"]}
    )
    assert login.status_code == 200
    assert login.json()["must_change_password"] is True


async def test_reset_password_issues_new_temp(db_session: AsyncSession, seed_data, client):
    (s,) = await _teacher_staff(db_session, ["91210"])
    await db_session.flush()
    cookie = await _admin_cookie(client)
    await client.post("/api/v1/admin/teacher-accounts/bulk-create",
                      params={"branch_id": str(BRANCH)}, json={}, cookies=cookie)

    r = await client.post(
        f"/api/v1/admin/teacher-accounts/{s.id}/reset-password", cookies=cookie,
    )
    assert r.status_code == 200
    new_temp = r.json()["temporary_password"]
    assert len(new_temp) >= 8
    # New temp logs in; the user is forced to change again.
    login = await client.post("/api/v1/auth/login", json={"username": "91210", "password": new_temp})
    assert login.status_code == 200 and login.json()["must_change_password"] is True


async def test_disable_blocks_login_then_enable_restores(db_session: AsyncSession, seed_data, client):
    (s,) = await _teacher_staff(db_session, ["91220"])
    await db_session.flush()
    cookie = await _admin_cookie(client)
    created = await client.post("/api/v1/admin/teacher-accounts/bulk-create",
                                params={"branch_id": str(BRANCH)}, json={}, cookies=cookie)
    temp = created.json()["created"][0]["temporary_password"]

    await client.post(f"/api/v1/admin/teacher-accounts/{s.id}/disable", cookies=cookie)
    blocked = await client.post("/api/v1/auth/login", json={"username": "91220", "password": temp})
    assert blocked.status_code == 403  # inactive account

    await client.post(f"/api/v1/admin/teacher-accounts/{s.id}/enable", cookies=cookie)
    ok = await client.post("/api/v1/auth/login", json={"username": "91220", "password": temp})
    assert ok.status_code == 200


async def test_unlock_clears_lock(db_session: AsyncSession, seed_data, client):
    (s,) = await _teacher_staff(db_session, ["91230"])
    await db_session.flush()
    cookie = await _admin_cookie(client)
    await client.post("/api/v1/admin/teacher-accounts/bulk-create",
                      params={"branch_id": str(BRANCH)}, json={}, cookies=cookie)
    # Force a lock directly.
    u = (await db_session.execute(select(User).where(User.username == "91230"))).scalar_one()
    from datetime import datetime, timedelta, timezone
    u.locked_until = datetime.now(timezone.utc) + timedelta(hours=1)
    await db_session.commit()

    r = await client.post(f"/api/v1/admin/teacher-accounts/{s.id}/unlock", cookies=cookie)
    assert r.status_code == 200
    await db_session.refresh(u)
    assert u.locked_until is None and u.failed_attempts == 0


async def test_list_accounts_shows_status(db_session: AsyncSession, seed_data, client):
    await _teacher_staff(db_session, ["91240", "91241"])
    await db_session.flush()
    cookie = await _admin_cookie(client)
    await client.post("/api/v1/admin/teacher-accounts/bulk-create",
                      params={"branch_id": str(BRANCH)}, json={}, cookies=cookie)
    r = await client.get("/api/v1/admin/teacher-accounts", params={"branch_id": str(BRANCH)}, cookies=cookie)
    assert r.status_code == 200
    rows = {row["employee_code"]: row for row in r.json()}
    assert "91240" in rows and rows["91240"]["status"] == "must_change_password"


async def test_non_admin_cannot_manage(db_session: AsyncSession, seed_data, client):
    (s,) = await _teacher_staff(db_session, ["91250"])
    await db_session.flush()
    # A plain teacher token must not reach the admin endpoints (allowlist 403).
    from app.modules.auth.services.token_service import create_access_token
    admin_cookie = await _admin_cookie(client)
    await client.post("/api/v1/admin/teacher-accounts/bulk-create",
                      params={"branch_id": str(BRANCH)}, json={}, cookies=admin_cookie)
    u = (await db_session.execute(select(User).where(User.username == "91250"))).scalar_one()
    teacher_cookie = {"access_token": create_access_token(u.id, ["teacher"], BRANCH)}
    r = await client.get("/api/v1/admin/teacher-accounts", params={"branch_id": str(BRANCH)}, cookies=teacher_cookie)
    assert r.status_code == 403
