"""RBAC Phase 2 enforcement: BatchScope on attendance + lectures, the
kill-switch (flag off = inert), coordinator batch scoping, accounts grant
gating, manual-mark Manager-only, and coordinator add rights."""

import uuid
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.modules.auth.models.auth_models import Role, User, UserBranchRole, UserRole
from app.modules.auth.models.access_models import (
    AccountsAttendanceGrant,
    BatchCoordinator,
)
from app.modules.auth.permissions import scope as scope_mod
from app.modules.auth.services.auth_service import hash_password

BRANCH_A = uuid.UUID("00000000-0000-0000-0000-000000000001")
BATCH_A = uuid.UUID("00000000-0000-0000-0000-000000000070")  # "Batch A"
BATCH_B = uuid.UUID("00000000-0000-0000-0000-000000000071")  # "Batch B"
TEACHER_ID = "00000000-0000-0000-0000-000000000060"
CLASSROOM_ID = "00000000-0000-0000-0000-000000000080"
SUBJECT_ID = "00000000-0000-0000-0000-000000000050"


def _enable_enforcement(monkeypatch, on: bool):
    monkeypatch.setattr(
        scope_mod,
        "get_settings",
        lambda: SimpleNamespace(RBAC_ENFORCEMENT_ENABLED=on),
    )


async def _mk_user(db_session, *, email, role_name) -> User:
    role = (
        await db_session.execute(select(Role).where(Role.name == role_name))
    ).scalar_one_or_none()
    if role is None:
        role = Role(
            id=uuid.uuid4(), name=role_name, display_name=role_name,
            status="active", is_deleted=False,
        )
        db_session.add(role)
        await db_session.flush()
    u = User(
        id=uuid.uuid4(), email=email, password_hash=hash_password("Passw0rd!"),
        first_name="R", last_name="B", primary_branch_id=BRANCH_A,
        status="active", is_deleted=False,
    )
    db_session.add(u)
    await db_session.flush()
    db_session.add(UserRole(user_id=u.id, role_id=role.id, status="active", is_deleted=False))
    db_session.add(
        UserBranchRole(
            user_id=u.id, branch_id=BRANCH_A, role_id=role.id,
            status="active", is_deleted=False,
        )
    )
    await db_session.commit()
    return u


async def _login(client, email):
    resp = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": "Passw0rd!"}
    )
    assert resp.status_code == 200, resp.text


async def _login_admin(client):
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.com", "password": "Admin123!"},
    )
    assert resp.status_code == 200


def _matrix_params(batch_id):
    today = date.today()
    return {
        "branch_id": str(BRANCH_A),
        "batch_id": str(batch_id),
        "start": (today - timedelta(days=7)).isoformat(),
        "end": today.isoformat(),
    }


async def _matrix(client, batch_id):
    return await client.get("/api/v1/attendance/daily/matrix", params=_matrix_params(batch_id))


# ── kill-switch: off = inert ─────────────────────────────────────────────────


async def test_flag_off_new_role_denied_manager_ok(client, seed_data, db_session, monkeypatch):
    _enable_enforcement(monkeypatch, False)
    coord = await _mk_user(db_session, email="coord@test.com", role_name="floor_coordinator")
    db_session.add(BatchCoordinator(user_id=coord.id, batch_id=BATCH_A, branch_id=BRANCH_A))
    await db_session.commit()

    # Manager: unrestricted regardless of flag.
    await _login_admin(client)
    assert (await _matrix(client, BATCH_A)).status_code == 200

    # Coordinator: with enforcement OFF the new role has no access yet (inert).
    await _login(client, "coord@test.com")
    assert (await _matrix(client, BATCH_A)).status_code == 403


# ── coordinator batch scoping (flag on) ──────────────────────────────────────


async def test_coordinator_scoped_to_assigned_batches(client, seed_data, db_session, monkeypatch):
    _enable_enforcement(monkeypatch, True)
    coord = await _mk_user(db_session, email="coord2@test.com", role_name="floor_coordinator")
    db_session.add(BatchCoordinator(user_id=coord.id, batch_id=BATCH_A, branch_id=BRANCH_A))
    await db_session.commit()

    await _login(client, "coord2@test.com")
    assert (await _matrix(client, BATCH_A)).status_code == 200   # assigned
    assert (await _matrix(client, BATCH_B)).status_code == 403   # not assigned


# ── accounts grant gating (flag on) ──────────────────────────────────────────


async def test_accounts_attendance_requires_grant(client, seed_data, db_session, monkeypatch):
    _enable_enforcement(monkeypatch, True)
    acct = await _mk_user(db_session, email="acct@test.com", role_name="accounts")
    await db_session.commit()

    await _login(client, "acct@test.com")
    assert (await _matrix(client, BATCH_A)).status_code == 403   # no grant → hidden

    # Grant batch-A attendance → now visible; batch-B still hidden.
    db_session.add(
        AccountsAttendanceGrant(
            user_id=acct.id, branch_id=BRANCH_A, batch_id=BATCH_A,
            expires_at=None, granted_by=acct.id,
        )
    )
    await db_session.commit()
    assert (await _matrix(client, BATCH_A)).status_code == 200
    assert (await _matrix(client, BATCH_B)).status_code == 403


async def test_accounts_expired_grant_denied(client, seed_data, db_session, monkeypatch):
    _enable_enforcement(monkeypatch, True)
    acct = await _mk_user(db_session, email="acct2@test.com", role_name="accounts")
    db_session.add(
        AccountsAttendanceGrant(
            user_id=acct.id, branch_id=BRANCH_A, batch_id=BATCH_A,
            expires_at=datetime.now(timezone.utc) - timedelta(days=1),  # expired
            granted_by=acct.id,
        )
    )
    await db_session.commit()

    await _login(client, "acct2@test.com")
    assert (await _matrix(client, BATCH_A)).status_code == 403


# ── lecture scheduling scope (flag on) ───────────────────────────────────────


async def test_coordinator_schedules_only_assigned_batch(client, seed_data, db_session, monkeypatch):
    _enable_enforcement(monkeypatch, True)
    coord = await _mk_user(db_session, email="coord3@test.com", role_name="floor_coordinator")
    db_session.add(BatchCoordinator(user_id=coord.id, batch_id=BATCH_A, branch_id=BRANCH_A))
    await db_session.commit()

    await _login(client, "coord3@test.com")
    now = datetime.now(timezone.utc)

    def _payload(batch_id):
        return {
            "teacher_id": TEACHER_ID, "batch_id": str(batch_id),
            "classroom_id": CLASSROOM_ID, "subject_id": SUBJECT_ID,
            "scheduled_start": (now + timedelta(hours=2)).isoformat(),
            "scheduled_end": (now + timedelta(hours=3)).isoformat(),
            "delivery_mode": "offline",
        }

    # Unassigned batch → blocked by scope before anything else.
    assert (await client.post("/api/v1/lectures", json=_payload(BATCH_B))).status_code == 403
    # Assigned batch → allowed (passes scope; creates).
    ok = await client.post("/api/v1/lectures", json=_payload(BATCH_A))
    assert ok.status_code == 200, ok.text


# ── manual mark is Manager-only; coordinator add is allowed ──────────────────


async def test_manual_mark_denied_to_coordinator(client, seed_data, db_session, monkeypatch):
    _enable_enforcement(monkeypatch, True)
    await _mk_user(db_session, email="coord4@test.com", role_name="floor_coordinator")
    await db_session.commit()
    await _login(client, "coord4@test.com")
    resp = await client.post(
        "/api/v1/attendance/daily/mark",
        params={"branch_id": str(BRANCH_A)},
        json={"student_id": str(uuid.uuid4()), "day": date.today().isoformat(),
              "attendance_status": "PRESENT"},
    )
    assert resp.status_code == 403


async def test_coordinator_can_add_student(client, seed_data, db_session, monkeypatch):
    _enable_enforcement(monkeypatch, True)
    await _mk_user(db_session, email="coord5@test.com", role_name="floor_coordinator")
    await db_session.commit()
    await _login(client, "coord5@test.com")
    resp = await client.post(
        "/api/v1/students",
        json={
            "branch_id": str(BRANCH_A),
            "first_name": "New", "last_name": "Student",
            "enrollment_number": "RBAC-ADD-1",
        },
    )
    # Add is open to coordinators (only Delete is Manager-only). Accept created
    # or a validation error, but never a 403.
    assert resp.status_code != 403, resp.text


# ── follow-ups: audit-on-denial + branch-summary scoping ─────────────────────


async def test_denied_delete_is_audited(client, seed_data, db_session, monkeypatch):
    _enable_enforcement(monkeypatch, True)
    await _mk_user(db_session, email="coord6@test.com", role_name="floor_coordinator")
    await db_session.commit()

    # Coordinator attempts a permanent delete → 403.
    await _login(client, "coord6@test.com")
    denied = await client.delete(
        f"/api/v1/students/{uuid.uuid4()}", params={"branch_id": str(BRANCH_A)}
    )
    assert denied.status_code == 403

    # The attempt is recorded for the Manager's audit report.
    await _login_admin(client)
    logs = await client.get("/api/v1/audit/logs", params={"action": "Access Denied"})
    assert logs.status_code == 200, logs.text
    items = logs.json()["items"]
    assert any(
        it["action"] == "Access Denied" and it["table_name"] == "students"
        for it in items
    )


async def test_branch_summary_scoped_to_assigned(client, seed_data, db_session, monkeypatch):
    _enable_enforcement(monkeypatch, True)
    coord = await _mk_user(db_session, email="coord7@test.com", role_name="floor_coordinator")
    db_session.add(BatchCoordinator(user_id=coord.id, batch_id=BATCH_A, branch_id=BRANCH_A))
    await db_session.commit()

    today = date.today()
    params = {
        "branch_id": str(BRANCH_A),
        "start": (today - timedelta(days=7)).isoformat(),
        "end": today.isoformat(),
    }

    # Manager sees every active batch (both A and B).
    await _login_admin(client)
    mgr = await client.get("/api/v1/attendance/daily/branch-summary", params=params)
    assert mgr.status_code == 200
    mgr_batches = {r["batch_id"] for r in mgr.json()}
    assert str(BATCH_A) in mgr_batches and str(BATCH_B) in mgr_batches

    # Coordinator sees only their assigned batch.
    await _login(client, "coord7@test.com")
    coord_resp = await client.get("/api/v1/attendance/daily/branch-summary", params=params)
    assert coord_resp.status_code == 200
    coord_batches = {r["batch_id"] for r in coord_resp.json()}
    assert coord_batches == {str(BATCH_A)}


async def test_branch_summary_flag_off_denies_coordinator(client, seed_data, db_session, monkeypatch):
    _enable_enforcement(monkeypatch, False)
    await _mk_user(db_session, email="coord8@test.com", role_name="floor_coordinator")
    await db_session.commit()
    await _login(client, "coord8@test.com")
    today = date.today()
    resp = await client.get(
        "/api/v1/attendance/daily/branch-summary",
        params={
            "branch_id": str(BRANCH_A),
            "start": (today - timedelta(days=7)).isoformat(),
            "end": today.isoformat(),
        },
    )
    assert resp.status_code == 403
