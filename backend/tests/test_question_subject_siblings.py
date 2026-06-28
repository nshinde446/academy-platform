"""Question-bank subject filtering spans same-named subject rows.

A subject NAME is carried by one Subject row per course (e.g. many "Physics"
rows). The question bank is branch-wide, and the composer's subject dropdown
collapses the name to one arbitrary id. Filtering questions by that one id must
still surface every question stored under a sibling same-named row — otherwise
the composer can pick a subject and see zero questions.
"""

import uuid

import pytest

from app.modules.academic.models.academic_models import Subject
from app.modules.tests.models.test_models import Question
from app.modules.tests.repositories import test_repository as repo


async def _question(db_session, seed_data, *, subject_id, content):
    q = Question(
        id=uuid.uuid4(),
        content=content,
        options=None,
        correct_answer="A",
        subject_id=subject_id,
        difficulty="MEDIUM",
        blooms_taxonomy="APPLY",
        source="studymat:x",
        source_ref="k#1",
        review_status="approved",
        exam_types=[],
        branch_id=seed_data["branch_a"].id,
        academic_year_id=seed_data["academic_year"].id,
        status="active",
        is_deleted=False,
    )
    db_session.add(q)
    await db_session.flush()
    return q


class TestSubjectNameSiblings:
    @pytest.mark.usefixtures("seed_data")
    async def test_filter_by_one_id_spans_same_name_rows(self, db_session, seed_data):
        primary = seed_data["subject"]  # the seeded "Physics"
        # A second "Physics" row (same name, different id) — a per-course
        # duplicate, exactly like prod's 21 Physics rows.
        sibling = Subject(
            id=uuid.uuid4(),
            name=primary.name,
            code=f"{primary.code}-DUP",
            course_id=primary.course_id,
            branch_id=seed_data["branch_a"].id,
            academic_year_id=seed_data["academic_year"].id,
            status="active",
            is_deleted=False,
        )
        db_session.add(sibling)
        await db_session.flush()

        await _question(db_session, seed_data, subject_id=primary.id, content="under-primary")
        await _question(db_session, seed_data, subject_id=sibling.id, content="under-sibling")
        await db_session.commit()

        branch = seed_data["branch_a"].id
        # Filtering by EITHER id returns BOTH questions — count, list, and pick.
        for sid in (primary.id, sibling.id):
            assert (
                await repo.count_questions(
                    db_session, branch, subject_id=sid, review_status="approved"
                )
                == 2
            )
            rows = await repo.list_questions(
                db_session, branch, subject_id=sid, review_status="approved"
            )
            assert {r.content for r in rows} == {"under-primary", "under-sibling"}
            picked = await repo.pick_random_questions(
                db_session, branch, count=10, subject_id=sid, review_status="approved"
            )
            assert len(picked) == 2

    @pytest.mark.usefixtures("seed_data")
    async def test_different_named_subject_not_pulled_in(self, db_session, seed_data):
        """Name-matching must not bleed across genuinely different subjects."""
        primary = seed_data["subject"]
        chem = Subject(
            id=uuid.uuid4(),
            name="Chemistry",
            code="CHEM-X",
            course_id=primary.course_id,
            branch_id=seed_data["branch_a"].id,
            academic_year_id=seed_data["academic_year"].id,
            status="active",
            is_deleted=False,
        )
        db_session.add(chem)
        await db_session.flush()
        await _question(db_session, seed_data, subject_id=primary.id, content="phys")
        await _question(db_session, seed_data, subject_id=chem.id, content="chem")
        await db_session.commit()

        branch = seed_data["branch_a"].id
        assert (
            await repo.count_questions(
                db_session, branch, subject_id=primary.id, review_status="approved"
            )
            == 1
        )
