"""Teacher Login — Slice 3: login by employee code, lockout, forced change.

Login accepts a username (employee code) or email; failures are generic and
logged; repeated failures lock the account; the first-login forced password
change clears the flag, enforces the policy, and ends other sessions.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models.auth_models import AuthEvent, TeacherPortalConfig, User
from app.modules.auth.services.auth_service import hash_password
from app.modules.staff.models.staff_models import Department, Staff

BRANCH = uuid.UUID("00000000-0000-0000-0000-000000000001")


async def _teacher_user(db: AsyncSession, emp: str, password: str, must_change=True) -> User:
    dept = (await db.execute(
        select(Department).where(Department.branch_id == BRANCH, Department.name == "MSA-Teachers")
    )).scalar_one_or_none()
    if dept is None:
        dept = Department(branch_id=BRANCH, name="MSA-Teachers", id_range_start=1, id_range_end=99)
        db.add(dept)
        await db.flush()
    s = Staff(branch_id=BRANCH, emp_code=emp, first_name="Asha", last_name="Rao",
              department_id=dept.id, shift_start="09:00")
    db.add(s)
    await db.flush()
    u = User(
        email=f"{emp}@teacher.local", password_hash=hash_password(password),
        first_name="Asha", last_name="Rao", username=emp, staff_id=s.id,
        primary_branch_id=BRANCH, must_change_password=must_change,
    )
    db.add(u)
    await db.flush()
    return u


async def test_login_by_employee_code(db_session: AsyncSession, seed_data, client):
    await _teacher_user(db_session, "91100", "TempPass9")
    r = await client.post("/api/v1/auth/login", json={"username": "91100", "password": "TempPass9"})
    assert r.status_code == 200
    assert r.json()["must_change_password"] is True
    assert "access_token" in r.cookies
    events = (await db_session.execute(
        select(AuthEvent).where(AuthEvent.event == "login_success")
    )).scalars().all()
    assert any(e.username_attempted == "91100" for e in events)


async def test_login_case_insensitive_username(db_session: AsyncSession, seed_data, client):
    await _teacher_user(db_session, "ABC12", "TempPass9")
    r = await client.post("/api/v1/auth/login", json={"username": "abc12", "password": "TempPass9"})
    assert r.status_code == 200


async def test_login_wrong_password_is_generic_and_logged(db_session: AsyncSession, seed_data, client):
    await _teacher_user(db_session, "91101", "TempPass9")
    r = await client.post("/api/v1/auth/login", json={"username": "91101", "password": "nope"})
    assert r.status_code == 401
    assert r.json()["error"]["message"] == "Invalid credentials"
    fails = (await db_session.execute(
        select(AuthEvent).where(AuthEvent.event == "login_fail")
    )).scalars().all()
    assert any(e.username_attempted == "91101" for e in fails)


async def test_unknown_user_is_generic(db_session: AsyncSession, seed_data, client):
    r = await client.post("/api/v1/auth/login", json={"username": "00000", "password": "x"})
    assert r.status_code == 401
    assert r.json()["error"]["message"] == "Invalid credentials"


async def test_lockout_after_configured_failures(db_session: AsyncSession, seed_data, client):
    # Tighten the lockout to 2 failures for a fast test.
    db_session.add(TeacherPortalConfig(key="lockout_attempts", value=2))
    db_session.add(TeacherPortalConfig(key="lockout_minutes", value=15))
    await _teacher_user(db_session, "91102", "TempPass9")
    await db_session.flush()

    for _ in range(2):
        bad = await client.post("/api/v1/auth/login", json={"username": "91102", "password": "wrong"})
        assert bad.status_code == 401
    # Now locked: even the CORRECT password is rejected (generic).
    good = await client.post("/api/v1/auth/login", json={"username": "91102", "password": "TempPass9"})
    assert good.status_code == 401

    u = (await db_session.execute(select(User).where(User.username == "91102"))).scalar_one()
    await db_session.refresh(u)
    assert u.locked_until is not None
    locked_events = (await db_session.execute(
        select(AuthEvent).where(AuthEvent.event == "locked")
    )).scalars().all()
    assert any(e.username_attempted == "91102" for e in locked_events)


async def test_forced_change_clears_flag_and_allows_portal(db_session: AsyncSession, seed_data, client):
    await _teacher_user(db_session, "91103", "TempPass9", must_change=True)
    # Log in (succeeds) then change the password.
    login = await client.post("/api/v1/auth/login", json={"username": "91103", "password": "TempPass9"})
    token = login.cookies["access_token"]
    # Before change: a data route is blocked by the forced-change gate.
    blocked = await client.get("/api/v1/me/profile", cookies={"access_token": token})
    assert blocked.status_code == 403 and blocked.json()["error"]["message"] == "PASSWORD_CHANGE_REQUIRED"

    changed = await client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "TempPass9", "new_password": "BrandNew99"},
        cookies={"access_token": token},
    )
    assert changed.status_code == 200
    u = (await db_session.execute(select(User).where(User.username == "91103"))).scalar_one()
    await db_session.refresh(u)
    assert u.must_change_password is False
    assert u.password_changed_at is not None
    # A fresh login with the new password now reaches the portal.
    relog = await client.post("/api/v1/auth/login", json={"username": "91103", "password": "BrandNew99"})
    assert relog.json()["must_change_password"] is False
    ok = await client.get("/api/v1/me/profile", cookies={"access_token": relog.cookies["access_token"]})
    assert ok.status_code == 200


async def test_change_password_policy(db_session: AsyncSession, seed_data, client):
    await _teacher_user(db_session, "91104", "TempPass9", must_change=True)
    login = await client.post("/api/v1/auth/login", json={"username": "91104", "password": "TempPass9"})
    token = login.cookies["access_token"]

    # Too short.
    r1 = await client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "TempPass9", "new_password": "short"},
        cookies={"access_token": token},
    )
    assert r1.status_code in (400, 422)
    # Equals the employee code.
    r2 = await client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "TempPass9", "new_password": "91104"},
        cookies={"access_token": token},
    )
    assert r2.status_code in (400, 422)
    # Same as the old password.
    r3 = await client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "TempPass9", "new_password": "TempPass9"},
        cookies={"access_token": token},
    )
    assert r3.status_code == 400


async def test_email_login_still_works(db_session: AsyncSession, seed_data, client):
    # Backward compatibility: the existing email-based login path is unaffected.
    r = await client.post(
        "/api/v1/auth/login", json={"email": "admin@test.com", "password": "Admin123!"}
    )
    assert r.status_code == 200
    assert r.json()["must_change_password"] is False
