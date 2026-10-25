"""Teacher portal — Slice 9: self-service productivity metrics + buckets.

Checks the endpoint shape (totals + chart buckets), range validation, and that
attendance days roll into the totals. Lecture-level numbers are exercised by the
faculty-service tests this reuses; here we assert wiring + attendance rollup.
"""

import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.attendance.models.attendance_models import StaffDailyAttendance
from app.modules.auth.models.auth_models import User
from app.modules.auth.services.auth_service import hash_password
from app.modules.auth.services.token_service import create_access_token
from app.modules.staff.models.staff_models import Department, Staff
from app.modules.teacher.models.teacher_models import Teacher

BRANCH = uuid.UUID("00000000-0000-0000-0000-000000000001")


async def _teacher(db: AsyncSession, emp: str, linked: bool = True) -> tuple[Staff, User]:
    dept = (await db.execute(
        select(Department).where(Department.branch_id == BRANCH, Department.name == "MSA-Teachers")
    )).scalar_one_or_none()
    if dept is None:
        dept = Department(branch_id=BRANCH, name="MSA-Teachers", id_range_start=1, id_range_end=99)
        db.add(dept)
        await db.commit()
    tid = None
    if linked:
        t = Teacher(branch_id=BRANCH, first_name="Asha", last_name="Rao")
        db.add(t)
        await db.commit()
        tid = t.id
    s = Staff(
        branch_id=BRANCH, emp_code=emp, first_name="Asha", last_name="Rao",
        department_id=dept.id, linked_teacher_id=tid, shift_start="09:00",
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


def _cookie(user: User) -> dict:
    return {"access_token": create_access_token(user.id, ["teacher_portal"], BRANCH)}


async def test_productivity_shape_and_attendance_rollup(db_session, seed_data, client):
    s, u = await _teacher(db_session, "99001")
    today = date.today()
    db_session.add(StaffDailyAttendance(
        staff_id=s.id, branch_id=BRANCH, attendance_date=today,
        first_in=datetime(today.year, today.month, today.day, 3, 30, tzinfo=timezone.utc),  # 09:00 IST
        last_out=None, day_status="PRESENT", signoff="MISSING", source="BIOMETRIC", work_minutes=0,
    ))
    await db_session.commit()
    r = await client.get("/api/v1/me/productivity", params={"range": "month"}, cookies=_cookie(u))
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["range"] == "month"
    assert b["is_teacher"] is True
    assert "totals" in b and "buckets" in b
    assert b["totals"]["present_days"] >= 1
    # Every bucket carries the charted keys.
    for bk in b["buckets"]:
        assert {"label", "lectures", "on_time", "delayed", "on_time_pct", "present_days"} <= bk.keys()


async def test_week_has_at_most_seven_buckets(db_session, seed_data, client):
    _, u = await _teacher(db_session, "99002")
    r = await client.get("/api/v1/me/productivity", params={"range": "week"}, cookies=_cookie(u))
    assert r.status_code == 200
    assert 1 <= len(r.json()["buckets"]) <= 7


async def test_year_buckets_are_months(db_session, seed_data, client):
    _, u = await _teacher(db_session, "99003")
    r = await client.get("/api/v1/me/productivity", params={"range": "year"}, cookies=_cookie(u))
    assert r.status_code == 200
    # One bucket per month that has started this year.
    assert len(r.json()["buckets"]) == date.today().month


async def test_invalid_range_rejected(db_session, seed_data, client):
    _, u = await _teacher(db_session, "99004")
    r = await client.get("/api/v1/me/productivity", params={"range": "decade"}, cookies=_cookie(u))
    assert r.status_code == 400


async def test_non_teacher_staff_is_flagged(db_session, seed_data, client):
    _, u = await _teacher(db_session, "99005", linked=False)
    r = await client.get("/api/v1/me/productivity", params={"range": "month"}, cookies=_cookie(u))
    assert r.status_code == 200
    assert r.json()["is_teacher"] is False
    assert r.json()["totals"]["lectures"] == 0
