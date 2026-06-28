"""Teacher↔subject matching spans same-named subject rows.

A subject NAME is carried by one Subject row per course (prod has many
"Physics"/"Chemistry" rows). A teacher is qualified against one of them, but
the schedule slot's subject dropdown collapses the name to one arbitrary id.
Both the dropdown (``list_for_subject``) and the save-time lock
(``teacher_teaches_subject``) must resolve by NAME across sibling rows, else
the timetable shows "No teacher for this subject" even though one exists.
"""

import uuid

import pytest

from app.modules.academic.models.academic_models import Subject
from app.modules.teacher.repositories import teacher_repository as repo


async def _sibling_subject(db_session, seed_data, *, name, code):
    primary = seed_data["subject"]  # seeded "Physics"
    s = Subject(
        id=uuid.uuid4(),
        name=name,
        code=code,
        course_id=primary.course_id,
        branch_id=seed_data["branch_a"].id,
        academic_year_id=seed_data["academic_year"].id,
        status="active",
        is_deleted=False,
    )
    db_session.add(s)
    await db_session.flush()
    return s


@pytest.mark.usefixtures("seed_data")
async def test_dropdown_offers_teacher_across_sibling_subject_rows(db_session, seed_data):
    branch = seed_data["branch_a"].id
    teacher = seed_data["teacher"]  # qualified for the seeded Physics (mapping in seed)
    sibling_physics = await _sibling_subject(db_session, seed_data, name="Physics", code="PHY-DUP")
    await db_session.commit()

    # Teacher mapped to the PRIMARY Physics is offered for the SIBLING Physics id.
    for sid in (seed_data["subject"].id, sibling_physics.id):
        teachers = await repo.list_for_subject(db_session, branch, sid)
        assert teacher.id in {t.id for t in teachers}


@pytest.mark.usefixtures("seed_data")
async def test_save_lock_accepts_sibling_subject_id(db_session, seed_data):
    teacher = seed_data["teacher"]
    sibling_physics = await _sibling_subject(db_session, seed_data, name="Physics", code="PHY-DUP")
    await db_session.commit()

    # The write-path lock must pass for the sibling id, not just the mapped one.
    assert await repo.teacher_teaches_subject(db_session, teacher.id, sibling_physics.id)
    assert await repo.teacher_teaches_subject(db_session, teacher.id, seed_data["subject"].id)


@pytest.mark.usefixtures("seed_data")
async def test_different_named_subject_not_offered(db_session, seed_data):
    branch = seed_data["branch_a"].id
    teacher = seed_data["teacher"]
    chemistry = await _sibling_subject(db_session, seed_data, name="Chemistry", code="CHEM-X")
    await db_session.commit()

    # A Physics teacher must NOT be offered for (or pass the lock on) Chemistry.
    teachers = await repo.list_for_subject(db_session, branch, chemistry.id)
    assert teacher.id not in {t.id for t in teachers}
    assert not await repo.teacher_teaches_subject(db_session, teacher.id, chemistry.id)
