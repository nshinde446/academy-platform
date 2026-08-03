"""Daily WhatsApp attendance digest — scope switch (ALL vs ABSENT_ONLY).

Builds a working day with one present and one absent student, then checks that
``run_daily_digest`` emits the right DAILY_ATTENDANCE_DIGEST events per scope, is
idempotent, and that the nightly sweep fires it only when a branch has switched
it on. IST = UTC+5:30, so the 04:30 UTC lecture is 10:00 IST (a working day).
"""

import json
import uuid
from datetime import date, datetime, timezone

import pytest
from sqlalchemy import select

from app.modules.attendance.jobs import tasks
from app.modules.attendance.models.attendance_models import DailyAttendance
from app.modules.attendance.services import daily_service
from app.modules.events.models.event_models import AcademicEvent
from app.modules.lectures.models.lecture_models import Lecture
from app.modules.notifications.repositories import notification_repository
from app.modules.student.models.student_models import Student, StudentBatchMapping

IST = "Asia/Kolkata"
DAY = date(2026, 6, 22)


async def _build_working_day(db_session, seed_data):
    """One batch with a lecture on DAY; student A present, student B absent."""
    branch = seed_data["branch_a"]
    batch = seed_data["batch"]
    present = seed_data["student"]  # gets a PRESENT row below

    absent = Student(
        id=uuid.UUID("00000000-0000-0000-0000-0000000000b2"),
        branch_id=branch.id,
        academic_year_id=seed_data["academic_year"].id,
        first_name="Absent", last_name="Kid",
        enrollment_number="STU002",
        parent_mobile="9876500002",
        status="active", is_deleted=False,
    )
    db_session.add(absent)

    for s in (present, absent):
        db_session.add(StudentBatchMapping(
            student_id=s.id, batch_id=batch.id, branch_id=branch.id,
            status="active", is_deleted=False,
        ))
    db_session.add(Lecture(
        teacher_id=seed_data["teacher"].id, batch_id=batch.id,
        subject_id=seed_data["subject"].id,
        academic_year_id=seed_data["academic_year"].id,
        scheduled_start=datetime(2026, 6, 22, 4, 30, tzinfo=timezone.utc),
        scheduled_end=datetime(2026, 6, 22, 6, 30, tzinfo=timezone.utc),
        branch_id=branch.id, status="active", is_deleted=False,
    ))
    # Present student's resolved day row.
    db_session.add(DailyAttendance(
        student_id=present.id, branch_id=branch.id, attendance_date=DAY,
        first_in=datetime(2026, 6, 22, 4, 25, tzinfo=timezone.utc),
        last_out=datetime(2026, 6, 22, 6, 35, tzinfo=timezone.utc),
        day_status="PRESENT", signoff="COMPLETE", source="BIOMETRIC",
        status="active", is_deleted=False,
    ))
    await db_session.commit()
    return branch, present, absent


async def _digest_events(db_session, branch_id):
    return list((await db_session.execute(
        select(AcademicEvent).where(
            AcademicEvent.event_type == "DAILY_ATTENDANCE_DIGEST",
            AcademicEvent.branch_id == branch_id,
        )
    )).scalars().all())


async def test_digest_all_scope_emits_for_every_student(db_session, seed_data):
    branch, present, absent = await _build_working_day(db_session, seed_data)

    emitted = await daily_service.run_daily_digest(
        db_session, branch_id=branch.id, day=DAY, scope="ALL", tz_name=IST,
    )
    await db_session.commit()
    assert len(emitted) == 2

    events = await _digest_events(db_session, branch.id)
    by_student = {e.student_id: json.loads(e.metadata_json) for e in events}
    assert by_student[present.id]["status"] == "Present"
    assert by_student[absent.id]["status"] == "Absent"
    assert by_student[absent.id]["recipient"] == "9876500002"


async def test_digest_absent_only_scope_skips_present(db_session, seed_data):
    branch, present, absent = await _build_working_day(db_session, seed_data)

    emitted = await daily_service.run_daily_digest(
        db_session, branch_id=branch.id, day=DAY, scope="ABSENT_ONLY", tz_name=IST,
    )
    await db_session.commit()
    assert len(emitted) == 1
    assert emitted[0].student_id == absent.id


async def test_digest_is_idempotent(db_session, seed_data):
    branch, _, _ = await _build_working_day(db_session, seed_data)

    first = await daily_service.run_daily_digest(
        db_session, branch_id=branch.id, day=DAY, scope="ALL", tz_name=IST,
    )
    await db_session.commit()
    assert len(first) == 2

    second = await daily_service.run_daily_digest(
        db_session, branch_id=branch.id, day=DAY, scope="ALL", tz_name=IST,
    )
    await db_session.commit()
    assert second == []  # already digested this local day


async def test_digest_no_working_day_emits_nothing(db_session, seed_data):
    # No lecture scheduled -> not a working day -> nothing.
    emitted = await daily_service.run_daily_digest(
        db_session, branch_id=seed_data["branch_a"].id, day=DAY,
        scope="ALL", tz_name=IST,
    )
    assert emitted == []


async def test_nightly_sweep_runs_digest_only_when_enabled(db_session, seed_data):
    branch, _, absent = await _build_working_day(db_session, seed_data)
    # Remove the present student's row so the sweep has something to mark, and so
    # ABSENT_ONLY has a clear target; the digest still reads final statuses.
    await notification_repository.upsert_settings(
        db_session, branch.id,
        daily_digest_enabled=True, daily_digest_scope="ABSENT_ONLY",
    )
    await db_session.commit()

    # 23:35 IST on DAY -> branch is due.
    await tasks.sweep_due_branches(
        db_session, datetime(2026, 6, 22, 18, 5, tzinfo=timezone.utc)
    )
    await db_session.commit()

    events = await _digest_events(db_session, branch.id)
    assert len(events) == 1  # only the absent student
    assert events[0].student_id == absent.id


async def test_nightly_sweep_no_digest_when_disabled(db_session, seed_data):
    branch, _, _ = await _build_working_day(db_session, seed_data)
    # No settings row -> digest off by default.
    await tasks.sweep_due_branches(
        db_session, datetime(2026, 6, 22, 18, 5, tzinfo=timezone.utc)
    )
    await db_session.commit()

    assert await _digest_events(db_session, branch.id) == []
