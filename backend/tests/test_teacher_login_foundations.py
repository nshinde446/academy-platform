"""Teacher Login — Slice 1 data foundations (migration 0067).

The additive user account-lifecycle columns, the append-only auth_events log,
and the seeded teacher_portal_config exist and behave. Existing email-login
users are unaffected (must_change_password defaults false).
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models.auth_models import (
    AUTH_EVENT_TYPES,
    AuthEvent,
    TeacherPortalConfig,
    User,
)
from app.modules.auth.services.auth_service import hash_password
from app.modules.staff.models.staff_models import Department, Staff

BRANCH = uuid.UUID("00000000-0000-0000-0000-000000000001")


async def _staff(db: AsyncSession, emp_code: str) -> Staff:
    dept = Department(
        branch_id=BRANCH, name="MSA-Teachers", id_range_start=1, id_range_end=50
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


async def test_user_defaults_unaffected_for_email_user(db_session: AsyncSession, seed_data):
    """A normal email user keeps the new fields at safe defaults — not forced to
    change password, no staff link, zero failed attempts."""
    u = User(
        email="plain@example.com", password_hash=hash_password("x"),
        first_name="Plain", last_name="User",
    )
    db_session.add(u)
    await db_session.flush()
    assert u.must_change_password is False
    assert u.failed_attempts == 0
    assert u.staff_id is None
    assert u.username is None
    assert u.locked_until is None


async def test_teacher_account_links_staff_and_forces_change(db_session: AsyncSession, seed_data):
    s = await _staff(db_session, "91000")
    u = User(
        email="91000@teacher.local", password_hash=hash_password("temp"),
        first_name="Asha", last_name="Rao",
        username="91000", staff_id=s.id, must_change_password=True,
    )
    db_session.add(u)
    await db_session.flush()
    loaded = (await db_session.execute(
        select(User).where(User.username == "91000")
    )).scalar_one()
    assert loaded.staff_id == s.id
    assert loaded.must_change_password is True


async def test_auth_event_is_appendable(db_session: AsyncSession, seed_data):
    ev = AuthEvent(
        username_attempted="91000", event="login_fail", ip="10.0.0.1",
        user_agent="pytest", detail="bad password",
    )
    db_session.add(ev)
    await db_session.flush()
    assert ev.event in AUTH_EVENT_TYPES
    assert ev.created_at is not None
    assert ev.id is not None


async def test_idor_attempt_is_a_recognised_event():
    # The IDOR attempt the spec requires logging must be a known event type.
    assert "idor_attempt" in AUTH_EVENT_TYPES
    assert "password_reset" in AUTH_EVENT_TYPES
    assert "account_created" in AUTH_EVENT_TYPES


async def test_portal_config_stores_typed_values(db_session: AsyncSession, seed_data):
    # Values keep their natural type (string / int / bool) via JSON.
    db_session.add_all([
        TeacherPortalConfig(key="fine_visibility", value="after_day_close"),
        TeacherPortalConfig(key="history_days", value=90),
        TeacherPortalConfig(key="teacher_login_enabled", value=False),
    ])
    await db_session.flush()
    rows = {
        r.key: r.value
        for r in (await db_session.execute(select(TeacherPortalConfig))).scalars()
    }
    assert rows["fine_visibility"] == "after_day_close"
    assert rows["history_days"] == 90
    assert rows["teacher_login_enabled"] is False
