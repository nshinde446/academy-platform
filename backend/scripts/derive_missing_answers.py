"""Phase H3 — AI fallback for questions the answer-key harvester
couldn't resolve.

For each studymat question that still has correct_answer empty after
reconcile_answer_keys.py has run, send (question_text + options) to
Gemini and ask which option is correct. Save only when the model
returns confidence >= MIN_CONFIDENCE.

We use Gemini text-only (no vision) here because the question +
options are already extracted as text in the DB — no need to round-
trip the PDF image again.

Usage:
    cd backend
    python scripts/derive_missing_answers.py --dry-run
    python scripts/derive_missing_answers.py --limit 25
    python scripts/derive_missing_answers.py --min-confidence 0.8

Flags:
    --dry-run             No DB writes; just report.
    --limit N             Stop after N questions (handy for first-pass).
    --min-confidence X    Save only when AI is at least this confident
                          (default 0.7).
    --only PATH           Substring filter on source_ref doc path.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_BACKEND = _HERE.parent
sys.path.insert(0, str(_BACKEND))

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

# Pre-load model modules so SQLAlchemy resolves cross-table FKs.
from app.modules.auth.models import auth_models  # noqa: F401,E402
from app.modules.academic.models import academic_models  # noqa: F401,E402
from app.modules.batch.models import batch_models  # noqa: F401,E402
from app.modules.tests.models import test_models  # noqa: F401,E402

from app.core.database.session import async_session_factory  # noqa: E402
from app.modules.tests.models.test_models import Question  # noqa: E402
from sqlalchemy import select  # noqa: E402


GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
MIN_CONFIDENCE_DEFAULT = 0.7

DERIVE_PROMPT = """\
You are an expert subject matter teacher (Physics / Chemistry / Biology
/ Mathematics) for JEE/NEET prep. The following multiple-choice
question was extracted from an NCERT-style coaching workbook, but the
answer key wasn't captured during ingest.

Identify the correct option. Be honest about uncertainty — if you
aren't sure, return null.

QUESTION:
{content}

OPTIONS:
{options_block}

Return ONLY a JSON object on a single line (no prose, no markdown
fences):

{{"answer": "A" | "B" | "C" | "D" | null, "confidence": <float 0..1>}}

Rules:
- "answer" must be A, B, C, D, or null.
- "confidence" is YOUR honest probability the answer is right.
- If the question depends on a diagram/figure not in the text, return
  null with low confidence.
- If options look broken (cut off mid-string, duplicate text), return
  null.
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


_FENCE_RE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL)


def parse_response(raw: str) -> tuple[str | None, float | None]:
    """Return (letter, confidence) or (None, None) when the response
    is unparseable / model declined."""
    text = (raw or "").strip()
    m = _FENCE_RE.match(text)
    if m:
        text = m.group(1)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None, None
    letter = data.get("answer")
    conf = data.get("confidence")
    if isinstance(letter, str):
        letter = letter.strip().upper()
        if letter not in ("A", "B", "C", "D"):
            letter = None
    else:
        letter = None
    if not isinstance(conf, (int, float)):
        conf = None
    return letter, conf


def derive_one(client, content: str, options: dict[str, str]) -> tuple[str | None, float | None]:
    opt_lines = "\n".join(f"{k}. {v}" for k, v in sorted(options.items()))
    prompt = DERIVE_PROMPT.format(content=content, options_block=opt_lines)
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[prompt],
    )
    return parse_response(response.text or "")


async def run(
    only: str | None,
    limit: int | None,
    min_confidence: float,
    dry_run: bool,
) -> None:
    client = None if dry_run else make_client()

    async with async_session_factory() as s:
        stmt = select(Question).where(
            Question.source.like("studymat:%"),
            Question.is_deleted == False,
            (Question.correct_answer == None) | (Question.correct_answer == ""),
        )
        rows = (await s.execute(stmt)).scalars().all()

        if only:
            rows = [
                q for q in rows
                if q.source_ref and only in q.source_ref
            ]
        if limit is not None:
            rows = rows[:limit]

        print(f"Processing {len(rows)} questions (min_confidence={min_confidence})…")

        saved = 0
        low_conf = 0
        unparseable = 0
        no_options = 0
        errors = 0

        for i, q in enumerate(rows, start=1):
            options_raw = q.options
            try:
                options = (
                    json.loads(options_raw)
                    if isinstance(options_raw, str)
                    else (options_raw or {})
                )
            except (json.JSONDecodeError, TypeError):
                options = {}
            if not options or len(options) < 2:
                no_options += 1
                continue

            if dry_run:
                print(f"  [{i}/{len(rows)}] would derive: {q.source_ref}")
                continue

            try:
                letter, conf = derive_one(client, q.content, options)
            except Exception as exc:  # noqa: BLE001
                errors += 1
                print(f"  [{i}/{len(rows)}] ERR {q.source_ref}: {exc}")
                continue

            if letter is None or conf is None:
                unparseable += 1
                print(f"  [{i}/{len(rows)}] declined: {q.source_ref}")
                continue
            if conf < min_confidence:
                low_conf += 1
                print(
                    f"  [{i}/{len(rows)}] low conf {conf:.2f}: {q.source_ref}"
                )
                continue

            await s.execute(
                Question.__table__.update()
                .where(Question.id == q.id)
                .values(correct_answer=letter, quality_score=conf)
            )
            saved += 1
            print(
                f"  [{i}/{len(rows)}] saved {letter} (conf={conf:.2f}): "
                f"{q.source_ref}"
            )

        if not dry_run:
            await s.commit()

        print()
        print("=" * 60)
        print("DERIVE SUMMARY")
        print(f"  Considered:         {len(rows)}")
        print(f"  Saved:              {saved}")
        print(f"  Low confidence:     {low_conf}")
        print(f"  Model declined:     {unparseable}")
        print(f"  No usable options:  {no_options}")
        print(f"  Errors:             {errors}")
        if dry_run:
            print("  (dry-run: no DB writes)")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--only", default=None)
    p.add_argument("--limit", type=int, default=None)
    p.add_argument(
        "--min-confidence",
        type=float,
        default=MIN_CONFIDENCE_DEFAULT,
        help="Save only when AI confidence >= this (default 0.7)",
    )
    args = p.parse_args()
    asyncio.run(
        run(
            only=args.only,
            limit=args.limit,
            min_confidence=args.min_confidence,
            dry_run=args.dry_run,
        )
    )


if __name__ == "__main__":
    main()
