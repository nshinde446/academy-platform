"""Teacher portal — Slice 7: self-service profile (view + contact edit).

A teacher sees their full profile and can edit ONLY their contact details
(phone / email). Identity is the session's own staff id, so there is no way to
edit another teacher. Employment fields are never writable here.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models.auth_models import User
from app.modules.auth.services.auth_service import hash_password
from app.modules.auth.services.token_service import create_access_token
from app.modules.staff.models.staff_models import Department, Staff

BRANCH = uuid.UUID("00000000-0000-0000-0000-000000000001")


async def _teacher(db: AsyncSession, emp: str) -> tuple[Staff, User]:
    dept = (await db.execute(
        select(Department).where(Department.branch_id == BRANCH, Department.name == "MSA-Teachers")
    )).scalar_one_or_none()
    if dept is None:
        dept = Department(branch_id=BRANCH, name="MSA-Teachers", id_range_start=1, id_range_end=99)
        db.add(dept)
        await db.commit()
    s = Staff(
        branch_id=BRANCH, emp_code=emp, first_name="Asha", last_name="Rao",
        department_id=dept.id, designation="Senior Faculty", title="Ms",
        shift_start="09:00", shift_end="17:00", phone="1112223333",
        email="old@example.com",
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
    return s, u


def _cookie(user: User, roles=("teacher_portal",)) -> dict:
    return {"access_token": create_access_token(user.id, list(roles), BRANCH)}


async def test_profile_returns_contact_and_employment(db_session, seed_data, client):
    _, u = await _teacher(db_session, "97001")
    r = await client.get("/api/v1/me/profile", cookies=_cookie(u))
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["employee_code"] == "97001"
    assert b["designation"] == "Senior Faculty"
    assert b["phone"] == "1112223333"
    assert b["email"] == "old@example.com"


async def test_patch_updates_contact(db_session, seed_data, client):
    _, u = await _teacher(db_session, "97002")
    r = await client.patch(
        "/api/v1/me/profile",
        json={"phone": "9998887777", "email": "new@example.com"},
        cookies=_cookie(u),
    )
    assert r.status_code == 200, r.text
    assert r.json()["phone"] == "9998887777"
    assert r.json()["email"] == "new@example.com"
    # Persisted — a fresh GET reads back the new values.
    r2 = await client.get("/api/v1/me/profile", cookies=_cookie(u))
    assert r2.json()["phone"] == "9998887777"
    assert r2.json()["email"] == "new@example.com"


async def test_patch_one_field_keeps_other(db_session, seed_data, client):
    s, u = await _teacher(db_session, "97003")
    r = await client.patch(
        "/api/v1/me/profile", json={"phone": "5554443333"}, cookies=_cookie(u)
    )
    assert r.status_code == 200, r.text
    # email untouched because it was not in the payload.
    assert r.json()["phone"] == "5554443333"
    assert r.json()["email"] == "old@example.com"


async def test_patch_empty_body_rejected(db_session, seed_data, client):
    _, u = await _teacher(db_session, "97004")
    r = await client.patch("/api/v1/me/profile", json={}, cookies=_cookie(u))
    assert r.status_code == 400


async def test_patch_invalid_email_rejected(db_session, seed_data, client):
    _, u = await _teacher(db_session, "97005")
    r = await client.patch(
        "/api/v1/me/profile", json={"email": "not-an-email"}, cookies=_cookie(u)
    )
    assert r.status_code == 422


async def test_patch_cannot_edit_another_teacher(db_session, seed_data, client):
    """Identity is session-derived: a staff_id in the body/query is ignored, so
    teacher A editing with B's id still only changes A's own record."""
    _, u_a = await _teacher(db_session, "97006")
    s_b, u_b = await _teacher(db_session, "97007")
    r = await client.patch(
        "/api/v1/me/profile",
        params={"staff_id": str(s_b.id)},
        json={"phone": "0001112222"},
        cookies=_cookie(u_a),
    )
    assert r.status_code == 200, r.text
    assert r.json()["phone"] == "0001112222"            # A changed
    rb = await client.get("/api/v1/me/profile", cookies=_cookie(u_b))
    assert rb.json()["phone"] == "1112223333"           # B untouched
