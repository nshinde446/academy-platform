"""One-shot: flag studymat questions still missing correct_answer as
``pending_review`` so they stay out of test generation until a human
resolves them.

After Phase H finished, ~46 questions had no answer key in the source
PDF (or had broken option text / diagram dependencies) and Gemini's
per-question fallback declined to guess. This script marks them so the
admin review queue picks them up.

Usage:
    cd backend
    python scripts/flag_missing_answers_for_review.py --dry-run
    python scripts/flag_missing_answers_for_review.py
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.modules.auth.models import auth_models  # noqa: F401
from app.modules.academic.models import academic_models  # noqa: F401
from app.modules.batch.models import batch_models  # noqa: F401
from app.modules.tests.models import test_models  # noqa: F401

from app.core.database.session import async_session_factory
from app.modules.tests.models.test_models import Question
from sqlalchemy import select, update


async def run(dry_run: bool) -> None:
    async with async_session_factory() as s:
        # Anything still missing correct_answer that isn't already
        # pending_review or rejected.
        rows = (
            await s.execute(
                select(Question.id, Question.source_ref, Question.review_status).where(
                    Question.source.like("studymat:%"),
                    Question.is_deleted == False,
                    (Question.correct_answer == None) | (Question.correct_answer == ""),
                    Question.review_status != "pending_review",
                    Question.review_status != "rejected",
                )
            )
        ).all()

        print(f"Found {len(rows)} questions to flag as pending_review:")
        for qid, ref, status in rows:
            print(f"  {ref}  (currently {status})")

        if dry_run:
            print("\n(dry-run: no DB writes)")
            return

        if not rows:
            print("Nothing to do.")
            return

        ids = [r[0] for r in rows]
        await s.execute(
            update(Question)
            .where(Question.id.in_(ids))
            .values(review_status="pending_review")
        )
        await s.commit()
        print(f"\nFlagged {len(ids)} questions as pending_review.")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    asyncio.run(run(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
