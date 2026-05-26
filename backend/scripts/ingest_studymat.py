"""Ingest study_material PDFs into the questions table using Gemini Vision.

Reads PDFs from ``study_material/extracted/<subject>/class-<N>/<chapter>/``
(produced by ``organize_study_material.py``), pages-as-images them with
PyMuPDF, sends each page to Gemini Vision with a structured-output
prompt, then writes rows to the ``questions`` table with
``review_status='pending_review'`` so the admin queue can validate them
before they're usable for paper composition.

Usage:
    cd backend
    # Dry-run: walk the tree, count pages, no API calls, no DB writes.
    python scripts/ingest_studymat.py --dry-run

    # Process a single PDF (smoke test):
    python scripts/ingest_studymat.py --only "physics/class-11/work-energy-power"

    # Process everything (uses GEMINI_API_KEY from .env):
    python scripts/ingest_studymat.py

Flags:
    --dry-run       List the work, don't call Gemini or touch the DB
    --only PATH     Substring filter on relative file path
    --limit N       Stop after N files (handy for first-pass validation)
    --pages N       Max pages per file (default: all)
    --resume        Skip files already ingested (tracked via Question.source_ref)
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import io
import json
import os
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

try:
    import fitz  # PyMuPDF
except ImportError:
    print("ERROR: PyMuPDF not installed. Run: pip install pymupdf")
    sys.exit(1)

# Add backend/ to sys.path so `app.*` imports resolve when this script
# is run directly (python scripts/ingest_studymat.py).
_HERE = Path(__file__).resolve().parent
_BACKEND = _HERE.parent
sys.path.insert(0, str(_BACKEND))

# Pre-load every model module so SQLAlchemy can resolve cross-table
# ForeignKeys before the ORM builds INSERT statements. Without this
# the questions.branch_id → branch.id FK fails to bind at first
# session.add() call. Mirrors seed_admin.py's approach.
from app.modules.auth.models import auth_models  # noqa: F401,E402
from app.modules.academic.models import academic_models  # noqa: F401,E402
from app.modules.batch.models import batch_models  # noqa: F401,E402
from app.modules.classroom.models import classroom_models  # noqa: F401,E402
from app.modules.student.models import student_models  # noqa: F401,E402
from app.modules.teacher.models import teacher_models  # noqa: F401,E402
from app.modules.lectures.models import lecture_models  # noqa: F401,E402
from app.modules.tests.models import test_models  # noqa: F401,E402
from app.modules.audit.models import audit_models  # noqa: F401,E402
from app.modules.attendance.models import attendance_models  # noqa: F401,E402

# Load backend/.env into os.environ so GEMINI_API_KEY is available
# when the script is invoked directly. Falls back to system env vars.
_BACKEND_ENV = _BACKEND / ".env"
if _BACKEND_ENV.exists():
    for line in _BACKEND_ENV.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
EXTRACTED = REPO_ROOT / "study_material" / "extracted"
UPLOADS = REPO_ROOT / os.environ.get("UPLOADS_DIR", "uploads") / "diagrams"


# ── Gemini provider (lazy import so --dry-run works without the SDK) ────────

def get_gemini_client():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY not set in environment. "
            "Add it to backend/.env (or use --dry-run)."
        )
    try:
        from google import genai
    except ImportError:
        raise RuntimeError(
            "google-genai SDK not installed. Run: pip install google-genai"
        )
    return genai.Client(api_key=api_key)


GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

EXTRACTION_PROMPT = """\
You are an expert JEE/NEET question-bank curator extracting MCQs from a
page of a coaching-institute practice paper or DPP.

Look at the image. Return ONLY a JSON array (no prose, no markdown
fences). Each element is one multiple-choice question on this page:

[
  {
    "question_number": 12,
    "question_text": "Full text. Use $LaTeX$ for math expressions inline. Use $$display$$ for centred equations.",
    "options": {"A": "...", "B": "...", "C": "...", "D": "..."},
    "correct_answer": "B",     // null if not visible
    "explanation": "...",       // null if not on this page
    "has_diagram": false,       // true if the question depends on a figure/graph/circuit
    "diagram_description": null, // brief text description if has_diagram=true
    "difficulty": "EASY|MEDIUM|HARD",   // best guess
    "blooms_taxonomy": "REMEMBER|UNDERSTAND|APPLY|ANALYZE|EVALUATE|CREATE"
  }
]

Rules:
- Only include questions that are fully visible on this page (skip
  partial questions split across pages).
- If the page is a solutions/answer-key page, return an empty array [].
- If no MCQs visible, return [].
- Convert mathematical expressions to LaTeX. Keep chemistry equations
  in standard notation (e.g. H2SO4, not LaTeX).
- correct_answer must be one of: A, B, C, D, or null. Never guess.
- options must have exactly four keys A, B, C, D.
"""


# ── PDF helpers ─────────────────────────────────────────────────────────────

def render_pdf_pages(pdf_path: Path, max_pages: int | None = None) -> list[bytes]:
    """Render each PDF page as PNG bytes. Returns one bytes-blob per page."""
    out: list[bytes] = []
    with fitz.open(pdf_path) as doc:
        n = doc.page_count if max_pages is None else min(doc.page_count, max_pages)
        for i in range(n):
            page = doc.load_page(i)
            # 2x scale for clear OCR of math + small text.
            pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0))
            out.append(pix.tobytes("png"))
    return out


def hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:16]


# ── Gemini call + JSON cleanup ──────────────────────────────────────────────

def gemini_extract_page(client, png_bytes: bytes) -> list[dict]:
    """Send one page image to Gemini, parse the JSON array reply."""
    from google.genai import types  # local import keeps --dry-run light

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[
            types.Part.from_bytes(data=png_bytes, mime_type="image/png"),
            EXTRACTION_PROMPT,
        ],
    )
    raw = (response.text or "").strip()
    # Tolerate models that fence the response despite our instructions.
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", raw, re.DOTALL)
    if fence:
        raw = fence.group(1)
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Gemini returned non-JSON: {raw[:300]}") from exc
    if not isinstance(data, list):
        return []
    return data


# ── Path → context (subject, class, chapter) ────────────────────────────────

def classify_path(pdf: Path) -> dict:
    """Derive subject / standard / chapter slug from extracted/-tree path."""
    try:
        rel = pdf.relative_to(EXTRACTED)
    except ValueError:
        return {"subject": None, "standard": None, "chapter_slug": None}
    parts = rel.parts
    subject = parts[0] if parts else None
    standard = None
    chapter_slug = None
    for p in parts[1:]:
        if p.startswith("class-"):
            tail = p[len("class-"):]
            if tail in {"11", "12", "mixed", "unknown"}:
                standard = tail
        elif p == "_docx":
            continue
        elif chapter_slug is None:
            chapter_slug = p
    return {
        "subject": subject,
        "standard": standard,
        "chapter_slug": chapter_slug,
    }


# ── DB insertion ────────────────────────────────────────────────────────────

async def insert_questions(rows: list[dict], pdf_relpath: str) -> int:
    """Insert extracted questions into the questions table.

    Best-effort: subject_id and topic_id resolution is deferred to the
    admin review step. For now we store the chapter slug + raw subject
    in concept_tags and leave the FKs NULL where unknown — the review
    queue UI lets a human map them onto real topics.
    """
    from app.core.database.session import async_session_factory
    from app.modules.academic.models.academic_models import Subject
    from app.modules.tests.models.test_models import Question
    from sqlalchemy import select

    if not rows:
        return 0

    written = 0
    async with async_session_factory() as session:
        # Pick the first matching subject in the branch — coarse but
        # acceptable; admin can re-assign on review.
        first_subject = await session.execute(
            select(Subject).where(Subject.is_deleted == False).limit(1)
        )
        default_subject = first_subject.scalar_one_or_none()
        if default_subject is None:
            print("  ⚠ no subjects in DB, skipping insert (run seed first)")
            return 0

        for r in rows:
            q = Question(
                content=r["question_text"],
                options=json.dumps(r.get("options") or {}),
                correct_answer=(r.get("correct_answer") or ""),
                explanation=r.get("explanation"),
                subject_id=default_subject.id,
                topic_id=None,  # admin maps in review queue
                difficulty=(r.get("difficulty") or "MEDIUM").upper(),
                blooms_taxonomy=(r.get("blooms_taxonomy") or "APPLY").upper(),
                concept_tags=json.dumps([r.get("subject_hint"), r.get("chapter_slug")]),
                source=f"studymat:{r.get('source_zip', '')}",
                source_ref=f"{pdf_relpath}#p{r['page']}q{r.get('question_number', '?')}",
                diagram_ref=r.get("diagram_ref"),
                review_status="pending_review",
                quality_score=None,
                branch_id=default_subject.branch_id,
                academic_year_id=default_subject.academic_year_id,
                status="active",
                is_deleted=False,
            )
            session.add(q)
            written += 1
        await session.commit()
    return written


async def already_ingested(pdf_relpath: str) -> bool:
    from app.core.database.session import async_session_factory
    from app.modules.tests.models.test_models import Question
    from sqlalchemy import select

    async with async_session_factory() as session:
        result = await session.execute(
            select(Question.id).where(
                Question.source_ref.like(f"{pdf_relpath}#%"),
                Question.is_deleted == False,
            ).limit(1)
        )
        return result.scalar_one_or_none() is not None


# ── Main driver ─────────────────────────────────────────────────────────────

async def run(args: argparse.Namespace) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:
        pass

    if not EXTRACTED.exists():
        print(f"ERROR: {EXTRACTED} does not exist. Run organize_study_material.py first.")
        return 1

    UPLOADS.mkdir(parents=True, exist_ok=True)

    # Walk every PDF under extracted/ (skip _docx siblings).
    pdfs: list[Path] = []
    for p in sorted(EXTRACTED.rglob("*.pdf")):
        rel = p.relative_to(EXTRACTED)
        if "_docx" in rel.parts:
            continue
        if args.only and args.only.lower() not in str(rel).lower():
            continue
        pdfs.append(p)
        if args.limit and len(pdfs) >= args.limit:
            break

    if not pdfs:
        print("No PDFs matched.")
        return 1

    print(f"Found {len(pdfs)} PDF(s).")

    if args.dry_run:
        print("\n[dry-run] would process:")
        total_pages = 0
        for p in pdfs:
            try:
                with fitz.open(p) as doc:
                    pages = doc.page_count
            except Exception as exc:
                pages = -1
            rel = p.relative_to(EXTRACTED)
            cls = classify_path(p)
            tag = f"{cls['subject']}/{cls['standard']}/{cls['chapter_slug']}"
            print(f"  {pages:>3}p  {tag:<60}  {rel}")
            if pages > 0:
                total_pages += pages
        # Rough Gemini cost: ~$0.0001 per image (gemini-2.0-flash).
        est_cost = total_pages * 0.0001
        print(f"\nTotal pages: {total_pages}  ·  est Gemini spend ~${est_cost:.2f}")
        return 0

    client = get_gemini_client()

    total_questions = 0
    total_pages = 0
    for pi, pdf in enumerate(pdfs, start=1):
        rel = str(pdf.relative_to(EXTRACTED)).replace("\\", "/")
        cls = classify_path(pdf)

        if args.resume:
            if await already_ingested(rel):
                print(f"[{pi}/{len(pdfs)}] skip (already ingested): {rel}")
                continue

        print(f"[{pi}/{len(pdfs)}] {rel}  ({cls['subject']}/{cls['standard']}/{cls['chapter_slug']})")
        try:
            pages = render_pdf_pages(pdf, max_pages=args.pages)
        except Exception as exc:
            print(f"  ✗ failed to render: {exc}")
            continue

        rows_for_pdf: list[dict] = []
        for page_idx, png in enumerate(pages, start=1):
            try:
                extracted = gemini_extract_page(client, png)
            except Exception as exc:
                print(f"  ✗ page {page_idx} Gemini error: {exc}")
                continue
            for q in extracted:
                if not q.get("question_text"):
                    continue
                q["page"] = page_idx
                q["subject_hint"] = cls.get("subject")
                q["chapter_slug"] = cls.get("chapter_slug")
                q["source_zip"] = pdf.stem.split("--", 1)[0] if "--" in pdf.stem else ""
                # Diagram extraction: skipped in v1 (need bounding-box
                # output from Gemini to crop accurately). Logged as TODO.
                q["diagram_ref"] = None
                rows_for_pdf.append(q)
            total_pages += 1

        written = await insert_questions(rows_for_pdf, rel)
        total_questions += written
        print(f"  ✓ {len(rows_for_pdf)} questions extracted, {written} written")

    print(f"\nDone. {total_pages} pages processed, {total_questions} questions ingested.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--only", default=None, help="Substring filter on path")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--pages", type=int, default=None)
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip PDFs already represented in Question.source_ref",
    )
    args = parser.parse_args()
    return asyncio.run(run(args))


if __name__ == "__main__":
    sys.exit(main())
