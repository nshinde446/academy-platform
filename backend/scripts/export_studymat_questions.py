"""Dump studymat-sourced questions to JSONL for porting to another DB.

Reads every ``questions`` row with ``source LIKE 'studymat:%'`` and
writes one JSON object per line to the output file (default
``studymat-export.jsonl`` in the current dir).

We intentionally **do not** serialize FK UUIDs (``subject_id``,
``branch_id``, ``academic_year_id``, ``topic_id``) — those are
re-resolved on the target DB by the companion ``import_studymat_questions.py``
because UUIDs differ between independent seedings.

Idempotent: re-running just overwrites the output file.

Usage:
    cd backend
    python scripts/export_studymat_questions.py
    python scripts/export_studymat_questions.py --out /tmp/studymat-export.jsonl
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_BACKEND = _HERE.parent
sys.path.insert(0, str(_BACKEND))

from app.modules.auth.models import auth_models  # noqa: F401,E402
from app.modules.academic.models import academic_models  # noqa: F401,E402
from app.modules.batch.models import batch_models  # noqa: F401,E402
from app.modules.tests.models import test_models  # noqa: F401,E402

from app.core.database.session import async_session_factory  # noqa: E402
from app.modules.tests.models.test_models import Question  # noqa: E402
from sqlalchemy import select  # noqa: E402


PORTABLE_COLUMNS = (
    "content",
    "options",
    "correct_answer",
    "explanation",
    "difficulty",
    "blooms_taxonomy",
    "concept_tags",
    "source",
    "source_ref",
    "diagram_ref",
    "review_status",
    "quality_score",
    "status",
)


async def run(out_path: Path) -> None:
    async with async_session_factory() as s:
        rows = (
            await s.execute(
                select(Question).where(
                    Question.source.like("studymat:%"),
                    Question.is_deleted == False,
                )
            )
        ).scalars().all()

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for q in rows:
            record = {col: getattr(q, col) for col in PORTABLE_COLUMNS}
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"Wrote {len(rows)} questions to {out_path}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--out",
        default="studymat-export.jsonl",
        help="Output JSONL path (default: ./studymat-export.jsonl)",
    )
    args = p.parse_args()
    asyncio.run(run(Path(args.out).resolve()))


if __name__ == "__main__":
    main()
