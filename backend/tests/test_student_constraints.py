"""DB-level guard: a branch can't have two active students sharing one
enrollment number (case-insensitive). Soft-deleted rows and NULL enrollment
numbers are exempt (partial index). Mirrors the app's dedup key so a re-upload
can never double a student even if the service-level dedup is bypassed."""

import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from app.modules.student.models.student_models import Student

BRANCH = uuid.UUID("00000000-0000-0000-0000-000000000001")
AY = uuid.UUID("00000000-0000-0000-0000-000000000030")


def _student(enrollment, *, deleted=False):
    return Student(
        branch_id=BRANCH,
        academic_year_id=AY,
        first_name="A",
        last_name="B",
        enrollment_number=enrollment,
        is_deleted=deleted,
    )


class TestActiveEnrollmentUnique:
    @pytest.mark.usefixtures("seed_data")
    async def test_duplicate_active_enrollment_rejected(self, seed_data, db_session):
        db_session.add(_student("ENR-100"))
        await db_session.flush()
        db_session.add(_student("ENR-100"))
        with pytest.raises(IntegrityError):
            await db_session.flush()

    @pytest.mark.usefixtures("seed_data")
    async def test_duplicate_is_case_insensitive(self, seed_data, db_session):
        db_session.add(_student("enr-200"))
        await db_session.flush()
        db_session.add(_student("ENR-200"))
        with pytest.raises(IntegrityError):
            await db_session.flush()

    @pytest.mark.usefixtures("seed_data")
    async def test_soft_deleted_duplicate_allowed(self, seed_data, db_session):
        db_session.add(_student("ENR-300", deleted=True))
        db_session.add(_student("ENR-300"))
        await db_session.flush()  # the live one + a dead one don't collide

    @pytest.mark.usefixtures("seed_data")
    async def test_null_enrollment_not_constrained(self, seed_data, db_session):
        db_session.add(_student(None))
        db_session.add(_student(None))
        await db_session.flush()  # many students legitimately have no enrollment no.
