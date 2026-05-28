"""M3 — extract questions from an uploaded material's PDF.

This is the real ingest pipeline behind the Materials "Ingest" button.
It lifts the extraction logic that used to live only in
scripts/ingest_studymat.py and makes it callable from the request
path (via a FastAPI BackgroundTask).

Flow for one material:
1. Read the file bytes through the StorageBackend (works for local FS
   today, S3 later — no path assumptions).
2. Render each PDF page to a PNG (PyMuPDF, 2x scale for crisp math).
3. Send each page image to Gemini Vision; parse the JSON array of MCQs.
4. Insert Question rows that inherit subject / class / exam_types from
   the material, tagged source="material:<id>",
   review_status="pending_review", linked via material_id.
5. Update material.question_count + ingest_status.

Idempotent: questions are keyed by source_ref
(``<storage_key>#p<page>q<qnum>``); re-ingesting skips rows that
already exist, so a human's review edits aren't clobbered.

Blocking work (PDF render, Gemini HTTP) runs in threads via
asyncio.to_thread so the event loop stays responsive while a
BackgroundTask is extracting.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config.settings import get_settings
from app.core.database.session import async_session_factory
from app.core.storage import get_storage_backend
from app.modules.materials.models.material_models import Material
from app.modules.tests.models.test_models import Question


GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

# Only run extraction on categories that actually contain questions.
# Notes/theory PDFs have nothing to extract.
EXTRACTABLE_CATEGORIES = {"ncert", "dpp", "cpp", "topic_wise", "pyq"}

EXTRACTION_PROMPT = """\
You are an expert JEE/NEET question-bank curator extracting MCQs from a
page of a coaching-institute practice paper or DPP.

Look at the image. Return ONLY a JSON array (no prose, no markdown
fences). Each element is one multiple-choice question on this page:

[
  {
    "question_number": 12,
    "question_text": "Full text. Use $LaTeX$ for math inline, $$display$$ for centred equations.",
    "options": {"A": "...", "B": "...", "C": "...", "D": "..."},
    "correct_answer": "B",
    "explanation": "...",
    "has_diagram": false,
    "diagram_description": null,
    "difficulty": "EASY|MEDIUM|HARD",
    "blooms_taxonomy": "REMEMBER|UNDERSTAND|APPLY|ANALYZE|EVALUATE|CREATE"
  }
]

Rules:
- Only fully-visible questions (skip ones split across pages).
- Solutions / answer-key page → return [].
- No MCQs visible → return [].
- Math as LaTeX. Chemistry in standard notation (H2SO4, not LaTeX).
- correct_answer must be A, B, C, D, or null. Never guess.
- options must have exactly four keys A, B, C, D.
"""


# ── Blocking helpers (run via asyncio.to_thread) ───────────────────────────

def _get_gemini_client():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set in environment.")
    try:
        from google import genai
    except ImportError as exc:
        raise RuntimeError("google-genai SDK not installed.") from exc
    return genai.Client(api_key=api_key)


def _render_pdf_pages(data: bytes, max_pages: int | None = None) -> list[bytes]:
    """Render each PDF page to PNG bytes. Opens from an in-memory stream
    so we never need the file on disk by path."""
    import fitz  # PyMuPDF

    out: list[bytes] = []
    with fitz.open(stream=data, filetype="pdf") as doc:
        n = doc.page_count if max_pages is None else min(doc.page_count, max_pages)
        for i in range(n):
            page = doc.load_page(i)
            pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0))
            out.append(pix.tobytes("png"))
    return out


_FENCE_RE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL)


def _gemini_extract_page(client, png_bytes: bytes) -> list[dict]:
    """Send one page image to Gemini; parse the JSON array reply."""
    from google.genai import types

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[
            types.Part.from_bytes(data=png_bytes, mime_type="image/png"),
            EXTRACTION_PROMPT,
        ],
    )
    raw = (response.text or "").strip()
    m = _FENCE_RE.match(raw)
    if m:
        raw = m.group(1)
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def _norm_enum(value: str | None, allowed: set[str], default: str) -> str:
    if not value:
        return default
    v = str(value).strip().upper()
    return v if v in allowed else default


_DIFFICULTY = {"EASY", "MEDIUM", "HARD"}
_BLOOMS = {"REMEMBER", "UNDERSTAND", "APPLY", "ANALYZE", "EVALUATE", "CREATE"}


# ── Orchestration (own session; safe to run as a BackgroundTask) ────────────

async def extract_and_store(
    material_id: uuid.UUID,
    branch_id: uuid.UUID,
    *,
    max_pages: int | None = None,
) -> dict:
    """Full pipeline for one material. Opens its own DB session because
    it runs after the HTTP response (BackgroundTask) — the request
    session is already closed.

    Returns a small dict summary; also persists ingest_status on the
    material so the UI can poll for completion."""
    storage = get_storage_backend()

    async with async_session_factory() as session:
        material = (await session.execute(
            select(Material).where(
                Material.id == material_id,
                Material.branch_id == branch_id,
                Material.is_deleted == False,
            )
        )).scalar_one_or_none()
        if material is None:
            return {"ok": False, "error": "material not found"}

        if material.category not in EXTRACTABLE_CATEGORIES:
            await _mark(
                session, material,
                status="ingested", error=None,
                count=await _count_questions(session, material.id),
            )
            return {"ok": True, "skipped": "non-extractable category", "inserted": 0}

        # Cap pages to bound Gemini cost. Explicit max_pages (e.g. a
        # smoke test) wins; otherwise use the configured safety cap.
        effective_max = (
            max_pages if max_pages is not None
            else get_settings().MATERIALS_INGEST_MAX_PAGES
        )

        try:
            data = await asyncio.to_thread(storage.read, material.storage_key)
            pages = await asyncio.to_thread(_render_pdf_pages, data, effective_max)

            client = _get_gemini_client()

            # Existing source_refs for this material → skip duplicates on re-ingest.
            existing = {
                r[0] for r in (await session.execute(
                    select(Question.source_ref).where(
                        Question.material_id == material.id,
                        Question.source_ref.is_not(None),
                    )
                )).all()
            }

            # Publish total + reset done so the UI bar can render. Commit
            # so a polling request in another session sees it immediately.
            material.ingest_pages_total = len(pages)
            material.ingest_pages_done = 0
            await session.commit()

            inserted = 0
            for page_idx, png in enumerate(pages, start=1):
                rows = await asyncio.to_thread(_gemini_extract_page, client, png)
                for r in rows:
                    if not isinstance(r, dict) or not r.get("question_text"):
                        continue
                    qnum = r.get("question_number", "?")
                    source_ref = f"{material.storage_key}#p{page_idx}q{qnum}"
                    if source_ref in existing:
                        continue
                    existing.add(source_ref)

                    options = r.get("options") or {}
                    correct = (r.get("correct_answer") or "")
                    if isinstance(correct, str):
                        correct = correct.strip().upper()
                        if correct not in ("A", "B", "C", "D"):
                            correct = ""

                    session.add(Question(
                        content=r["question_text"],
                        options=json.dumps(options),
                        correct_answer=correct,
                        explanation=r.get("explanation"),
                        subject_id=material.subject_id,
                        topic_id=None,
                        difficulty=_norm_enum(r.get("difficulty"), _DIFFICULTY, "MEDIUM"),
                        blooms_taxonomy=_norm_enum(
                            r.get("blooms_taxonomy"), _BLOOMS, "APPLY"
                        ),
                        # Drop None entries — QuestionResponse.concept_tags
                        # is list[str] and a null would 500 the list endpoint.
                        concept_tags=json.dumps(
                            [t for t in (material.topic, material.class_label) if t]
                        ),
                        source=f"material:{material.id}",
                        source_ref=source_ref,
                        diagram_ref=None,
                        review_status="pending_review",
                        quality_score=None,
                        material_id=material.id,
                        exam_types=list(material.exam_types or []),
                        branch_id=material.branch_id,
                        academic_year_id=material.academic_year_id,
                        status="active",
                        is_deleted=False,
                    ))
                    inserted += 1

                # Commit progress (and this page's questions) so the UI
                # bar advances live via polling. Partial results survive
                # a mid-run crash; re-ingest is idempotent on source_ref.
                material.ingest_pages_done = page_idx
                await session.commit()

            total = await _count_questions(session, material.id)
            await _mark(session, material, status="ingested", error=None, count=total)
            return {"ok": True, "inserted": inserted, "pages": len(pages), "total": total}

        except Exception as exc:  # noqa: BLE001
            await session.rollback()
            # Record the failure in a fresh transaction.
            await _mark_failed(material_id, branch_id, str(exc))
            return {"ok": False, "error": str(exc)}


async def _count_questions(session: AsyncSession, material_id: uuid.UUID) -> int:
    return (await session.execute(
        select(func.count(Question.id)).where(
            Question.material_id == material_id,
            Question.is_deleted == False,
        )
    )).scalar_one()


async def _mark(
    session: AsyncSession,
    material: Material,
    *,
    status: str,
    error: str | None,
    count: int,
) -> None:
    material.ingest_status = status
    material.ingest_error = error
    material.question_count = count
    await session.commit()


async def _mark_failed(
    material_id: uuid.UUID, branch_id: uuid.UUID, error: str
) -> None:
    async with async_session_factory() as session:
        material = (await session.execute(
            select(Material).where(Material.id == material_id)
        )).scalar_one_or_none()
        if material is None:
            return
        material.ingest_status = "ingest_failed"
        material.ingest_error = error[:1000]
        await session.commit()
