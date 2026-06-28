"""Sweep scheduler (B6) — which branches are due, and the due-branch core.

The Celery wrappers just call asyncio.run; the logic worth testing is the pure
due-check and the session-injected core. IST = UTC+5:30, so 18:05 UTC == 23:35
IST (in the sweep hour), and 10:00 UTC == 15:30 IST (not).
"""

from datetime import date, datetime, timezone

import pytest
from sqlalchemy import select

from app.modules.attendance.jobs import tasks
from app.modules.attendance.models.attendance_models import DailyAttendance
from app.modules.lectures.models.lecture_models import Lecture
from app.modules.student.models.student_models import StudentBatchMapping

IST = "Asia/Kolkata"


def test_is_branch_due_in_sweep_hour():
    due, local_date = tasks.is_branch_due(
        datetime(2026, 6, 22, 18, 5, tzinfo=timezone.utc), IST
    )
    assert due is True
    assert local_date == date(2026, 6, 22)


def test_is_branch_due_outside_sweep_hour():
    due, _ = tasks.is_branch_due(
        datetime(2026, 6, 22, 10, 0, tzinfo=timezone.utc), IST
    )
    assert due is False


@pytest.mark.usefixtures("seed_data")
async def test_sweep_due_branches_marks_absent_at_local_2330(db_session, seed_data):
    db_session.add(StudentBatchMapping(
        student_id=seed_data["student"].id,
        batch_id=seed_data["batch"].id,
        branch_id=seed_data["branch_a"].id,
        status="active", is_deleted=False,
    ))
    db_session.add(Lecture(
        teacher_id=seed_data["teacher"].id,
        batch_id=seed_data["batch"].id,
        subject_id=seed_data["subject"].id,
        academic_year_id=seed_data["academic_year"].id,
        scheduled_start=datetime(2026, 6, 22, 4, 30, tzinfo=timezone.utc),
        scheduled_end=datetime(2026, 6, 22, 6, 30, tzinfo=timezone.utc),
        branch_id=seed_data["branch_a"].id,
        status="active", is_deleted=False,
    ))
    await db_session.commit()

    # 23:35 IST on the 22nd.
    swept = await tasks.sweep_due_branches(
        db_session, datetime(2026, 6, 22, 18, 5, tzinfo=timezone.utc)
    )
    marked = {b: n for b, d, n in swept}
    assert marked.get(seed_data["branch_a"].id) == 1

    row = (await db_session.execute(
        select(DailyAttendance).where(
            DailyAttendance.student_id == seed_data["student"].id
        )
    )).scalar_one()
    assert row.day_status == "ABSENT"


@pytest.mark.usefixtures("seed_data")
async def test_sweep_due_branches_noop_outside_hour(db_session, seed_data):
    # 15:30 IST — no branch is due, nothing marked.
    swept = await tasks.sweep_due_branches(
        db_session, datetime(2026, 6, 22, 10, 0, tzinfo=timezone.utc)
    )
    assert swept == []
