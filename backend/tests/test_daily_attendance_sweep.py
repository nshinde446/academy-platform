"""run_absent_sweep (B5) — population end-of-day absent marking + parent notify.

Decisions: only students with >=1 scheduled lecture that day (working day) get
swept (1); active/enrolled only (3); a STUDENT_ABSENT event is emitted per
sweep-ABSENT for parent notification (5); manual/present rows are left alone.
"""

import uuid
from datetime import date, datetime, timezone

import pytest
from sqlalchemy import select

from app.modules.attendance.models.attendance_models import DailyAttendance
from app.modules.attendance.services import daily_service
from app.modules.events.models.event_models import AcademicEvent
from app.modules.lectures.models.lecture_models import Lecture
from app.modules.student.models.student_models import StudentBatchMapping

DAY = date(2026, 6, 22)


async def _map_student_to_batch(db_session, seed_data):
    db_session.add(StudentBatchMapping(
        student_id=seed_data["student"].id,
        batch_id=seed_data["batch"].id,
        branch_id=seed_data["branch_a"].id,
        status="active",
        is_deleted=False,
    ))
    await db_session.flush()


async def _schedule_lecture(db_session, seed_data):
    # 10:00–12:00 IST == 04:30–06:30 UTC on the 22nd.
    db_session.add(Lecture(
        teacher_id=seed_data["teacher"].id,
        batch_id=seed_data["batch"].id,
        subject_id=seed_data["subject"].id,
        academic_year_id=seed_data["academic_year"].id,
        scheduled_start=datetime(2026, 6, 22, 4, 30, tzinfo=timezone.utc),
        scheduled_end=datetime(2026, 6, 22, 6, 30, tzinfo=timezone.utc),
        branch_id=seed_data["branch_a"].id,
        status="active",
        is_deleted=False,
    ))
    await db_session.flush()


async def _sweep(db_session, seed_data, notify=True):
    return await daily_service.run_absent_sweep(
        db_session, branch_id=seed_data["branch_a"].id, day=DAY, notify=notify
    )


@pytest.mark.usefixtures("seed_data")
async def test_sweep_marks_absent_and_notifies(db_session, seed_data):
    seed_data["student"].parent_mobile = "9876543210"
    await _map_student_to_batch(db_session, seed_data)
    await _schedule_lecture(db_session, seed_data)

    created = await _sweep(db_session, seed_data)
    assert len(created) == 1
    assert created[0].day_status == "ABSENT"
    assert created[0].source == "SYSTEM"

    events = (await db_session.execute(
        select(AcademicEvent).where(AcademicEvent.event_type == "STUDENT_ABSENT")
    )).scalars().all()
    assert len(events) == 1
    assert events[0].student_id == seed_data["student"].id
    assert "9876543210" in (events[0].metadata_json or "")


@pytest.mark.usefixtures("seed_data")
async def test_present_student_not_swept(db_session, seed_data):
    await _map_student_to_batch(db_session, seed_data)
    await _schedule_lecture(db_session, seed_data)
    db_session.add(DailyAttendance(
        student_id=seed_data["student"].id,
        branch_id=seed_data["branch_a"].id,
        attendance_date=DAY,
        day_status="PRESENT",
        signoff="MISSING",
        source="BIOMETRIC",
    ))
    await db_session.flush()

    created = await _sweep(db_session, seed_data)
    assert created == []


@pytest.mark.usefixtures("seed_data")
async def test_no_lecture_means_no_sweep(db_session, seed_data):
    # Student mapped to a batch but NO lecture scheduled -> not a working day.
    await _map_student_to_batch(db_session, seed_data)
    created = await _sweep(db_session, seed_data)
    assert created == []
    rows = (await db_session.execute(
        select(DailyAttendance).where(DailyAttendance.student_id == seed_data["student"].id)
    )).scalars().all()
    assert rows == []


@pytest.mark.usefixtures("seed_data")
async def test_sweep_idempotent(db_session, seed_data):
    await _map_student_to_batch(db_session, seed_data)
    await _schedule_lecture(db_session, seed_data)
    first = await _sweep(db_session, seed_data)
    assert len(first) == 1
    second = await _sweep(db_session, seed_data)
    assert second == []  # already marked -> no double-mark, no re-notify
