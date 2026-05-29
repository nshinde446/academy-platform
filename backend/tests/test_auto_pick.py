"""Composer auto-pick (M4): random draw from the question bank by facets,
difficulty mix, exclude_ids, and approved-only default. Also covers
paper_type persistence on create_test and the test-questions detail read.

Exercises the service + repository directly (SQLite test DB), mirroring
test_question_filters.py."""

import uuid

import pytest

from app.modules.tests.repositories import test_repository as repo
from app.modules.tests.schemas.test_schemas import AutoPickRequest
from app.modules.tests.services import test_service
from app.modules.tests.models.test_models import Question


async def _q(db_session, seed_data, *, difficulty="MEDIUM", review_status="approved",
             content="q") -> Question:
    q = Question(
        id=uuid.uuid4(),
        content=content,
        options=None,
        correct_answer="A",
        subject_id=seed_data["subject"].id,
        difficulty=difficulty,
        blooms_taxonomy="APPLY",
        source="HUMAN",
        review_status=review_status,
        exam_types=[],
        branch_id=seed_data["branch_a"].id,
        academic_year_id=seed_data["academic_year"].id,
        status="active",
        is_deleted=False,
    )
    db_session.add(q)
    await db_session.flush()
    return q


class TestAutoPick:
    @pytest.mark.usefixtures("seed_data")
    async def test_flat_count_returns_at_most_count(self, db_session, seed_data):
        for i in range(8):
            await _q(db_session, seed_data, content=f"a{i}")
        await db_session.commit()

        picked = await test_service.auto_pick_questions(
            db_session, seed_data["branch_a"].id,
            AutoPickRequest(subject_id=seed_data["subject"].id, count=5),
        )
        assert len(picked) == 5

    @pytest.mark.usefixtures("seed_data")
    async def test_approved_only_by_default(self, db_session, seed_data):
        await _q(db_session, seed_data, content="ok", review_status="approved")
        await _q(db_session, seed_data, content="pending", review_status="pending_review")
        await _q(db_session, seed_data, content="rejected", review_status="rejected")
        await db_session.commit()

        picked = await test_service.auto_pick_questions(
            db_session, seed_data["branch_a"].id,
            AutoPickRequest(subject_id=seed_data["subject"].id, count=10),
        )
        assert {p["content"] for p in picked} == {"ok"}

    @pytest.mark.usefixtures("seed_data")
    async def test_difficulty_mix_draws_per_difficulty(self, db_session, seed_data):
        for i in range(4):
            await _q(db_session, seed_data, difficulty="EASY", content=f"e{i}")
        for i in range(4):
            await _q(db_session, seed_data, difficulty="MEDIUM", content=f"m{i}")
        for i in range(4):
            await _q(db_session, seed_data, difficulty="HARD", content=f"h{i}")
        await db_session.commit()

        picked = await test_service.auto_pick_questions(
            db_session, seed_data["branch_a"].id,
            AutoPickRequest(
                subject_id=seed_data["subject"].id,
                difficulty_mix={"EASY": 2, "MEDIUM": 3, "HARD": 1},
            ),
        )
        by_diff: dict[str, int] = {}
        for p in picked:
            by_diff[p["difficulty"]] = by_diff.get(p["difficulty"], 0) + 1
        assert by_diff == {"EASY": 2, "MEDIUM": 3, "HARD": 1}

    @pytest.mark.usefixtures("seed_data")
    async def test_exclude_ids_are_never_returned(self, db_session, seed_data):
        kept = [await _q(db_session, seed_data, content=f"k{i}") for i in range(3)]
        await db_session.commit()
        exclude = [kept[0].id, kept[1].id]

        picked = await test_service.auto_pick_questions(
            db_session, seed_data["branch_a"].id,
            AutoPickRequest(
                subject_id=seed_data["subject"].id, count=10, exclude_ids=exclude,
            ),
        )
        assert {p["content"] for p in picked} == {"k2"}

    @pytest.mark.usefixtures("seed_data")
    async def test_subject_facet_scopes_results(self, db_session, seed_data):
        await _q(db_session, seed_data, content="in-subject")
        await db_session.commit()

        picked = await test_service.auto_pick_questions(
            db_session, seed_data["branch_a"].id,
            AutoPickRequest(subject_id=uuid.uuid4(), count=10),
        )
        assert picked == []


class TestPaperTypePersistence:
    @pytest.mark.usefixtures("seed_data")
    async def test_create_test_persists_paper_type(self, db_session, seed_data):
        test = await test_service.create_test(
            db_session,
            {
                "name": "Mechanics DPP",
                "paper_type": "DPP",
                "batch_id": seed_data["batch"].id,
                "subject_id": seed_data["subject"].id,
            },
            seed_data["admin_user"].id,
        )
        assert test.paper_type == "DPP"

    @pytest.mark.usefixtures("seed_data")
    async def test_invalid_paper_type_rejected(self, db_session, seed_data):
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc:
            await test_service.create_test(
                db_session,
                {
                    "name": "bad",
                    "paper_type": "QUIZ",
                    "batch_id": seed_data["batch"].id,
                    "subject_id": seed_data["subject"].id,
                },
                seed_data["admin_user"].id,
            )
        assert exc.value.status_code == 422


class TestTestQuestionDetails:
    @pytest.mark.usefixtures("seed_data")
    async def test_returns_questions_in_order(self, db_session, seed_data):
        test = await test_service.create_test(
            db_session,
            {
                "name": "paper",
                "paper_type": "TEST",
                "batch_id": seed_data["batch"].id,
                "subject_id": seed_data["subject"].id,
            },
            seed_data["admin_user"].id,
        )
        q1 = await _q(db_session, seed_data, content="first")
        q2 = await _q(db_session, seed_data, content="second")
        await db_session.commit()
        await repo.add_questions_to_test(
            db_session, test.id,
            [
                {"question_id": q2.id, "order": 1},
                {"question_id": q1.id, "order": 0},
            ],
        )
        await db_session.commit()

        rows = await test_service.get_test_question_details(
            db_session, test.id, seed_data["branch_a"].id
        )
        assert [r["content"] for r in rows] == ["first", "second"]
