"""Staff punches ride the same ingest funnel as students.

A device userId that matches Staff.emp_code (and not a student rfid) is written
to staff_raw_punch_logs and rolled up into staff_daily_attendance — instead of
being dropped as 'no student'. Student punches are unaffected.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.attendance.integrations.biomax.schemas import PunchEvent
from app.modules.attendance.integrations.biomax.service import ingest_punches
from app.modules.attendance.models.attendance_models import (
    RawPunchLog,
    StaffDailyAttendance,
    StaffRawPunchLog,
)
from app.modules.attendance.services import daily_service
from app.modules.staff.models.staff_models import Department, Staff
from app.modules.student.models.student_models import Student

BRANCH_A = uuid.UUID("00000000-0000-0000-0000-000000000001")
ACADEMIC_YEAR = uuid.UUID("00000000-0000-0000-0000-000000000030")


def _utc(y, mo, d, h, mi) -> datetime:
    return datetime(y, mo, d, h, mi, tzinfo=timezone.utc)


async def _make_staff(db: AsyncSession, emp_code: str) -> Staff:
    dept = Department(
        branch_id=BRANCH_A, name="Security", id_range_start=81, id_range_end=90,
    )
    db.add(dept)
    await db.flush()
    staff = Staff(
        branch_id=BRANCH_A, emp_code=emp_code, first_name="Ratan", last_name="Singh",
        department_id=dept.id,
    )
    db.add(staff)
    await db.flush()
    return staff


async def _make_student(db: AsyncSession, rfid: str) -> Student:
    student = Student(
        branch_id=BRANCH_A, academic_year_id=ACADEMIC_YEAR,
        first_name="Stud", last_name="Ent", rfid_number=rfid,
    )
    db.add(student)
    await db.flush()
    return student


async def test_staff_punch_routes_to_staff_path(db_session: AsyncSession, seed_data):
    staff = await _make_staff(db_session, "81")
    student = await _make_student(db_session, "9001")

    # IST 10:20 IN and 18:30 OUT on Mon 2026-08-03 (04:50 / 13:00 UTC), plus one
    # student punch. Two staff punches -> COMPLETE sign-off.
    events = [
        PunchEvent(vendor_user_id="81", punch_timestamp=_utc(2026, 8, 3, 4, 50),
                   direction="IN", device_id="biomax"),
        PunchEvent(vendor_user_id="81", punch_timestamp=_utc(2026, 8, 3, 13, 0),
                   direction="OUT", device_id="biomax"),
        PunchEvent(vendor_user_id="9001", punch_timestamp=_utc(2026, 8, 3, 4, 30),
                   direction="IN", device_id="biomax"),
    ]

    result = await ingest_punches(db_session, events, BRANCH_A)
    assert result.staff_inserted == 2
    assert result.inserted == 1  # the student punch
    assert result.skipped_no_student == 0

    await daily_service.rebuild_after_ingest(
        db_session,
        branch_id=BRANCH_A,
        affected=[(a.student_id, a.punch_timestamp) for a in result.affected],
        affected_staff=[(a.staff_id, a.punch_timestamp) for a in result.affected_staff],
    )

    # Staff raw + daily rows exist.
    raw = (await db_session.execute(
        select(StaffRawPunchLog).where(StaffRawPunchLog.staff_id == staff.id)
    )).scalars().all()
    assert len(raw) == 2

    day = (await db_session.execute(
        select(StaffDailyAttendance).where(StaffDailyAttendance.staff_id == staff.id)
    )).scalar_one()
    assert day.day_status == "LATE"  # 10:20 IST > 10:00 + 10min grace
    assert day.signoff == "COMPLETE"
    assert day.work_minutes == 490  # 18:30 - 10:20
    assert day.ot_minutes == 0

    # Student punch still landed in the student log, untouched.
    student_raw = (await db_session.execute(
        select(RawPunchLog).where(RawPunchLog.student_id == student.id)
    )).scalars().all()
    assert len(student_raw) == 1


async def test_unknown_id_still_skipped(db_session: AsyncSession, seed_data):
    await _make_staff(db_session, "81")
    events = [
        PunchEvent(vendor_user_id="99999", punch_timestamp=_utc(2026, 8, 3, 5, 0),
                   direction="IN", device_id="biomax"),
    ]
    result = await ingest_punches(db_session, events, BRANCH_A)
    assert result.skipped_no_student == 1
    assert result.staff_inserted == 0
    assert result.inserted == 0


async def test_half_day_when_work_below_threshold(db_session: AsyncSession, seed_data):
    staff = await _make_staff(db_session, "82")
    # IST 10:00 IN, 12:30 OUT = 150 min < 240 half-day threshold.
    events = [
        PunchEvent(vendor_user_id="82", punch_timestamp=_utc(2026, 8, 3, 4, 30),
                   direction="IN", device_id="biomax"),
        PunchEvent(vendor_user_id="82", punch_timestamp=_utc(2026, 8, 3, 7, 0),
                   direction="OUT", device_id="biomax"),
    ]
    result = await ingest_punches(db_session, events, BRANCH_A)
    await daily_service.rebuild_after_ingest(
        db_session, branch_id=BRANCH_A, affected=[],
        affected_staff=[(a.staff_id, a.punch_timestamp) for a in result.affected_staff],
    )
    day = (await db_session.execute(
        select(StaffDailyAttendance).where(StaffDailyAttendance.staff_id == staff.id)
    )).scalar_one()
    assert day.day_status == "HALF_DAY"
    assert day.work_minutes == 150


async def test_day_register_lists_every_staff_with_status(
    db_session: AsyncSession, seed_data
):
    """The staff Day Register returns one row per staff for the day — the puncher
    with IN/OUT/work/LATE, and a non-puncher as ABSENT."""
    from datetime import date

    from app.modules.attendance.services import staff_daily_service

    present = await _make_staff(db_session, "81")
    # A second staff in the same dept who never punches -> ABSENT.
    absent = Staff(
        branch_id=BRANCH_A, emp_code="83", first_name="No", last_name="Show",
        department_id=present.department_id,
    )
    db_session.add(absent)
    await db_session.flush()

    events = [
        PunchEvent(vendor_user_id="81", punch_timestamp=_utc(2026, 8, 3, 4, 50),
                   direction="IN", device_id="biomax"),
        PunchEvent(vendor_user_id="81", punch_timestamp=_utc(2026, 8, 3, 13, 0),
                   direction="OUT", device_id="biomax"),
    ]
    result = await ingest_punches(db_session, events, BRANCH_A)
    await daily_service.rebuild_after_ingest(
        db_session, branch_id=BRANCH_A, affected=[],
        affected_staff=[(a.staff_id, a.punch_timestamp) for a in result.affected_staff],
    )

    rows = await staff_daily_service.day_register(
        db_session, branch_id=BRANCH_A, day=date(2026, 8, 3),
    )
    by_code = {r["emp_code"]: r for r in rows}
    assert by_code["81"]["status"] == "LATE"
    assert by_code["81"]["in_time"] == "10:20"
    assert by_code["81"]["out_time"] == "18:30"
    assert by_code["81"]["work_minutes"] == 490
    assert by_code["83"]["status"] == "ABSENT"
    assert by_code["83"]["in_time"] is None
