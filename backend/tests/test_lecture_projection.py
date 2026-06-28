"""Layer 2 projection (B7) — day fact -> per-lecture attendance_records.

Feeds the EXISTING attendance_records table (same key, same status enum), one
row per batch student (present & absent), manual marks never overwritten.
Lecture 10:00–12:00 IST == 04:30–06:30 UTC; on-time cutoff 04:40 UTC.
"""

import uuid
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.modules.attendance.models.attendance_models import (
    AttendanceRecord,
    DailyAttendance,
)
from app.modules.attendance.services import attendance_service, daily_service
from app.modules.attendance.models.attendance_models import RawPunchLog
from app.modules.lectures.models.lecture_models import Lecture
from app.modules.student.models.student_models import Student, StudentBatchMapping

START = datetime(2026, 6, 22, 4, 30, tzinfo=timezone.utc)
END = datetime(2026, 6, 22, 6, 30, tzinfo=timezone.utc)
CLOSE = datetime(2026, 6, 22, 9, 30, tzinfo=timezone.utc)  # 15:00 IST
GRACE = timedelta(minutes=10)


def _day(first_in, last_out=None, day_status="PRESENT"):
    return SimpleNamespace(
        first_in=first_in, last_out=last_out, day_status=day_status
    )


# ── pure projection logic ──────────────────────────────────────────────────

def test_status_present_when_on_time_and_overlapping():
    row = _day(datetime(2026, 6, 22, 3, 59, tzinfo=timezone.utc), last_out=END)
    assert daily_service.lecture_status_from_day(row, START, END, CLOSE, GRACE) == "PRESENT"


def test_status_late_when_after_cutoff():
    row = _day(datetime(2026, 6, 22, 5, 0, tzinfo=timezone.utc), last_out=END)
    assert daily_service.lecture_status_from_day(row, START, END, CLOSE, GRACE) == "LATE"


def test_status_absent_when_no_overlap():
    row = _day(datetime(2026, 6, 22, 7, 0, tzinfo=timezone.utc))  # came after lecture
    assert daily_service.lecture_status_from_day(row, START, END, CLOSE, GRACE) == "ABSENT"


def test_missing_out_treated_as_present_through_close():
    # Punched in on time, never punched out -> presumed on campus through close.
    row = _day(datetime(2026, 6, 22, 3, 59, tzinfo=timezone.utc), last_out=None)
    assert daily_service.lecture_status_from_day(row, START, END, CLOSE, GRACE) == "PRESENT"


def test_absent_day_row_is_absent():
    row = _day(None, day_status="ABSENT")
    assert daily_service.lecture_status_from_day(row, START, END, CLOSE, GRACE) == "ABSENT"


# ── integration: writes one record per batch student ───────────────────────

async def _second_student(db_session, seed_data):
    s = Student(
        id=uuid.uuid4(),
        branch_id=seed_data["branch_a"].id,
        academic_year_id=seed_data["academic_year"].id,
        first_name="Second", last_name="Student",
        status="active", is_deleted=False,
    )
    db_session.add(s)
    await db_session.flush()
    return s


async def _setup_lecture_and_batch(db_session, seed_data, students):
    for s in students:
        db_session.add(StudentBatchMapping(
            student_id=s.id, batch_id=seed_data["batch"].id,
            branch_id=seed_data["branch_a"].id, status="active", is_deleted=False,
        ))
    lecture = Lecture(
        teacher_id=seed_data["teacher"].id, batch_id=seed_data["batch"].id,
        subject_id=seed_data["subject"].id, academic_year_id=seed_data["academic_year"].id,
        scheduled_start=START, scheduled_end=END,
        branch_id=seed_data["branch_a"].id, status="active", is_deleted=False,
    )
    db_session.add(lecture)
    await db_session.flush()
    return lecture


@pytest.mark.usefixtures("seed_data")
async def test_project_writes_present_and_absent_records(db_session, seed_data):
    s1 = seed_data["student"]
    s2 = await _second_student(db_session, seed_data)
    lecture = await _setup_lecture_and_batch(db_session, seed_data, [s1, s2])

    # s1 present on time (day row); s2 has no day row -> absent.
    db_session.add(DailyAttendance(
        student_id=s1.id, branch_id=seed_data["branch_a"].id, attendance_date=date(2026, 6, 22),
        first_in=datetime(2026, 6, 22, 3, 59, tzinfo=timezone.utc), last_out=None,
        day_status="PRESENT", signoff="MISSING", source="BIOMETRIC",
    ))
    await db_session.flush()

    recs = await daily_service.project_day_onto_lecture(
        db_session, lecture_id=lecture.id, branch_id=seed_data["branch_a"].id,
        current_user_id=seed_data["admin_user"].id,
    )
    by_student = {r.student_id: r for r in recs}
    assert by_student[s1.id].attendance_status == "PRESENT"
    assert by_student[s1.id].source == "BIOMETRIC"
    assert by_student[s2.id].attendance_status == "ABSENT"
    assert by_student[s2.id].source == "SYSTEM"


@pytest.mark.usefixtures("seed_data")
async def test_manual_record_not_overwritten(db_session, seed_data):
    s1 = seed_data["student"]
    lecture = await _setup_lecture_and_batch(db_session, seed_data, [s1])
    # Teacher manually marked PRESENT; student has NO punches (would project ABSENT).
    db_session.add(AttendanceRecord(
        student_id=s1.id, lecture_id=lecture.id, attendance_status="PRESENT",
        marked_at=datetime.now(timezone.utc), marked_by=seed_data["admin_user"].id,
        source="MANUAL", branch_id=seed_data["branch_a"].id,
    ))
    await db_session.flush()

    recs = await daily_service.project_day_onto_lecture(
        db_session, lecture_id=lecture.id, branch_id=seed_data["branch_a"].id,
        current_user_id=seed_data["admin_user"].id,
    )
    assert recs[0].attendance_status == "PRESENT"
    assert recs[0].source == "MANUAL"


@pytest.mark.usefixtures("seed_data")
async def test_process_raw_punches_delegates_to_day_layer(db_session, seed_data):
    s1 = seed_data["student"]
    lecture = await _setup_lecture_and_batch(db_session, seed_data, [s1])
    # On-time punch at 09:29 IST (03:59 UTC).
    db_session.add(RawPunchLog(
        device_id="dev1", student_id=s1.id,
        punch_timestamp=datetime(2026, 6, 22, 3, 59, tzinfo=timezone.utc),
        branch_id=seed_data["branch_a"].id,
    ))
    await db_session.flush()

    recs = await attendance_service.process_raw_punches(
        db_session, lecture.id, seed_data["branch_a"].id, seed_data["admin_user"].id
    )
    assert len(recs) == 1
    assert recs[0].attendance_status == "PRESENT"

    # And it landed in the existing attendance_records table the UI reads.
    stored = (await db_session.execute(
        select(AttendanceRecord).where(AttendanceRecord.lecture_id == lecture.id)
    )).scalars().all()
    assert len(stored) == 1
