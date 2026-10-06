"""Flexible teacher–subject assignment: a teacher keeps their core subject and
can teach a SECONDARY subject for specific batches only. The Subject→Teacher
lock treats a (teacher, subject, batch) assignment like a core qualification,
scoped to that batch."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.academic.models.academic_models import Subject
from app.modules.academic import subject_seeding
from app.modules.teacher.repositories import teacher_repository
from app.modules.teacher.services import teacher_service
from app.modules.teacher.models.teacher_models import (
    TeacherSubjectMapping,
)

BRANCH = uuid.UUID("00000000-0000-0000-0000-000000000001")
TEACHER = uuid.UUID("00000000-0000-0000-0000-000000000060")   # core: Physics (seed)
SUBJECT_PHY = uuid.UUID("00000000-0000-0000-0000-000000000050")
BATCH_A = uuid.UUID("00000000-0000-0000-0000-000000000070")   # seed batch (course JEE-ADV)
BATCH_B = uuid.UUID("00000000-0000-0000-0000-000000000071")
ADMIN = uuid.UUID("00000000-0000-0000-0000-000000000100")
AY = uuid.UUID("00000000-0000-0000-0000-000000000030")
COURSE = uuid.UUID("00000000-0000-0000-0000-000000000040")


async def _core_physics(db: AsyncSession):
    """The seed teacher already has a Physics TeacherSubjectMapping (core)."""
    db.add(TeacherSubjectMapping(
        teacher_id=TEACHER, subject_id=SUBJECT_PHY, branch_id=BRANCH,
        status="active", is_deleted=False,
    ))
    await db.flush()


def test_six_new_subjects_in_catalog():
    cat = subject_seeding.ADDABLE_SUBJECTS
    assert len(cat) == 10
    for s in ("Marathi", "Hindi", "English", "IT", "SST", "History"):
        assert s in cat
        assert s in subject_seeding.SUBJECT_CODES  # has a code


async def test_core_subject_unchanged(db_session: AsyncSession, seed_data):
    """No secondary assignment ⇒ behaves exactly as today: core subject teacher
    is eligible in any batch; a non-core subject is not."""
    await _core_physics(db_session)
    # Physics (core) — eligible regardless of batch.
    assert await teacher_repository.teacher_teaches_subject(
        db_session, TEACHER, SUBJECT_PHY, BATCH_A)
    assert await teacher_repository.teacher_teaches_subject(
        db_session, TEACHER, SUBJECT_PHY)  # batch_id=None, as before


async def test_assign_secondary_subject_scoped_to_batch(db_session: AsyncSession, seed_data):
    """Assign the (core-Physics) teacher to teach IT for Batch A only."""
    await _core_physics(db_session)

    rows = await teacher_service.assign_secondary_subjects(
        db_session, BRANCH, TEACHER, "IT", [BATCH_A], ADMIN,
    )
    assert len(rows) == 1 and rows[0]["subject_name"] == "IT"
    it_subject_id = rows[0]["subject_id"]

    # The IT subject was auto-created on the batch's course.
    it = await db_session.get(Subject, it_subject_id)
    assert it is not None and it.name == "IT" and it.course_id == COURSE

    # Eligible for IT in Batch A …
    assert await teacher_repository.teacher_teaches_subject(
        db_session, TEACHER, it_subject_id, BATCH_A)
    # … but NOT in Batch B (not assigned there) …
    assert not await teacher_repository.teacher_teaches_subject(
        db_session, TEACHER, it_subject_id, BATCH_B)
    # … and NOT at all without a batch (IT is not a core subject).
    assert not await teacher_repository.teacher_teaches_subject(
        db_session, TEACHER, it_subject_id)

    # Core Physics still intact and batch-agnostic.
    assert await teacher_repository.teacher_teaches_subject(
        db_session, TEACHER, SUBJECT_PHY, BATCH_B)


async def test_list_for_subject_includes_secondary_only_for_batch(
    db_session: AsyncSession, seed_data
):
    await _core_physics(db_session)
    rows = await teacher_service.assign_secondary_subjects(
        db_session, BRANCH, TEACHER, "IT", [BATCH_A], ADMIN,
    )
    it_id = rows[0]["subject_id"]

    offered_a = await teacher_repository.list_for_subject(db_session, BRANCH, it_id, BATCH_A)
    assert TEACHER in {t.id for t in offered_a}
    offered_b = await teacher_repository.list_for_subject(db_session, BRANCH, it_id, BATCH_B)
    assert TEACHER not in {t.id for t in offered_b}
    # No batch given ⇒ core-only, teacher not offered for IT.
    offered_none = await teacher_repository.list_for_subject(db_session, BRANCH, it_id)
    assert TEACHER not in {t.id for t in offered_none}


async def test_remove_secondary_assignment(db_session: AsyncSession, seed_data):
    await _core_physics(db_session)
    rows = await teacher_service.assign_secondary_subjects(
        db_session, BRANCH, TEACHER, "IT", [BATCH_A, BATCH_B], ADMIN,
    )
    it_id = rows[0]["subject_id"]
    # Remove the Batch B assignment only.
    batch_b_row = next(r for r in rows if r["batch_id"] == BATCH_B)
    await teacher_service.remove_secondary_subject(
        db_session, BRANCH, batch_b_row["id"], ADMIN)

    assert await teacher_repository.teacher_teaches_subject(
        db_session, TEACHER, it_id, BATCH_A)        # Batch A intact
    assert not await teacher_repository.teacher_teaches_subject(
        db_session, TEACHER, it_id, BATCH_B)        # Batch B gone
    remaining = await teacher_service.list_secondary_for_teacher(db_session, BRANCH, TEACHER)
    assert {r["batch_id"] for r in remaining} == {BATCH_A}


async def test_scheduling_secondary_lecture_passes_lock(db_session: AsyncSession, seed_data):
    """Scheduling an IT lecture for the (core-Physics) teacher in the assigned
    batch passes the lock; in an unassigned batch it is rejected."""
    from app.modules.lectures.services import lecture_service
    from app.modules.lectures.schemas.lecture_schemas import LectureCreate
    from datetime import datetime, timezone
    from fastapi import HTTPException

    await _core_physics(db_session)
    rows = await teacher_service.assign_secondary_subjects(
        db_session, BRANCH, TEACHER, "IT", [BATCH_A], ADMIN,
    )
    it_id = rows[0]["subject_id"]

    def _lec(batch_id, hour):
        return LectureCreate(
            teacher_id=TEACHER, batch_id=batch_id, subject_id=it_id,
            scheduled_start=datetime(2026, 11, 2, hour, 0, tzinfo=timezone.utc),
            scheduled_end=datetime(2026, 11, 2, hour + 1, 0, tzinfo=timezone.utc),
            delivery_mode="online",
        )

    # Batch A (assigned) — lock passes, lecture created with subject = IT.
    lec = await lecture_service.schedule_lecture(db_session, _lec(BATCH_A, 4), ADMIN)
    assert lec.subject_id == it_id and lec.teacher_id == TEACHER

    # Batch B (not assigned) — a non-conflicting slot, so we reach (and fail) the
    # Subject→Teacher lock rather than a time clash.
    try:
        await lecture_service.schedule_lecture(db_session, _lec(BATCH_B, 7), ADMIN)
        assert False, "expected the Subject→Teacher lock to reject IT in Batch B"
    except HTTPException as e:
        assert e.status_code == 422
        assert "not assigned to this subject" in e.detail.lower()
