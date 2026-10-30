"""Teacher Portal — Change 1: per-day attendance feed.

The feed reuses the existing staff attendance + late-fine logic so the numbers
match the staff reports: per-day IN/OUT/hours, late minutes, fine, and a status
code (P/A/L/HD/WO/HL), plus a month summary. Future days are blank, not Absent.
"""

import uuid
from datetime import date

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.attendance.models.attendance_models import (
    LateFineSlab,
    StaffDailyAttendance,
)
from app.modules.attendance.services.daily_service import branch_timezone
from app.modules.attendance.time_utils import local_time_on
from app.modules.teacher_portal.services import portal_service
from app.modules.staff.models.staff_models import Department, Staff

BRANCH = uuid.UUID("00000000-0000-0000-0000-000000000001")


async def _staff(db: AsyncSession) -> Staff:
    dept = Department(branch_id=BRANCH, name="MSA-Teachers", id_range_start=91000, id_range_end=91999)
    db.add(dept)
    await db.flush()
    s = Staff(branch_id=BRANCH, emp_code="91000", first_name="Asha", last_name="Rao",
              department_id=dept.id, shift_start="08:00", weekly_off_days="6")  # Sunday off
    db.add(s)
    await db.flush()
    return s


async def _slabs(db: AsyncSession) -> None:
    db.add_all([
        LateFineSlab(min_minutes=1, max_minutes=5, fine_amount=200, color_hex="#BDD7EE", label="1-5"),
        LateFineSlab(min_minutes=6, max_minutes=10, fine_amount=500, color_hex="#FFE699", label="6-10"),
        LateFineSlab(min_minutes=11, max_minutes=None, fine_amount=1000, color_hex="#F4B084", label="11+"),
    ])
    await db.flush()


async def test_attendance_rows_and_summary(db_session: AsyncSession, seed_data):
    s = await _staff(db_session)
    await _slabs(db_session)
    tz = await branch_timezone(db_session, BRANCH)
    # A fully-past month (Jan 2026) so nothing is "future".
    # Day 1: present on time. Day 2: late ~20m (L). Day 3: half day. (Jan 4 = Sun WO.)
    db_session.add(StaffDailyAttendance(
        branch_id=BRANCH, staff_id=s.id, attendance_date=date(2026, 1, 1),
        day_status="PRESENT", signoff="COMPLETE", source="BIOMETRIC", work_minutes=510,
        first_in=local_time_on(date(2026, 1, 1), tz, 7, 55),
        last_out=local_time_on(date(2026, 1, 1), tz, 17, 0),
    ))
    db_session.add(StaffDailyAttendance(
        branch_id=BRANCH, staff_id=s.id, attendance_date=date(2026, 1, 2),
        day_status="LATE", signoff="COMPLETE", source="BIOMETRIC", work_minutes=480,
        first_in=local_time_on(date(2026, 1, 2), tz, 8, 20),
        last_out=local_time_on(date(2026, 1, 2), tz, 17, 0),
    ))
    db_session.add(StaffDailyAttendance(
        branch_id=BRANCH, staff_id=s.id, attendance_date=date(2026, 1, 3),
        day_status="HALF_DAY", signoff="MISSING", source="BIOMETRIC", work_minutes=0,
        first_in=local_time_on(date(2026, 1, 3), tz, 7, 55),  # on time, out missing -> HD
    ))
    await db_session.flush()

    data = await portal_service.attendance(db_session, s.id, date(2026, 1, 1), date(2026, 1, 5))
    by_date = {r["date"]: r for r in data["rows"]}

    assert by_date["2026-01-01"]["status"] == "P"
    assert by_date["2026-01-01"]["in"] == "07:55"
    assert by_date["2026-01-01"]["hours"] == "8h 30m"
    assert by_date["2026-01-01"]["fine"] in (0.0, None)

    assert by_date["2026-01-02"]["status"] == "L"
    assert by_date["2026-01-02"]["late_minutes"] == 20
    assert by_date["2026-01-02"]["fine"] == 1000.0  # 11+ band

    assert by_date["2026-01-03"]["status"] == "HD"
    assert by_date["2026-01-03"]["out"] == "Missing"

    assert by_date["2026-01-04"]["status"] == "WO"   # Sunday weekly-off, no punch
    assert by_date["2026-01-05"]["status"] == "A"    # Monday, no punch

    sm = data["summary"]
    assert sm["present"] == 2 and sm["late"] == 1
    assert sm["half"] == 1 and sm["absent"] == 1 and sm["weekly_off"] == 1
    assert sm["total_fine"] == 1000.0


async def test_future_days_are_blank(db_session: AsyncSession, seed_data):
    s = await _staff(db_session)
    # A range spanning into next year → those days are future.
    nxt = date.today().replace(year=date.today().year + 1)
    data = await portal_service.attendance(db_session, s.id, nxt, nxt)
    assert data["rows"][0]["future"] is True
    assert data["rows"][0]["status"] is None


async def test_range_limit_enforced(db_session: AsyncSession, seed_data):
    from fastapi import HTTPException
    s = await _staff(db_session)
    with pytest.raises(HTTPException) as e:
        await portal_service.attendance(db_session, s.id, date(2026, 1, 1), date(2026, 12, 31))
    assert e.value.status_code == 422
