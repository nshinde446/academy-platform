"""Manual staff attendance audit trail (PDF3): a manager enters a staff In/Out
time by hand; the row is tagged MANUAL with who made the entry (Name + Role)."""

import uuid
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.attendance.services import staff_daily_service as sds
from app.modules.attendance.models.attendance_models import StaffDailyAttendance
from app.modules.staff.models.staff_models import Department, Staff

BRANCH = uuid.UUID("00000000-0000-0000-0000-000000000001")
ADMIN = uuid.UUID("00000000-0000-0000-0000-000000000100")  # "Admin User", super_admin
DAY = date(2026, 10, 6)


async def _seed_staff(db: AsyncSession) -> Staff:
    dept = Department(branch_id=BRANCH, name="MSA-Teachers", id_range_start=1, id_range_end=50)
    db.add(dept)
    await db.flush()
    staff = Staff(
        branch_id=BRANCH, emp_code="12", first_name="Rahul", last_name="Pawar",
        department_id=dept.id,
    )
    db.add(staff)
    await db.flush()
    return staff


async def test_manual_mark_records_source_and_user(db_session: AsyncSession, seed_data):
    staff = await _seed_staff(db_session)
    row = await sds.manual_mark(
        db_session, staff_id=staff.id, branch_id=BRANCH, day=DAY,
        in_time="09:45", out_time="17:35", user_id=ADMIN,
    )
    assert row.source == "MANUAL"
    assert row.override_by == ADMIN
    assert row.override_at is not None
    assert row.first_in is not None and row.last_out is not None
    assert row.work_minutes > 0


async def test_manual_mark_rejects_out_before_in(db_session: AsyncSession, seed_data):
    from fastapi import HTTPException
    staff = await _seed_staff(db_session)
    try:
        await sds.manual_mark(
            db_session, staff_id=staff.id, branch_id=BRANCH, day=DAY,
            in_time="10:00", out_time="09:00", user_id=ADMIN,
        )
        assert False, "expected rejection"
    except HTTPException as e:
        assert e.status_code == 422


async def test_day_register_shows_manual_tag_with_name_and_role(
    db_session: AsyncSession, seed_data
):
    staff = await _seed_staff(db_session)
    await sds.manual_mark(
        db_session, staff_id=staff.id, branch_id=BRANCH, day=DAY,
        in_time="09:45", out_time="17:35", user_id=ADMIN,
    )
    rows = await sds.day_register(db_session, branch_id=BRANCH, day=DAY)
    r = next(x for x in rows if x["staff_id"] == staff.id)
    assert r["entry_type"] == "MANUAL"
    # "Admin User (Super Admin)" — name from the login, role in brackets.
    assert r["marked_by"].startswith("Admin User (")
    assert "Admin" in r["marked_by"]
    assert r["marked_at"] is not None


async def test_biometric_row_has_no_manual_tag(db_session: AsyncSession, seed_data):
    staff = await _seed_staff(db_session)
    db_session.add(StaffDailyAttendance(
        staff_id=staff.id, branch_id=BRANCH, attendance_date=DAY,
        day_status="PRESENT", signoff="COMPLETE", source="BIOMETRIC", work_minutes=400,
    ))
    await db_session.flush()
    rows = await sds.day_register(db_session, branch_id=BRANCH, day=DAY)
    r = next(x for x in rows if x["staff_id"] == staff.id)
    assert r["entry_type"] == "BIOMETRIC"
    assert r["marked_by"] is None


async def test_old_manual_without_user_shows_not_available(
    db_session: AsyncSession, seed_data
):
    staff = await _seed_staff(db_session)
    db_session.add(StaffDailyAttendance(
        staff_id=staff.id, branch_id=BRANCH, attendance_date=DAY,
        day_status="PRESENT", signoff="MISSING", source="MANUAL",
        work_minutes=0, override_by=None,  # pre-audit manual row
    ))
    await db_session.flush()
    rows = await sds.day_register(db_session, branch_id=BRANCH, day=DAY)
    r = next(x for x in rows if x["staff_id"] == staff.id)
    assert r["entry_type"] == "MANUAL"
    assert r["marked_by"] == "Not available"
