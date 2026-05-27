"""Phase H2 (AI rewrite) — extract answer keys per PDF using Gemini.

For each studymat PDF that still has questions with empty
correct_answer, send the whole PDF to Gemini and ask it to extract every
answer-key section it can find. Map results back to questions via the
qnum component of source_ref.

This replaces the regex-based reconcile_answer_keys.py (kept as a
reference). The AI version handles any layout — inline ``1. (a)``,
multi-column tabular grids, sectioned exercises where qnums restart —
without us having to hand-write a regex per format.

How it disambiguates sections:
- A PDF may have Exercise 1 (q1-120) and Exercise 2 (q1-36). Gemini
  returns each section separately.
- For a pending question with qnum=N, we look across every section. If
  exactly one letter shows up (either N is unique to one section, or
  all sections agree), we save it. If sections disagree, we leave it
  for the per-question H3 fallback to handle with question text.

Usage:
    cd backend
    python scripts/extract_keys_ai.py --dry-run
    python scripts/extract_keys_ai.py --only "physics/class-12"
    python scripts/extract_keys_ai.py --doc "physics/class-11/work-energy-power/ncert-topic-wise-mcq--Work, Energy & Power.pdf"
    python scripts/extract_keys_ai.py --limit 1

Flags:
    --dry-run   No DB writes / no AI calls; just list what would run.
    --only PATH Substring filter on source_ref's doc path.
    --doc PATH  Process exactly this one doc (relative to extracted/).
    --limit N   Process at most N PDFs.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_BACKEND = _HERE.parent
sys.path.insert(0, str(_BACKEND))

# Load backend/.env into os.environ so GEMINI_API_KEY is available
# when the script is invoked directly.
_BACKEND_ENV = _BACKEND / ".env"
if _BACKEND_ENV.exists():
    for line in _BACKEND_ENV.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

# Pre-load model modules so SQLAlchemy resolves cross-table FKs.
from app.modules.auth.models import auth_models  # noqa: F401,E402
from app.modules.academic.models import academic_models  # noqa: F401,E402
from app.modules.batch.models import batch_models  # noqa: F401,E402
from app.modules.tests.models import test_models  # noqa: F401,E402

from app.core.database.session import async_session_factory  # noqa: E402
from app.modules.tests.models.test_models import Question  # noqa: E402
from sqlalchemy import select  # noqa: E402


STUDY_MATERIAL = _BACKEND.parent / "study_material" / "extracted"
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
# Gemini accepts PDFs inline up to ~20MB; above that switch to Files API.
INLINE_PDF_MAX = 18 * 1024 * 1024

# source_ref shape: "<subject>/class-<N>/<chapter>/<file>.pdf#p<page>q<qnum>"
SOURCE_REF_RE = re.compile(r"^(.+?)#p(\d+)q(\d+)$")


EXTRACT_PROMPT = """\
You are reading an NCERT/coaching workbook PDF. Find every answer-key
section in this document and return them as structured JSON.

Answer-key sections usually appear near the end and may be labeled
"Exercise 1", "Exercise 2", "NEET Previous Year", "Hints and Solutions",
"Answers", etc. Their layout varies — inline ("1. (a) explanation..."),
tabular grids, multi-column tables. Question numbers commonly restart
between sections.

Read EVERY page. Extract every (question_number, letter) pair you can
read confidently. Be exhaustive within each section.

Return ONLY a JSON object:

{"sections": [{"label": "<section name>", "answers": {"<qnum>": "<letter>", ...}}, ...]}

Rules:
- Letters MUST be uppercase A, B, C, or D. Skip anything else.
- Question numbers MUST be integers as strings ("1", "23", "120").
- Skip any pair you cannot read confidently — omit, don't guess.
- Order sections as they appear in the document.
- If no answer key exists, return {"sections": []}.
"""


def make_client():
    """Lazy import + construct Gemini client. Kept inside a function so
    --dry-run doesn't require the SDK."""
    try:
        from google import genai
    except ImportError:
        raise SystemExit(
            "google-genai SDK not installed. Run: pip install google-genai"
        )
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise SystemExit("GEMINI_API_KEY missing — set it in backend/.env")
    return genai.Client(api_key=api_key)


def parse_response(raw: str) -> list[dict]:
    """Return list of {label, answers: {qnum: letter}} or [] on failure."""
    text = (raw or "").strip()
    # Strip markdown fences if the model added them despite the system
    # instructions (defensive — response_mime_type=json should prevent).
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []
    sections = data.get("sections") or []
    cleaned = []
    for sec in sections:
        if not isinstance(sec, dict):
            continue
        answers_raw = sec.get("answers") or {}
        if not isinstance(answers_raw, dict):
            continue
        answers: dict[int, str] = {}
        for qk, lv in answers_raw.items():
            try:
                qnum = int(str(qk).strip())
            except (ValueError, TypeError):
                continue
            if not isinstance(lv, str):
                continue
            letter = lv.strip().upper()
            if letter not in ("A", "B", "C", "D"):
                continue
            answers[qnum] = letter
        if answers:
            cleaned.append({"label": str(sec.get("label", "?")), "answers": answers})
    return cleaned


def extract_keys(client, pdf_path: Path) -> list[dict]:
    """Ask Gemini for the structured answer key. Returns list of
    {label, answers: {qnum: letter}}."""
    from google.genai import types

    size = pdf_path.stat().st_size
    if size <= INLINE_PDF_MAX:
        part = types.Part.from_bytes(
            data=pdf_path.read_bytes(),
            mime_type="application/pdf",
        )
        contents = [part, EXTRACT_PROMPT]
    else:
        uploaded = client.files.upload(file=str(pdf_path))
        contents = [uploaded, EXTRACT_PROMPT]

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=contents,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.0,
            max_output_tokens=8192,
        ),
    )
    return parse_response(response.text or "")


def resolve(sections: list[dict]) -> tuple[dict[int, str], list[int]]:
    """Collapse sections into {qnum: letter} for qnums whose letter is
    unambiguous across sightings. Returns (unambiguous, conflicting)."""
    seen: dict[int, set[str]] = defaultdict(set)
    for sec in sections:
        for qnum, letter in sec["answers"].items():
            seen[qnum].add(letter)
    unambiguous: dict[int, str] = {}
    conflicts: list[int] = []
    for qnum, letters in seen.items():
        if len(letters) == 1:
            unambiguous[qnum] = next(iter(letters))
        else:
            conflicts.append(qnum)
    return unambiguous, conflicts


def find_pdf(doc_rel: str) -> Path | None:
    p = STUDY_MATERIAL / doc_rel
    if p.exists():
        return p
    parent = p.parent
    if not parent.exists():
        return None
    target = p.name.lower()
    for candidate in parent.iterdir():
        if candidate.name.lower() == target:
            return candidate
    return None


async def run(
    only: str | None,
    one_doc: str | None,
    limit: int | None,
    dry_run: bool,
) -> None:
    client = None if dry_run else make_client()

    async with async_session_factory() as s:
        result = await s.execute(
            select(Question.id, Question.source_ref).where(
                Question.source.like("studymat:%"),
                Question.is_deleted == False,
                (Question.correct_answer == None) | (Question.correct_answer == ""),
            )
        )
        rows = result.all()

        by_doc: dict[str, list[tuple[object, int]]] = defaultdict(list)
        for qid, ref in rows:
            if not ref:
                continue
            m = SOURCE_REF_RE.match(ref)
            if not m:
                continue
            doc_path, _, qnum = m.group(1), int(m.group(2)), int(m.group(3))
            if one_doc and doc_path != one_doc:
                continue
            if only and only not in doc_path:
                continue
            by_doc[doc_path].append((qid, qnum))

        doc_list = sorted(by_doc.keys())
        if limit is not None:
            doc_list = doc_list[:limit]

        total_docs = len(doc_list)
        total_questions = sum(len(by_doc[d]) for d in doc_list)
        total_updated = 0
        docs_with_key = 0

        for idx, doc_path in enumerate(doc_list, start=1):
            questions = by_doc[doc_path]
            pdf = find_pdf(doc_path)
            if pdf is None:
                print(f"  [{idx}/{total_docs}] SKIP (file not found): {doc_path}")
                continue

            if dry_run:
                print(
                    f"  [{idx}/{total_docs}] would extract {pdf.name} "
                    f"({len(questions)} pending)"
                )
                continue

            try:
                sections = extract_keys(client, pdf)
            except Exception as exc:  # noqa: BLE001
                print(f"  [{idx}/{total_docs}] ERR {doc_path}: {exc}")
                continue

            if not sections:
                print(
                    f"  [{idx}/{total_docs}] no key  {pdf.name} "
                    f"({len(questions)} pending)"
                )
                continue

            docs_with_key += 1
            key_map, conflicts = resolve(sections)
            matched = 0
            for qid, qnum in questions:
                letter = key_map.get(qnum)
                if letter is None:
                    continue
                matched += 1
                await s.execute(
                    Question.__table__.update()
                    .where(Question.id == qid)
                    .values(correct_answer=letter)
                )
            total_updated += matched
            section_summary = ", ".join(
                f"{sec['label']}={len(sec['answers'])}" for sec in sections
            )
            print(
                f"  [{idx}/{total_docs}] {pdf.name}: "
                f"sections=[{section_summary}], "
                f"unambig={len(key_map)}, conflicts={len(conflicts)}, "
                f"matched={matched}/{len(questions)}"
            )

        if not dry_run:
            await s.commit()

        print()
        print("=" * 60)
        print("AI EXTRACTION SUMMARY")
        print(f"  Docs scanned:          {total_docs}")
        print(f"  Docs with answer key:  {docs_with_key}")
        print(f"  Questions with gaps:   {total_questions}")
        pct = 100 * total_updated / max(total_questions, 1)
        print(f"  Questions backfilled:  {total_updated} ({pct:.0f}%)")
        print(
            f"  Remaining for H3 AI:   {total_questions - total_updated}"
        )
        if dry_run:
            print("  (dry-run: no AI calls, no DB writes)")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--only", default=None)
    p.add_argument("--doc", default=None)
    p.add_argument("--limit", type=int, default=None)
    args = p.parse_args()
    asyncio.run(
        run(
            only=args.only,
            one_doc=args.doc,
            limit=args.limit,
            dry_run=args.dry_run,
        )
    )


if __name__ == "__main__":
    main()
