"""Paper PDF generation (Tier 14): mathtext LaTeX rendering + PyMuPDF
Story layout for the question paper and answer key. Exercises the render
helpers directly so it runs on the SQLite test DB without HTTP."""

import uuid
from types import SimpleNamespace

import fitz
import pytest

from app.modules.tests.repositories import test_repository as repo
from app.modules.tests.services import test_service
from app.modules.tests.services import pdf_service
from app.modules.tests.services.latex_render import render_math_png
from app.modules.tests.models.test_models import Question


def _meta(name="Mechanics DPP", paper_type="DPP", total_marks=2.0):
    return SimpleNamespace(name=name, paper_type=paper_type, total_marks=total_marks)


def _q(content, *, options=None, correct="A", explanation=None, difficulty="MEDIUM"):
    return {
        "content": content,
        "options": options,
        "correct_answer": correct,
        "explanation": explanation,
        "difficulty": difficulty,
    }


class TestLatexRender:
    def test_good_expression_returns_png(self):
        png = render_math_png(r"x^2 + \frac{1}{2}")
        assert png is not None
        assert png[:8] == b"\x89PNG\r\n\x1a\n"

    def test_malformed_expression_returns_none(self):
        assert render_math_png(r"\frac{1}{") is None


class TestPaperPdf:
    def test_question_paper_is_valid_pdf(self):
        questions = [
            _q(
                "A body moves with velocity $v = u + at$. Find $v$.",
                options={"A": "$5$", "B": "10", "C": "15", "D": "20"},
            ),
            _q("Plain text question with no math here.",
               options={"A": "one", "B": "two", "C": "three", "D": "four"}),
        ]
        data = pdf_service.build_question_paper_pdf(_meta(), questions, "Bright Future")
        assert data[:5] == b"%PDF-"
        doc = fitz.open("pdf", data)
        assert doc.page_count >= 1
        text = doc[0].get_text()
        assert "Bright Future" in text
        assert "Mechanics DPP" in text

    def test_answer_key_lists_answers(self):
        questions = [
            _q("Q1", correct="B", explanation="Because $E = mc^2$."),
            _q("Q2", correct="D"),
        ]
        data = pdf_service.build_answer_key_pdf(_meta(), questions, "Bright Future")
        doc = fitz.open("pdf", data)
        text = doc[0].get_text()
        assert "Answer key" in text
        assert "B" in text and "D" in text

    def test_malformed_latex_does_not_break_paper(self):
        # An unparseable expression must fall back to raw source, not raise.
        questions = [_q(r"Broken math $\frac{1}{$ still renders.")]
        data = pdf_service.build_question_paper_pdf(_meta(), questions, "Inst")
        assert data[:5] == b"%PDF-"

    def test_latex_markup_is_stripped_in_pdf_text(self):
        # The user-reported case: $1.6\text{m}$ must render as "1.6m"
        # in the PDF, matching the KaTeX-rendered Question Bank preview.
        questions = [_q("Bucket on a $1.6\\text{m}$ string.")]
        data = pdf_service.build_question_paper_pdf(_meta(), questions, "Inst")
        text = fitz.open("pdf", data)[0].get_text()
        assert "1.6m" in text
        assert "\\text" not in text
        assert "$1.6" not in text

    def test_degree_idiom_renders_cleanly(self):
        # ^\circ should become "°" with no orphaned caret.
        questions = [_q("Projected at $45^\\circ$ to horizontal.")]
        data = pdf_service.build_question_paper_pdf(_meta(), questions, "Inst")
        text = fitz.open("pdf", data)[0].get_text()
        assert "45°" in text
        assert "^°" not in text
        assert "\\circ" not in text

    def test_options_use_letter_dot_format(self):
        # Match the QB preview's "A. text" style instead of "(A) text".
        questions = [_q("Pick one.", options={"A": "alpha", "B": "beta"})]
        data = pdf_service.build_question_paper_pdf(_meta(), questions, "Inst")
        text = fitz.open("pdf", data)[0].get_text()
        assert "A." in text and "B." in text
        assert "(A)" not in text

    def test_embedded_options_in_content_stripped_when_real_options_present(self):
        # Ingested content sometimes carries options inline AND as a
        # separate dict. The inline copy gets trimmed so they only print
        # once.
        questions = [
            _q(
                "If KE increases with t, force is proportional to "
                "(a) √t (b) constant (c) t (d) 1/√t",
                options={"A": "√t", "B": "constant", "C": "t", "D": "1/√t"},
            )
        ]
        data = pdf_service.build_question_paper_pdf(_meta(), questions, "Inst")
        text = fitz.open("pdf", data)[0].get_text()
        # The inline "(a)" lowercase block is stripped from content.
        assert "(a)" not in text and "(b)" not in text
        # Proper options still print.
        assert "A." in text and "D." in text

    def test_nested_brace_sqrt_renders(self):
        # \sqrt{mkt^{-1/2}} should render with the radical glyph in the PDF.
        questions = [_q("Force is", options={"A": "\\sqrt{mkt^{-1/2}}"})]
        data = pdf_service.build_question_paper_pdf(_meta(), questions, "Inst")
        text = fitz.open("pdf", data)[0].get_text()
        assert "√" in text
        assert "\\sqrt" not in text


async def _seed_question(db_session, seed_data, content="q") -> Question:
    q = Question(
        id=uuid.uuid4(),
        content=content,
        options=None,
        correct_answer="A",
        subject_id=seed_data["subject"].id,
        difficulty="EASY",
        blooms_taxonomy="APPLY",
        source="HUMAN",
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


def _chromium_available() -> bool:
    """Whether Playwright + Chromium are installed locally. CI may not
    have run `playwright install chromium`, so the end-to-end PDF test
    skips when the browser isn't there."""
    try:
        import playwright  # noqa: F401
    except Exception:
        return False
    import os
    if os.environ.get("PLAYWRIGHT_BROWSERS_PATH"):
        return True
    import pathlib
    cache = pathlib.Path.home() / ".cache" / "ms-playwright"
    appdata = pathlib.Path(
        os.environ.get("LOCALAPPDATA", str(pathlib.Path.home()))
    ) / "ms-playwright"
    return cache.exists() or appdata.exists()


@pytest.mark.skipif(
    not _chromium_available(),
    reason="Playwright / Chromium not installed locally",
)
class TestPdfServiceEndToEnd:
    @pytest.mark.usefixtures("seed_data")
    async def test_generate_paper_pdf_from_saved_test(self, db_session, seed_data):
        test = await test_service.create_test(
            db_session,
            {
                "name": "Physics Test",
                "paper_type": "TEST",
                "batch_id": seed_data["batch"].id,
                "subject_id": seed_data["subject"].id,
            },
            seed_data["admin_user"].id,
        )
        q1 = await _seed_question(db_session, seed_data, content="What is $g$?")
        await db_session.commit()
        await repo.add_questions_to_test(
            db_session, test.id, [{"question_id": q1.id, "order": 0}]
        )
        await db_session.commit()

        filename, data = await test_service.generate_paper_pdf(
            db_session, test.id, seed_data["branch_a"].id
        )
        assert filename.endswith("-paper.pdf")
        assert data[:5] == b"%PDF-"

    @pytest.mark.usefixtures("seed_data")
    async def test_generate_pdf_rejects_empty_paper(self, db_session, seed_data):
        from fastapi import HTTPException

        test = await test_service.create_test(
            db_session,
            {
                "name": "Empty",
                "paper_type": "DPP",
                "batch_id": seed_data["batch"].id,
                "subject_id": seed_data["subject"].id,
            },
            seed_data["admin_user"].id,
        )
        await db_session.commit()
        with pytest.raises(HTTPException) as exc:
            await test_service.generate_paper_pdf(
                db_session, test.id, seed_data["branch_a"].id
            )
        assert exc.value.status_code == 400
