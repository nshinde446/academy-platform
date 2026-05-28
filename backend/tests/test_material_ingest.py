"""M3 — tests for the materials ingest (PDF → questions) pipeline.

We mock the two blocking, external bits (PDF render + Gemini call) and
the storage read, then exercise the real orchestration: question rows
created with the right inheritance, counts + status updated, idempotent
re-ingest, and non-extractable categories skipped.
"""

import uuid

import pytest
from sqlalchemy import select

from app.modules.materials.models.material_models import Material
from app.modules.materials.services import ingest_service
from app.modules.tests.models.test_models import Question


# Canned extraction output — two questions on "page 1", one on "page 2".
FAKE_PAGES = [b"png-page-1", b"png-page-2"]
FAKE_EXTRACTION = {
    b"png-page-1": [
        {
            "question_number": 1,
            "question_text": "What is 2+2?",
            "options": {"A": "3", "B": "4", "C": "5", "D": "6"},
            "correct_answer": "B",
            "difficulty": "easy",
            "blooms_taxonomy": "remember",
        },
        {
            "question_number": 2,
            "question_text": "Speed of light is?",
            "options": {"A": "3e8 m/s", "B": "3e6", "C": "1e8", "D": "9e8"},
            "correct_answer": "a",  # lowercase → normalized to A
            "difficulty": "weird",  # invalid → defaults MEDIUM
        },
    ],
    b"png-page-2": [
        {
            "question_number": 5,
            "question_text": "Newton's second law?",
            "options": {"A": "F=ma", "B": "E=mc2", "C": "PV=nRT", "D": "V=IR"},
            "correct_answer": None,  # not visible → empty
        },
    ],
}


async def _make_material(db_session, seed_data, *, category="dpp") -> Material:
    m = Material(
        id=uuid.uuid4(),
        filename="electric-current.pdf",
        storage_key=f"2025-26/class-11/phy/{category}/{uuid.uuid4()}--ec.pdf",
        mime_type="application/pdf",
        size_bytes=1234,
        sha256="deadbeef" * 8,
        academic_year_id=seed_data["academic_year"].id,
        class_label="11",
        subject_id=seed_data["subject"].id,
        category=category,
        exam_types=["neet", "jee_main"],
        ingest_status="uploaded",
        question_count=0,
        branch_id=seed_data["branch_a"].id,
    )
    db_session.add(m)
    await db_session.commit()
    return m


async def _fresh_material(material_id):
    """Read a material through a brand-new session so we see whatever
    the service session committed (avoids SQLite cross-connection
    snapshot staleness in the test's own session)."""
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as s:
        return (await s.execute(
            select(Material).where(Material.id == material_id)
        )).scalar_one()


async def _fresh_questions(material_id):
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as s:
        return (await s.execute(
            select(Question).where(Question.material_id == material_id)
        )).scalars().all()


def _patch_extraction(monkeypatch):
    """Wire the service to the test DB + canned extraction."""
    from tests.conftest import TestSessionLocal

    monkeypatch.setattr(ingest_service, "async_session_factory", TestSessionLocal)

    class _FakeStorage:
        def read(self, key):
            return b"%PDF-fake"

    monkeypatch.setattr(ingest_service, "get_storage_backend", lambda: _FakeStorage())
    monkeypatch.setattr(
        ingest_service, "_render_pdf_pages", lambda data, max_pages=None: FAKE_PAGES
    )
    monkeypatch.setattr(ingest_service, "_get_gemini_client", lambda: object())
    monkeypatch.setattr(
        ingest_service,
        "_gemini_extract_page",
        lambda client, png: FAKE_EXTRACTION.get(png, []),
    )


class TestMaterialIngest:
    @pytest.mark.usefixtures("seed_data")
    async def test_extracts_and_inherits_material_fields(
        self, db_session, seed_data, monkeypatch
    ):
        material = await _make_material(db_session, seed_data)
        _patch_extraction(monkeypatch)

        result = await ingest_service.extract_and_store(
            material.id, seed_data["branch_a"].id
        )
        assert result["ok"] is True
        assert result["inserted"] == 3

        qs = await _fresh_questions(material.id)
        assert len(qs) == 3
        for q in qs:
            assert q.review_status == "pending_review"
            assert q.subject_id == seed_data["subject"].id
            assert q.branch_id == seed_data["branch_a"].id
            assert q.source == f"material:{material.id}"
            assert q.exam_types == ["neet", "jee_main"]

        # Answer normalization
        by_text = {q.content: q for q in qs}
        assert by_text["What is 2+2?"].correct_answer == "B"
        assert by_text["Speed of light is?"].correct_answer == "A"  # 'a' → 'A'
        assert by_text["Speed of light is?"].difficulty == "MEDIUM"  # invalid → default
        assert by_text["Newton's second law?"].correct_answer == ""  # None → empty

        refreshed = await _fresh_material(material.id)
        assert refreshed.ingest_status == "ingested"
        assert refreshed.question_count == 3
        assert refreshed.ingest_error is None
        # Progress counters reached completion (2 fake pages).
        assert refreshed.ingest_pages_total == 2
        assert refreshed.ingest_pages_done == 2

    @pytest.mark.usefixtures("seed_data")
    async def test_reingest_is_idempotent(self, db_session, seed_data, monkeypatch):
        material = await _make_material(db_session, seed_data)
        _patch_extraction(monkeypatch)

        first = await ingest_service.extract_and_store(material.id, seed_data["branch_a"].id)
        assert first["inserted"] == 3

        second = await ingest_service.extract_and_store(material.id, seed_data["branch_a"].id)
        assert second["inserted"] == 0  # all source_refs already present

        qs = await _fresh_questions(material.id)
        assert len(qs) == 3  # no duplicates

    @pytest.mark.usefixtures("seed_data")
    async def test_non_extractable_category_skipped(
        self, db_session, seed_data, monkeypatch
    ):
        material = await _make_material(db_session, seed_data, category="notes")
        _patch_extraction(monkeypatch)

        result = await ingest_service.extract_and_store(
            material.id, seed_data["branch_a"].id
        )
        assert result["ok"] is True
        assert result["inserted"] == 0

        qs = await _fresh_questions(material.id)
        assert len(qs) == 0

        refreshed = await _fresh_material(material.id)
        assert refreshed.ingest_status == "ingested"

    @pytest.mark.usefixtures("seed_data")
    async def test_extraction_failure_marks_failed(
        self, db_session, seed_data, monkeypatch
    ):
        material = await _make_material(db_session, seed_data)
        _patch_extraction(monkeypatch)

        # Make rendering blow up.
        def _boom(data, max_pages=None):
            raise RuntimeError("corrupt PDF")

        monkeypatch.setattr(ingest_service, "_render_pdf_pages", _boom)

        result = await ingest_service.extract_and_store(
            material.id, seed_data["branch_a"].id
        )
        assert result["ok"] is False
        assert "corrupt PDF" in result["error"]

        refreshed = await _fresh_material(material.id)
        assert refreshed.ingest_status == "ingest_failed"
        assert "corrupt PDF" in (refreshed.ingest_error or "")
