"""Per-batch class start time drives the PRESENT/LATE cutoff (afternoon-batch fix).

The global default class-start is 10:00 IST, so an afternoon punch used to read
LATE for everyone. With a per-batch class_start_time, an afternoon batch is judged
against its own start, and recompute_range flips the historical rows.
"""

import uuid
from datetime import date, datetime, timezone

import pytest

from app.modules.attendance.models.attendance_models import DailyAttendance, RawPunchLog
from app.modules.attendance.services import daily_service
from app.modules.student.models.student_models import Student, StudentBatchMapping

DAY = date(2026, 6, 22)
DAY2 = date(2026, 6, 23)


def _utc(h, m):
    return datetime(2026, 6, 22, h, m, tzinfo=timezone.utc)


async def _punch(db_session, seed_data, *, h, m):
    db_session.add(RawPunchLog(
        device_id="dev1", student_id=seed_data["student"].id,
        punch_timestamp=_utc(h, m), branch_id=seed_data["branch_a"].id,
    ))
    await db_session.flush()


async def _map_to_batch(db_session, seed_data):
    db_session.add(StudentBatchMapping(
        student_id=seed_data["student"].id, batch_id=seed_data["batch"].id,
        branch_id=seed_data["branch_a"].id, status="active", is_deleted=False,
    ))
    await db_session.flush()


async def _rebuild(db_session, seed_data):
    return await daily_service.rebuild_daily(
        db_session, student_id=seed_data["student"].id,
        branch_id=seed_data["branch_a"].id, day=DAY,
    )


# 14:00 IST == 08:30 UTC — exactly the 14:00 batch start, so on time under the
# strict (no-grace) rule; still LATE against the global 10:00 default.
AFTERNOON_H, AFTERNOON_M = 8, 30


@pytest.mark.usefixtures("seed_data")
async def test_afternoon_punch_is_late_under_global_default(db_session, seed_data):
    await _map_to_batch(db_session, seed_data)  # batch has no class_start_time
    await _punch(db_session, seed_data, h=AFTERNOON_H, m=AFTERNOON_M)
    row = await _rebuild(db_session, seed_data)
    assert row.day_status == "LATE"  # the bug: judged against the 10:00 default


@pytest.mark.usefixtures("seed_data")
async def test_afternoon_punch_is_present_with_per_batch_start(db_session, seed_data):
    seed_data["batch"].class_start_time = "14:00"
    await _map_to_batch(db_session, seed_data)
    await _punch(db_session, seed_data, h=AFTERNOON_H, m=AFTERNOON_M)
    row = await _rebuild(db_session, seed_data)
    assert row.day_status == "PRESENT"  # on time for a 14:00 class


@pytest.mark.usefixtures("seed_data")
async def test_recompute_range_flips_historical_late_to_present(db_session, seed_data):
    # 1) record the day with no batch time -> LATE
    await _map_to_batch(db_session, seed_data)
    await _punch(db_session, seed_data, h=AFTERNOON_H, m=AFTERNOON_M)
    row = await _rebuild(db_session, seed_data)
    assert row.day_status == "LATE"

    # 2) set the batch's afternoon start, then recompute the range
    seed_data["batch"].class_start_time = "14:00"
    await db_session.flush()
    n = await daily_service.recompute_range(
        db_session, branch_id=seed_data["branch_a"].id, start=DAY, end=DAY,
    )
    assert n >= 1

    fixed = (await db_session.execute(
        DailyAttendance.__table__.select().where(
            DailyAttendance.student_id == seed_data["student"].id,
            DailyAttendance.attendance_date == DAY,
        )
    )).first()
    assert fixed.day_status == "PRESENT"


@pytest.mark.usefixtures("seed_data")
async def test_recompute_preserves_manual_rows(db_session, seed_data):
    seed_data["batch"].class_start_time = "14:00"
    await _map_to_batch(db_session, seed_data)
    db_session.add(DailyAttendance(
        student_id=seed_data["student"].id, branch_id=seed_data["branch_a"].id,
        attendance_date=DAY, day_status="ABSENT", signoff="NA", source="MANUAL",
    ))
    await db_session.flush()
    await daily_service.recompute_range(
        db_session, branch_id=seed_data["branch_a"].id, start=DAY, end=DAY,
    )
    row = (await db_session.execute(
        DailyAttendance.__table__.select().where(
            DailyAttendance.student_id == seed_data["student"].id,
            DailyAttendance.attendance_date == DAY,
        )
    )).first()
    assert row.source == "MANUAL" and row.day_status == "ABSENT"  # human edit kept


@pytest.mark.usefixtures("seed_data")
async def test_recompute_batched_multi_student_multi_day(db_session, seed_data):
    """The batched recompute must judge each student against their OWN batch
    start across every day in the range — no cross-contamination between the
    per-day punch buckets or the per-student class-start map."""
    b = seed_data["branch_a"].id
    s1 = seed_data["student"]
    s2 = Student(
        branch_id=b, academic_year_id=seed_data["academic_year"].id,
        first_name="Two", last_name="Afternoon", enrollment_number="STU002",
        status="active", is_deleted=False,
    )
    db_session.add(s2)
    await db_session.flush()

    seed_data["batch"].class_start_time = "10:00"     # morning  -> s1
    seed_data["batch_b"].class_start_time = "14:00"   # afternoon -> s2
    db_session.add_all([
        StudentBatchMapping(student_id=s1.id, batch_id=seed_data["batch"].id,
                            branch_id=b, status="active", is_deleted=False),
        StudentBatchMapping(student_id=s2.id, batch_id=seed_data["batch_b"].id,
                            branch_id=b, status="active", is_deleted=False),
    ])
    await db_session.flush()

    # s1 punches 10:00 IST (04:30 UTC); s2 punches 14:00 IST (08:30 UTC) — each
    # on time for their own batch. Seed stale LATE rows so recompute must flip them.
    for dd, day in ((22, DAY), (23, DAY2)):
        for sid, (h, m) in ((s1.id, (4, 30)), (s2.id, (8, 30))):
            db_session.add(RawPunchLog(
                device_id="d", student_id=sid, branch_id=b,
                punch_timestamp=datetime(2026, 6, dd, h, m, tzinfo=timezone.utc),
            ))
            db_session.add(DailyAttendance(
                student_id=sid, branch_id=b, attendance_date=day,
                day_status="LATE", signoff="MISSING", source="BIOMETRIC",
            ))
    await db_session.flush()

    n = await daily_service.recompute_range(db_session, branch_id=b, start=DAY, end=DAY2)
    assert n == 4

    rows = (await db_session.execute(
        DailyAttendance.__table__.select().where(DailyAttendance.branch_id == b)
    )).all()
    status = {(r.student_id, r.attendance_date): r.day_status for r in rows}
    # If s2's afternoon punch were judged against the 10:00 morning cutoff it
    # would read LATE — all four must be PRESENT.
    assert status[(s1.id, DAY)] == "PRESENT"
    assert status[(s1.id, DAY2)] == "PRESENT"
    assert status[(s2.id, DAY)] == "PRESENT"
    assert status[(s2.id, DAY2)] == "PRESENT"


# ── simple model: fixed class-start cutoff, no lecture window, no EXCEPTION ───
# A single campus-entry scanner only proves a student came and roughly when, so
# classification is Present/Late/Absent against the batch's class-start time —
# it does NOT depend on the day's lecture timetable, and never yields EXCEPTION.

from app.modules.lectures.models.lecture_models import Lecture


async def _afternoon_lecture(db_session, seed_data):
    """A 14:00–15:00 IST lecture (08:30–09:30 UTC) for the seed batch."""
    db_session.add(Lecture(
        teacher_id=seed_data["teacher"].id, batch_id=seed_data["batch"].id,
        subject_id=seed_data["subject"].id, academic_year_id=seed_data["academic_year"].id,
        scheduled_start=datetime(2026, 6, 22, 8, 30, tzinfo=timezone.utc),
        scheduled_end=datetime(2026, 6, 22, 9, 30, tzinfo=timezone.utc),
        branch_id=seed_data["branch_a"].id, lecture_status="scheduled",
        status="active", is_deleted=False,
    ))
    await db_session.flush()


@pytest.mark.usefixtures("seed_data")
async def test_strict_one_minute_late_is_late(db_session, seed_data):
    """No grace: arriving one minute after the batch start is LATE."""
    seed_data["batch"].class_start_time = "14:00"
    await _map_to_batch(db_session, seed_data)
    await _punch(db_session, seed_data, h=8, m=31)  # 14:01 IST, 1 min after start
    row = await _rebuild(db_session, seed_data)
    assert row.day_status == "LATE"


@pytest.mark.usefixtures("seed_data")
async def test_strict_seconds_ignored_is_present(db_session, seed_data):
    """Seconds are ignored: 14:00:45 counts as 14:00 → PRESENT."""
    seed_data["batch"].class_start_time = "14:00"
    await _map_to_batch(db_session, seed_data)
    db_session.add(RawPunchLog(
        device_id="dev1", student_id=seed_data["student"].id,
        punch_timestamp=datetime(2026, 6, 22, 8, 30, 45, tzinfo=timezone.utc),  # 14:00:45
        branch_id=seed_data["branch_a"].id,
    ))
    await db_session.flush()
    row = await _rebuild(db_session, seed_data)
    assert row.day_status == "PRESENT"


@pytest.mark.usefixtures("seed_data")
async def test_early_arrival_is_present_no_lower_bound(db_session, seed_data):
    """Arriving well before class start is PRESENT (the old window flagged this
    as an EXCEPTION for being >30 min early)."""
    seed_data["batch"].class_start_time = "14:00"
    await _map_to_batch(db_session, seed_data)
    await _punch(db_session, seed_data, h=7, m=0)   # 12:30 IST, 90 min before class
    row = await _rebuild(db_session, seed_data)
    assert row.day_status == "PRESENT"


@pytest.mark.usefixtures("seed_data")
async def test_scheduled_lecture_does_not_produce_exception(db_session, seed_data):
    """A punch long after the last lecture ended is just LATE, never EXCEPTION —
    the lecture timetable no longer drives classification."""
    await _map_to_batch(db_session, seed_data)  # batch: no class_start -> 10:00 default
    await _afternoon_lecture(db_session, seed_data)
    await _punch(db_session, seed_data, h=11, m=0)  # 16:30 IST, past the 15:00 lecture end
    row = await _rebuild(db_session, seed_data)
    assert row.day_status == "LATE"
    assert row.day_status != "EXCEPTION"


@pytest.mark.usefixtures("seed_data")
async def test_lecture_schedule_does_not_change_status(db_session, seed_data):
    """Same punch classifies the same with or without a scheduled lecture."""
    seed_data["batch"].class_start_time = "14:00"
    await _map_to_batch(db_session, seed_data)
    await _afternoon_lecture(db_session, seed_data)
    await _punch(db_session, seed_data, h=8, m=30)  # 14:00 IST, exactly on time (strict)
    row = await _rebuild(db_session, seed_data)
    assert row.day_status == "PRESENT"  # unaffected by the 14:00–15:00 lecture


@pytest.mark.usefixtures("seed_data")
async def test_single_punch_flags_missing_signoff(db_session, seed_data):
    seed_data["batch"].class_start_time = "14:00"
    await _map_to_batch(db_session, seed_data)
    await _punch(db_session, seed_data, h=8, m=30)   # 14:00 IST, exactly on time, single punch
    row = await _rebuild(db_session, seed_data)
    assert row.day_status == "PRESENT"
    assert row.signoff == "MISSING"   # NO PUNCH-OUT warning
