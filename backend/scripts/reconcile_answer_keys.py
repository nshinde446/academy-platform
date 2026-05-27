"""DEPRECATED — kept as reference. Use scripts/extract_keys_ai.py instead.

This regex-based harvester only handles inline answer keys of the form
``<n>. (<letter>) ...`` and misses tabular/grid layouts where PyMuPDF
flattens cells across columns. The AI-based replacement
(extract_keys_ai.py) sends the whole PDF to Gemini and handles every
layout uniformly.

------------------------------------------------------------------------

Backfill empty correct_answer on study-material questions.

Reads source PDFs from study_material/extracted/, scans for answer-key
blocks (typical format: ``<n>. (<letter>) <explanation>`` or
``<n>. <letter>``), and updates Question rows where the question number
in source_ref matches an answer-key entry unambiguously.

What it does NOT do:
- It does not guess. Empty answers stay empty for AI fallback (Phase H3).
- It does not touch review_status. Caller decides whether to re-queue.
- It does not modify questions that already have a correct_answer set.

Usage:
    cd backend
    python scripts/reconcile_answer_keys.py --dry-run
    python scripts/reconcile_answer_keys.py --only "physics/class-12"
    python scripts/reconcile_answer_keys.py --doc "physics/class-12/current-electricity/ncert-topic-wise-mcq--CURRENT ELECTRICITY.pdf"

Flags:
    --dry-run         No DB writes; just report what would change.
    --only PATH       Substring filter on source_ref's doc path.
    --doc PATH        Process exactly this one doc (relative to extracted/).
    --limit N         Process at most N docs.
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
from collections import defaultdict
from pathlib import Path

try:
    import fitz  # PyMuPDF
except ImportError:
    print("ERROR: PyMuPDF not installed. Run: pip install pymupdf")
    sys.exit(1)

_HERE = Path(__file__).resolve().parent
_BACKEND = _HERE.parent
sys.path.insert(0, str(_BACKEND))

# Pre-load model modules so SQLAlchemy resolves cross-table FKs.
from app.modules.auth.models import auth_models  # noqa: F401,E402
from app.modules.academic.models import academic_models  # noqa: F401,E402
from app.modules.batch.models import batch_models  # noqa: F401,E402
from app.modules.tests.models import test_models  # noqa: F401,E402

from app.core.database.session import async_session_factory  # noqa: E402
from app.modules.tests.models.test_models import Question  # noqa: E402
from sqlalchemy import select  # noqa: E402


STUDY_MATERIAL = _BACKEND.parent / "study_material" / "extracted"

# Catches:  "1. (a) text..."   "23. (B) ..."   "5. . (c) ..."   "12. a"
# Tolerant of extra dots / whitespace produced by PDF text extraction.
ANSWER_KEY_RE = re.compile(
    r"^\s*(\d{1,3})\s*\.\s*\.?\s*\(?\s*([a-dA-D])\s*\)?",
    re.MULTILINE,
)

# Source_ref shape:  "<subject>/class-<N>/<chapter>/<file>.pdf#p<page>q<qnum>"
SOURCE_REF_RE = re.compile(r"^(.+?)#p(\d+)q(\d+)$")


def parse_answer_pages(pdf_path: Path, threshold: int = 3) -> dict[int, str]:
    """Walk every page; collect answer-key (qnum, letter) pairs from
    pages that have at least ``threshold`` matches. Returns a dict
    {qnum: letter} where we keep only unambiguous numbers (qnum that
    appears exactly once across all collected pairs)."""
    seen: dict[int, list[str]] = defaultdict(list)
    with fitz.open(pdf_path) as doc:
        for i in range(doc.page_count):
            text = doc.load_page(i).get_text()
            matches = ANSWER_KEY_RE.findall(text)
            if len(matches) < threshold:
                continue
            for qnum_str, letter in matches:
                seen[int(qnum_str)].append(letter.upper())

    # Resolve: keep only entries where all sightings agree (or only one
    # sighting). If a qnum appears multiple times with different
    # letters, it's ambiguous (sections restart numbering) — skip.
    unambiguous: dict[int, str] = {}
    for qnum, letters in seen.items():
        unique = set(letters)
        if len(unique) == 1:
            unambiguous[qnum] = next(iter(unique))
    return unambiguous


def find_pdf(doc_rel: str) -> Path | None:
    """Resolve a source_ref's doc-path component (e.g.
    ``physics/class-12/current-electricity/ncert-topic-wise-mcq--CURRENT ELECTRICITY.pdf``)
    to an actual file under study_material/extracted/."""
    p = STUDY_MATERIAL / doc_rel
    if p.exists():
        return p
    # Some legacy refs may have minor path differences (capitalization,
    # spaces); fall back to a case-insensitive glob in the same dir.
    parent = p.parent
    if not parent.exists():
        return None
    target = p.name.lower()
    for candidate in parent.iterdir():
        if candidate.name.lower() == target:
            return candidate
    return None


async def reconcile(
    only: str | None = None,
    one_doc: str | None = None,
    limit: int | None = None,
    dry_run: bool = False,
) -> None:
    async with async_session_factory() as s:
        # Pull every studymat question that's missing an answer.
        result = await s.execute(
            select(Question.id, Question.source_ref).where(
                Question.source.like("studymat:%"),
                Question.is_deleted == False,
                (Question.correct_answer == None) | (Question.correct_answer == ""),
            )
        )
        rows = result.all()

        # Group by source doc.
        by_doc: dict[str, list[tuple[object, int]]] = defaultdict(list)
        for qid, ref in rows:
            if not ref:
                continue
            m = SOURCE_REF_RE.match(ref)
            if not m:
                continue
            doc_path, _page, qnum = m.group(1), int(m.group(2)), int(m.group(3))
            if one_doc and doc_path != one_doc:
                continue
            if only and only not in doc_path:
                continue
            by_doc[doc_path].append((qid, qnum))

        doc_list = sorted(by_doc.keys())
        if limit is not None:
            doc_list = doc_list[:limit]

        # Totals for the closing report.
        total_docs = len(doc_list)
        docs_with_key = 0
        total_questions = sum(len(by_doc[d]) for d in doc_list)
        total_updated = 0
        per_doc_unmatched: list[tuple[str, int, int]] = []

        for idx, doc_path in enumerate(doc_list, start=1):
            questions = by_doc[doc_path]
            pdf = find_pdf(doc_path)
            if pdf is None:
                print(f"  [{idx}/{total_docs}] SKIP (file not found): {doc_path}")
                per_doc_unmatched.append((doc_path, len(questions), 0))
                continue

            try:
                key_map = parse_answer_pages(pdf)
            except Exception as exc:  # noqa: BLE001
                print(f"  [{idx}/{total_docs}] ERR  {doc_path}: {exc}")
                continue

            if not key_map:
                print(
                    f"  [{idx}/{total_docs}] no key  {doc_path} "
                    f"({len(questions)} pending)"
                )
                per_doc_unmatched.append((doc_path, len(questions), 0))
                continue

            docs_with_key += 1
            matched = 0
            for qid, qnum in questions:
                letter = key_map.get(qnum)
                if letter is None:
                    continue
                matched += 1
                if not dry_run:
                    await s.execute(
                        Question.__table__.update()
                        .where(Question.id == qid)
                        .values(correct_answer=letter)
                    )
            total_updated += matched
            unmatched = len(questions) - matched
            per_doc_unmatched.append((doc_path, len(questions), matched))
            print(
                f"  [{idx}/{total_docs}] {pdf.name}: "
                f"key={len(key_map)}, matched={matched}/{len(questions)}, "
                f"unmatched={unmatched}"
            )

        if not dry_run:
            await s.commit()

        # Summary.
        print()
        print("=" * 60)
        print("RECONCILIATION SUMMARY")
        print(f"  Docs scanned:           {total_docs}")
        print(f"  Docs with answer key:   {docs_with_key}")
        print(f"  Questions with gaps:    {total_questions}")
        print(
            f"  Questions backfilled:   {total_updated} "
            f"({100 * total_updated / max(total_questions, 1):.0f}%)"
        )
        print(
            f"  Remaining gaps for AI:  "
            f"{total_questions - total_updated} (Phase H3)"
        )
        if dry_run:
            print()
            print("  (dry-run: no DB writes)")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true", help="No DB writes")
    p.add_argument("--only", default=None, help="Substring filter on doc path")
    p.add_argument("--doc", default=None, help="Exact doc path (relative to extracted/)")
    p.add_argument("--limit", type=int, default=None, help="Process at most N docs")
    args = p.parse_args()

    asyncio.run(
        reconcile(
            only=args.only,
            one_doc=args.doc,
            limit=args.limit,
            dry_run=args.dry_run,
        )
    )


if __name__ == "__main__":
    main()
