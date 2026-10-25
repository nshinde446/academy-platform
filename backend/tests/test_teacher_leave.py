"""Teacher portal — Slice 8: apply leave (request → approval).

A teacher applies for leave (starts pending → does NOT block scheduling); an
admin approves (now blocks) or rejects. Identity is session-derived so a teacher
only ever files/withdraws their own leave.
"""

import uuid
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models.auth_models import User
from app.modules.auth.services.auth_service import hash_password
from app.modules.auth.services.token_service import create_access_token
from app.modules.staff.models.staff_models import Department, Staff
from app.modules.teacher.models.teacher_models import Teacher
from app.modules.teacher.repositories import teacher_repository

BRANCH = uuid.UUID("00000000-0000-0000-0000-000000000001")


async def _teacher(db: AsyncSession, emp: str) -> tuple[Staff, User, Teacher]:
    dept = (await db.execute(
        select(Department).where(Department.branch_id == BRANCH, Department.name == "MSA-Teachers")
    )).scalar_one_or_none()
    if dept is None:
        dept = Department(branch_id=BRANCH, name="MSA-Teachers", id_range_start=1, id_range_end=99)
        db.add(dept)
        await db.commit()
    t = Teacher(branch_id=BRANCH, first_name="Asha", last_name="Rao")
    db.add(t)
    await db.commit()
    s = Staff(
        branch_id=BRANCH, emp_code=emp, first_name="Asha", last_name="Rao",
        department_id=dept.id, linked_teacher_id=t.id,
    )
    db.add(s)
    await db.commit()
    u = User(
        email=f"{emp}@teacher.local", password_hash=hash_password("x"),
        first_name="Asha", last_name="Rao", username=emp, staff_id=s.id,
        primary_branch_id=BRANCH,
    )
    db.add(u)
    await db.commit()
    return s, u, t


async def _admin(db: AsyncSession, emp: str) -> User:
    u = User(
        email=f"{emp}@admin.local", password_hash=hash_password("x"),
        first_name="Adm", last_name="In", primary_branch_id=BRANCH,
    )
    db.add(u)
    await db.commit()
    return u


def _cookie(user: User, roles) -> dict:
    return {"access_token": create_access_token(user.id, list(roles), BRANCH)}


def _dates(offset_start: int, days: int) -> tuple[str, str]:
    start = date.today() + timedelta(days=offset_start)
    return start.isoformat(), (start + timedelta(days=days)).isoformat()


async def test_apply_creates_pending_not_blocking(db_session, seed_data, client):
    _, u, t = await _teacher(db_session, "98001")
    s_date, e_date = _dates(3, 1)
    r = await client.post(
        "/api/v1/me/leaves", json={"start_date": s_date, "end_date": e_date, "reason": "trip"},
        cookies=_cookie(u, ["teacher_portal"]),
    )
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "pending"
    # A pending leave must NOT block scheduling.
    on = date.fromisoformat(s_date)
    assert await teacher_repository.teacher_on_leave(db_session, t.id, on) is False


async def test_admin_approve_then_blocks(db_session, seed_data, client):
    _, u, t = await _teacher(db_session, "98002")
    admin = await _admin(db_session, "adm2")
    s_date, e_date = _dates(5, 0)
    r = await client.post(
        "/api/v1/me/leaves", json={"start_date": s_date, "end_date": e_date},
        cookies=_cookie(u, ["teacher_portal"]),
    )
    leave_id = r.json()["id"]
    ar = await client.post(
        f"/api/v1/admin/leave-requests/{leave_id}/approve",
        params={"branch_id": str(BRANCH)}, json={"note": "ok"},
        cookies=_cookie(admin, ["branch_admin"]),
    )
    assert ar.status_code == 200, ar.text
    assert ar.json()["status"] == "approved"
    # Now it blocks scheduling for the date.
    assert await teacher_repository.teacher_on_leave(
        db_session, t.id, date.fromisoformat(s_date)
    ) is True


async def test_admin_reject_does_not_block(db_session, seed_data, client):
    _, u, t = await _teacher(db_session, "98003")
    admin = await _admin(db_session, "adm3")
    s_date, e_date = _dates(7, 0)
    r = await client.post(
        "/api/v1/me/leaves", json={"start_date": s_date, "end_date": e_date},
        cookies=_cookie(u, ["teacher_portal"]),
    )
    leave_id = r.json()["id"]
    rr = await client.post(
        f"/api/v1/admin/leave-requests/{leave_id}/reject",
        params={"branch_id": str(BRANCH)}, cookies=_cookie(admin, ["academic_head"]),
    )
    assert rr.status_code == 200, rr.text
    assert rr.json()["status"] == "rejected"
    assert await teacher_repository.teacher_on_leave(
        db_session, t.id, date.fromisoformat(s_date)
    ) is False


async def test_my_leaves_lists_own(db_session, seed_data, client):
    _, u, _ = await _teacher(db_session, "98004")
    s_date, e_date = _dates(2, 0)
    await client.post(
        "/api/v1/me/leaves", json={"start_date": s_date, "end_date": e_date},
        cookies=_cookie(u, ["teacher_portal"]),
    )
    r = await client.get("/api/v1/me/leaves", cookies=_cookie(u, ["teacher_portal"]))
    assert r.status_code == 200
    assert len(r.json()) == 1 and r.json()[0]["status"] == "pending"


async def test_overlap_rejected(db_session, seed_data, client):
    _, u, _ = await _teacher(db_session, "98005")
    s_date, e_date = _dates(4, 3)
    ck = _cookie(u, ["teacher_portal"])
    assert (await client.post("/api/v1/me/leaves", json={"start_date": s_date, "end_date": e_date}, cookies=ck)).status_code == 201
    # Overlapping second request is refused.
    r2 = await client.post(
        "/api/v1/me/leaves",
        json={"start_date": s_date, "end_date": e_date}, cookies=ck,
    )
    assert r2.status_code == 409


async def test_past_start_rejected(db_session, seed_data, client):
    _, u, _ = await _teacher(db_session, "98006")
    past = (date.today() - timedelta(days=1)).isoformat()
    r = await client.post(
        "/api/v1/me/leaves", json={"start_date": past, "end_date": past},
        cookies=_cookie(u, ["teacher_portal"]),
    )
    assert r.status_code == 422


async def test_withdraw_only_pending_and_own(db_session, seed_data, client):
    _, u_a, _ = await _teacher(db_session, "98007")
    _, u_b, _ = await _teacher(db_session, "98008")
    s_date, e_date = _dates(6, 0)
    r = await client.post(
        "/api/v1/me/leaves", json={"start_date": s_date, "end_date": e_date},
        cookies=_cookie(u_a, ["teacher_portal"]),
    )
    leave_id = r.json()["id"]
    # Teacher B cannot withdraw A's request.
    rb = await client.delete(
        f"/api/v1/me/leaves/{leave_id}", cookies=_cookie(u_b, ["teacher_portal"])
    )
    assert rb.status_code == 404
    # A can withdraw their own pending request.
    ra = await client.delete(
        f"/api/v1/me/leaves/{leave_id}", cookies=_cookie(u_a, ["teacher_portal"])
    )
    assert ra.status_code == 200
