"""Question-bank facet filters: class_label / topic (via material join),
material_id, subject_id. exam_type is Postgres-only so it's exercised
only for "accepted without error" here (the test DB is SQLite)."""

import uuid

import pytest

from app.modules.materials.models.material_models import Material
from app.modules.tests.models.test_models import Question
from app.modules.tests.repositories import test_repository as repo


async def _material(db_session, seed_data, *, class_label, topic) -> Material:
    m = Material(
        id=uuid.uuid4(),
        filename=f"{topic}.pdf",
        storage_key=f"k/{uuid.uuid4()}.pdf",
        mime_type="application/pdf",
        size_bytes=1,
        sha256="0" * 64,
        academic_year_id=seed_data["academic_year"].id,
        class_label=class_label,
        subject_id=seed_data["subject"].id,
        topic=topic,
        category="dpp",
        exam_types=["neet"],
        ingest_status="ingested",
        question_count=0,
        branch_id=seed_data["branch_a"].id,
    )
    db_session.add(m)
    await db_session.flush()
    return m


async def _question(db_session, seed_data, *, material=None, content="q") -> Question:
    q = Question(
        id=uuid.uuid4(),
        content=content,
        options=None,
        correct_answer="A",
        subject_id=seed_data["subject"].id,
        difficulty="MEDIUM",
        blooms_taxonomy="APPLY",
        source="material:x" if material else "studymat:x",
        source_ref="k#p1q1",
        review_status="pending_review",
        material_id=material.id if material else None,
        exam_types=["neet"] if material else [],
        branch_id=seed_data["branch_a"].id,
        academic_year_id=seed_data["academic_year"].id,
        status="active",
        is_deleted=False,
    )
    db_session.add(q)
    await db_session.flush()
    return q


class TestQuestionFilters:
    @pytest.mark.usefixtures("seed_data")
    async def test_filter_by_class_label_via_material(self, db_session, seed_data):
        m12 = await _material(db_session, seed_data, class_label="12", topic="electricity")
        m11 = await _material(db_session, seed_data, class_label="11", topic="kinematics")
        await _question(db_session, seed_data, material=m12, content="c12-a")
        await _question(db_session, seed_data, material=m12, content="c12-b")
        await _question(db_session, seed_data, material=m11, content="c11-a")
        await _question(db_session, seed_data, material=None, content="legacy")
        await db_session.commit()

        rows = await repo.list_questions(
            db_session, seed_data["branch_a"].id, class_label="12"
        )
        assert {r.content for r in rows} == {"c12-a", "c12-b"}

        n = await repo.count_questions(
            db_session, seed_data["branch_a"].id, class_label="12"
        )
        assert n == 2

    @pytest.mark.usefixtures("seed_data")
    async def test_filter_by_material_id(self, db_session, seed_data):
        m = await _material(db_session, seed_data, class_label="12", topic="optics")
        await _question(db_session, seed_data, material=m, content="m-a")
        await _question(db_session, seed_data, material=None, content="other")
        await db_session.commit()

        rows = await repo.list_questions(
            db_session, seed_data["branch_a"].id, material_id=m.id
        )
        assert {r.content for r in rows} == {"m-a"}

    @pytest.mark.usefixtures("seed_data")
    async def test_filter_by_topic_via_material(self, db_session, seed_data):
        m = await _material(db_session, seed_data, class_label="12", topic="thermodynamics")
        await _question(db_session, seed_data, material=m, content="thermo-q")
        await _question(db_session, seed_data, material=None, content="nope")
        await db_session.commit()

        rows = await repo.list_questions(
            db_session, seed_data["branch_a"].id, topic="thermodynamics"
        )
        assert {r.content for r in rows} == {"thermo-q"}

    @pytest.mark.usefixtures("seed_data")
    async def test_exam_type_param_accepted(self, db_session, seed_data):
        # On SQLite exam_type is a no-op (PG-only array op); just verify it
        # doesn't raise and returns the unfiltered set.
        m = await _material(db_session, seed_data, class_label="12", topic="x")
        await _question(db_session, seed_data, material=m, content="q1")
        await db_session.commit()

        rows = await repo.list_questions(
            db_session, seed_data["branch_a"].id, exam_type="neet"
        )
        assert any(r.content == "q1" for r in rows)
