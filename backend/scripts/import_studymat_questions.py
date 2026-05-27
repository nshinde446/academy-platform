"""Import studymat questions from a JSONL dump into the current DB.

Companion to ``export_studymat_questions.py``. Runs on the target host
(e.g. inside the prod backend container) and resolves FK UUIDs against
the target's own ``subjects``, ``branch``, and ``academic_years`` rows.

Mirrors the FK strategy ``ingest_studymat.py`` uses for fresh ingest:
- Picks the first active Subject in the DB as the default.
- Inherits ``branch_id`` and ``academic_year_id`` from that subject.
- Leaves ``topic_id`` NULL — admin maps in review queue.

Idempotent: skips any row whose ``source_ref`` already exists.

Usage (on the target host):
    docker compose -p academy-prod exec backend \
        python scripts/import_studymat_questions.py /tmp/studymat-export.jsonl

Flags:
    --dry-run     Parse + report but don't write.
    --batch-size  Commit every N rows (default 100).
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
from app.modules.academic.models.academic_models import Subject  # noqa: E402
from app.modules.tests.models.test_models import Question  # noqa: E402
from sqlalchemy import select  # noqa: E402


async def run(jsonl_path: Path, dry_run: bool, batch_size: int) -> None:
    if not jsonl_path.exists():
        raise SystemExit(f"Input file not found: {jsonl_path}")

    records: list[dict] = []
    with jsonl_path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise SystemExit(f"Bad JSON at line {line_no}: {exc}")

    print(f"Read {len(records)} records from {jsonl_path}")

    async with async_session_factory() as s:
        default_subject = (
            await s.execute(
                select(Subject).where(Subject.is_deleted == False).limit(1)
            )
        ).scalar_one_or_none()
        if default_subject is None:
            raise SystemExit("Target DB has no subjects — seed first.")

        existing_refs_rows = (
            await s.execute(
                select(Question.source_ref).where(
                    Question.source.like("studymat:%"),
                    Question.source_ref.is_not(None),
                )
            )
        ).all()
        existing_refs = {r[0] for r in existing_refs_rows}

        print(
            f"Target DB: subject={default_subject.name} ({default_subject.code}), "
            f"branch_id={default_subject.branch_id}, "
            f"ay_id={default_subject.academic_year_id}"
        )
        print(f"Existing studymat source_refs: {len(existing_refs)}")

        inserted = 0
        skipped_existing = 0
        skipped_no_ref = 0
        pending = 0

        for rec in records:
            ref = rec.get("source_ref")
            if not ref:
                skipped_no_ref += 1
                continue
            if ref in existing_refs:
                skipped_existing += 1
                continue

            q = Question(
                content=rec["content"],
                options=rec.get("options"),
                correct_answer=rec.get("correct_answer") or "",
                explanation=rec.get("explanation"),
                subject_id=default_subject.id,
                topic_id=None,
                difficulty=(rec.get("difficulty") or "MEDIUM"),
                blooms_taxonomy=(rec.get("blooms_taxonomy") or "REMEMBER"),
                concept_tags=rec.get("concept_tags"),
                source=rec.get("source"),
                source_ref=ref,
                diagram_ref=rec.get("diagram_ref"),
                review_status=rec.get("review_status") or "approved",
                quality_score=rec.get("quality_score"),
                branch_id=default_subject.branch_id,
                academic_year_id=default_subject.academic_year_id,
                status=rec.get("status") or "active",
                is_deleted=False,
            )
            existing_refs.add(ref)
            if dry_run:
                inserted += 1
                continue

            s.add(q)
            inserted += 1
            pending += 1
            if pending >= batch_size:
                await s.commit()
                pending = 0

        if not dry_run and pending:
            await s.commit()

        print()
        print("=" * 60)
        print("IMPORT SUMMARY")
        print(f"  Records read:        {len(records)}")
        print(f"  Inserted:            {inserted}")
        print(f"  Skipped (existing):  {skipped_existing}")
        print(f"  Skipped (no ref):    {skipped_no_ref}")
        if dry_run:
            print("  (dry-run: no DB writes)")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("jsonl", help="Path to studymat-export.jsonl")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--batch-size", type=int, default=100)
    args = p.parse_args()
    asyncio.run(
        run(
            jsonl_path=Path(args.jsonl).resolve(),
            dry_run=args.dry_run,
            batch_size=args.batch_size,
        )
    )


if __name__ == "__main__":
    main()
