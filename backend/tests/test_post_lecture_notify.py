"""notify_absent_after_last_lecture — mark+notify absent 120 min after a student's
LAST scheduled lecture (per-batch timing, WhatsApp-gated, no false positives)."""

import uuid
from datetime import date, datetime, timezone

import pytest
from sqlalchemy import select

from app.modules.attendance.models.attendance_models import DailyAttendance
from app.modules.attendance.services import daily_service
from app.modules.events.models.event_models import AcademicEvent
from app.modules.lectures.models.lecture_models import Lecture
from app.modules.notifications.models.notification_models import NotificationWhatsappBatch
from app.modules.student.models.student_models import StudentBatchMapping

DAY = date(2026, 6, 22)
# Morning lecture 10:00–12:00 IST == 04:30–06:30 UTC. End + 120 min = 08:30 UTC.
AFTER_MORNING = datetime(2026, 6, 22, 8, 31, tzinfo=timezone.utc)   # end+121m
BEFORE_DELAY = datetime(2026, 6, 22, 7, 0, tzinfo=timezone.utc)     # end+30m


async def _map(db, sd):
    db.add(StudentBatchMapping(student_id=sd["student"].id, batch_id=sd["batch"].id,
                               branch_id=sd["branch_a"].id, status="active", is_deleted=False))
    await db.flush()


async def _enable(db, sd):
    db.add(NotificationWhatsappBatch(branch_id=sd["branch_a"].id, batch_id=sd["batch"].id, is_deleted=False))
    await db.flush()


async def _lecture(db, sd, sh, sm, eh, em):
    db.add(Lecture(teacher_id=sd["teacher"].id, batch_id=sd["batch"].id,
                   subject_id=sd["subject"].id, academic_year_id=sd["academic_year"].id,
                   scheduled_start=datetime(2026, 6, 22, sh, sm, tzinfo=timezone.utc),
                   scheduled_end=datetime(2026, 6, 22, eh, em, tzinfo=timezone.utc),
                   branch_id=sd["branch_a"].id, lecture_status="scheduled",
                   status="active", is_deleted=False))
    await db.flush()


async def _run(db, sd, now):
    return await daily_service.notify_absent_after_last_lecture(
        db, branch_id=sd["branch_a"].id, now=now)


async def _events(db):
    return (await db.execute(
        select(AcademicEvent).where(AcademicEvent.event_type == "STUDENT_ABSENT")
    )).scalars().all()


@pytest.mark.usefixtures("seed_data")
async def test_finalizes_and_notifies_after_last_lecture_plus_delay(db_session, seed_data):
    seed_data["student"].parent_mobile = "9876543210"
    await _map(db_session, seed_data)
    await _enable(db_session, seed_data)
    await _lecture(db_session, seed_data, 4, 30, 6, 30)  # morning
    created = await _run(db_session, seed_data, AFTER_MORNING)
    assert len(created) == 1 and created[0].day_status == "ABSENT"
    evs = await _events(db_session)
    assert len(evs) == 1 and evs[0].student_id == seed_data["student"].id
    assert "9876543210" in (evs[0].metadata_json or "")


@pytest.mark.usefixtures("seed_data")
async def test_not_finalized_before_delay(db_session, seed_data):
    await _map(db_session, seed_data)
    await _enable(db_session, seed_data)
    await _lecture(db_session, seed_data, 4, 30, 6, 30)
    created = await _run(db_session, seed_data, BEFORE_DELAY)
    assert created == []
    assert await _events(db_session) == []


@pytest.mark.usefixtures("seed_data")
async def test_defers_until_the_students_LAST_lecture(db_session, seed_data):
    """A later lecture the same day defers finalization — no false absent after
    the morning class when an afternoon class is still to come."""
    await _map(db_session, seed_data)
    await _enable(db_session, seed_data)
    await _lecture(db_session, seed_data, 4, 30, 6, 30)     # morning end 06:30
    await _lecture(db_session, seed_data, 9, 30, 10, 30)    # afternoon end 10:30 UTC
    # After morning+120 (08:31) but afternoon not ended -> nothing.
    assert await _run(db_session, seed_data, AFTER_MORNING) == []
    # After afternoon end + 120 (12:31) -> finalized.
    created = await _run(db_session, seed_data, datetime(2026, 6, 22, 12, 31, tzinfo=timezone.utc))
    assert len(created) == 1


@pytest.mark.usefixtures("seed_data")
async def test_skips_student_with_a_punch_row(db_session, seed_data):
    await _map(db_session, seed_data)
    await _enable(db_session, seed_data)
    await _lecture(db_session, seed_data, 4, 30, 6, 30)
    db_session.add(DailyAttendance(student_id=seed_data["student"].id, branch_id=seed_data["branch_a"].id,
                                   attendance_date=DAY, day_status="PRESENT", signoff="MISSING", source="BIOMETRIC"))
    await db_session.flush()
    assert await _run(db_session, seed_data, AFTER_MORNING) == []
    assert await _events(db_session) == []


@pytest.mark.usefixtures("seed_data")
async def test_no_action_when_batch_not_whatsapp_enabled(db_session, seed_data):
    await _map(db_session, seed_data)
    await _lecture(db_session, seed_data, 4, 30, 6, 30)  # batch NOT enabled
    assert await _run(db_session, seed_data, AFTER_MORNING) == []
    assert await _events(db_session) == []
