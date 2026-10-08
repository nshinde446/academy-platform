"""GET /students?batch_id= restricts the roster to a batch's enrolled students.

Before the fix the endpoint ignored batch_id and returned the whole branch.
"""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.student.models.student_models import Student, StudentBatchMapping
from app.modules.student.services import student_service


async def _student(db_session, seed_data, enr, batch_id=None) -> uuid.UUID:
    s = Student(
        id=uuid.uuid4(), branch_id=seed_data["branch_a"].id,
        academic_year_id=seed_data["academic_year"].id,
        first_name=enr, last_name="S", enrollment_number=enr,
        status="active", is_deleted=False,
    )
    db_session.add(s)
    if batch_id is not None:
        db_session.add(StudentBatchMapping(
            student_id=s.id, batch_id=batch_id, branch_id=seed_data["branch_a"].id,
            status="active", is_deleted=False,
        ))
    await db_session.flush()
    return s.id


@pytest.mark.usefixtures("seed_data")
async def test_batch_id_restricts_to_enrolled_students(db_session: AsyncSession, seed_data):
    b = seed_data["branch_a"].id
    a_batch = seed_data["batch"].id
    b_batch = seed_data["batch_b"].id
    in_a = await _student(db_session, seed_data, "INA", a_batch)
    in_b = await _student(db_session, seed_data, "INB", b_batch)
    await _student(db_session, seed_data, "NONE")  # no batch

    only_a = await student_service.list_students(db_session, b, batch_id=a_batch)
    ids_a = {s.id for s in only_a}
    assert in_a in ids_a
    assert in_b not in ids_a  # other batch excluded

    # No batch_id → the whole branch (includes the unmapped one + seed student).
    everyone = await student_service.list_students(db_session, b, limit=200)
    assert in_a in {s.id for s in everyone} and in_b in {s.id for s in everyone}
    assert len(everyone) > len(only_a)


@pytest.mark.usefixtures("seed_data")
async def test_batch_id_no_duplicate_on_multiple_mappings(db_session: AsyncSession, seed_data):
    b = seed_data["branch_a"].id
    a_batch = seed_data["batch"].id
    sid = await _student(db_session, seed_data, "DUP", a_batch)
    # A second live mapping to the SAME batch must not duplicate the student.
    db_session.add(StudentBatchMapping(
        student_id=sid, batch_id=a_batch, branch_id=b, status="active", is_deleted=False,
    ))
    await db_session.flush()
    rows = await student_service.list_students(db_session, b, batch_id=a_batch)
    assert [s.id for s in rows].count(sid) == 1
