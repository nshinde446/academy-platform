"""M1.4 — Backfill the materials table from existing study_material PDFs.

For every PDF under ``study_material/extracted/`` that has at least one
existing ``questions`` row linking back to it (via source_ref), create
a ``materials`` row and link those questions to the new material via
``questions.material_id``.

What this script does:
1. Walks ``study_material/extracted/`` for *.pdf.
2. Parses subject + class + chapter from the relative path
   (``<subject>/class-<N>/<chapter>/<file>.pdf``), mirroring the ingest
   pipeline's convention.
3. Computes sha256 of the file. If a material with that sha256 already
   exists for the target branch, reuses it (idempotent re-run).
4. Otherwise: writes the file into the new canonical storage layout
   via the StorageBackend, creates the ``materials`` row, and links
   any matching questions through ``material_id``.

Idempotent — safe to re-run. Only files with matching questions
become materials; orphan PDFs (with no questions) are skipped.

Usage:
    cd backend
    python scripts/backfill_materials.py --dry-run
    python scripts/backfill_materials.py
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_BACKEND = _HERE.parent
sys.path.insert(0, str(_BACKEND))

from app.modules.auth.models import auth_models  # noqa: F401,E402
from app.modules.academic.models import academic_models  # noqa: F401,E402
from app.modules.batch.models import batch_models  # noqa: F401,E402
from app.modules.tests.models import test_models  # noqa: F401,E402
from app.modules.materials.models import material_models  # noqa: F401,E402

from sqlalchemy import select, update  # noqa: E402

from app.core.database.session import async_session_factory  # noqa: E402
from app.core.storage import (  # noqa: E402
    LocalFilesystemBackend,
    build_storage_key,
    compute_sha256,
)
from app.modules.academic.models.academic_models import AcademicYear, Subject  # noqa: E402
from app.modules.materials.models.material_models import Material  # noqa: E402
from app.modules.tests.models.test_models import Question  # noqa: E402


STUDY_MATERIAL = _BACKEND.parent / "study_material"
EXTRACTED = STUDY_MATERIAL / "extracted"

# Maps the path-derived subject slug → the canonical subject code we
# expect to find in the subjects table. Kept tiny on purpose — this
# script only touches the existing study_material/ tree.
SUBJECT_CODE_BY_HINT = {
    "physics": "PHYSICS",
    "chemistry": "CHEMISTRY",
    "biology": "BIOLOGY",
    "mathematics": "MATHEMATICS",
    "maths": "MATHEMATICS",
    "math": "MATHEMATICS",
}


def parse_path(rel_path: Path) -> tuple[str, str, str | None]:
    """Return (subject_hint, class_label, chapter_slug) parsed from a
    path like ``physics/class-12/current-electricity/foo.pdf``."""
    parts = rel_path.parts
    subject = parts[0].lower() if parts else "unknown"
    class_label = "unknown"
    chapter_slug: str | None = None
    for p in parts[1:]:
        if p.startswith("class-"):
            class_label = p[len("class-"):]
        elif chapter_slug is None and not p.lower().endswith(".pdf"):
            chapter_slug = p
    return subject, class_label, chapter_slug


def _ay_code(ay: AcademicYear) -> str:
    return f"{ay.start_year}-{ay.end_year % 100:02d}"


async def run(dry_run: bool) -> None:
    if not EXTRACTED.exists():
        raise SystemExit(f"Source tree missing: {EXTRACTED}")

    storage = LocalFilesystemBackend(STUDY_MATERIAL)

    async with async_session_factory() as s:
        # Pick the AY that actually has subjects. Newest first, falling
        # back to whichever has data.
        ay_rows = (
            await s.execute(
                select(AcademicYear)
                .where(AcademicYear.is_deleted == False)
                .order_by(AcademicYear.start_year.desc())
            )
        ).scalars().all()
        if not ay_rows:
            raise SystemExit("No academic years in DB — seed first.")

        ay = None
        subjects_by_code: dict[str, Subject] = {}
        for candidate in ay_rows:
            subs = (
                await s.execute(
                    select(Subject).where(
                        Subject.is_deleted == False,
                        Subject.academic_year_id == candidate.id,
                    )
                )
            ).scalars().all()
            if subs:
                ay = candidate
                subjects_by_code = {sub.code.upper(): sub for sub in subs}
                break
        if ay is None:
            raise SystemExit("No subjects in any academic year — seed first.")
        print(f"Backfilling into academic year {ay.name} ({_ay_code(ay)})")
        # Used as a fallback when the path hint doesn't match any known code.
        fallback_subject = next(iter(subjects_by_code.values()))

        pdfs = sorted(EXTRACTED.rglob("*.pdf"))
        print(f"Found {len(pdfs)} PDFs under {EXTRACTED}")

        created_materials = 0
        reused_materials = 0
        skipped_no_questions = 0
        linked_questions = 0

        for pdf in pdfs:
            rel = pdf.relative_to(EXTRACTED)
            doc_path = str(rel).replace("\\", "/")
            subject_hint, class_label, chapter_slug = parse_path(rel)

            # Pick the subject row to attach to.
            target_code = SUBJECT_CODE_BY_HINT.get(subject_hint)
            subject = subjects_by_code.get(target_code) if target_code else None
            if subject is None:
                subject = fallback_subject

            # source_ref's doc-path component matches this PDF's relative
            # path under extracted/. Use it as the join key.
            q_count = (
                await s.execute(
                    select(Question)
                    .where(
                        Question.source.like("studymat:%"),
                        Question.is_deleted == False,
                        Question.source_ref.like(f"{doc_path}#%"),
                    )
                )
            ).scalars().all()

            if not q_count:
                skipped_no_questions += 1
                continue

            # Dedup on sha256 before writing.
            data = pdf.read_bytes()
            sha = compute_sha256(data)

            existing = (
                await s.execute(
                    select(Material).where(
                        Material.sha256 == sha,
                        Material.branch_id == subject.branch_id,
                        Material.is_deleted == False,
                    )
                )
            ).scalar_one_or_none()

            if existing is not None:
                material = existing
                reused_materials += 1
            else:
                material_id = uuid.uuid4()
                storage_key = build_storage_key(
                    material_id=str(material_id),
                    academic_year_code=_ay_code(ay),
                    class_label=class_label,
                    subject_slug=subject.code.lower(),
                    category="ncert",
                    filename=pdf.name,
                )
                if not dry_run:
                    storage.write(storage_key, data)
                    material = Material(
                        id=material_id,
                        filename=pdf.name,
                        storage_key=storage_key,
                        mime_type="application/pdf",
                        size_bytes=len(data),
                        sha256=sha,
                        academic_year_id=ay.id,
                        class_label=class_label,
                        subject_id=subject.id,
                        topic=chapter_slug,
                        category="ncert",
                        exam_types=[],
                        ingest_status="ingested",  # questions already exist
                        question_count=len(q_count),
                        branch_id=subject.branch_id,
                    )
                    s.add(material)
                    await s.flush()
                else:
                    material = None
                created_materials += 1

            # Link questions to the material (only ones not yet linked).
            if not dry_run and material is not None:
                result = await s.execute(
                    update(Question)
                    .where(
                        Question.source.like("studymat:%"),
                        Question.is_deleted == False,
                        Question.source_ref.like(f"{doc_path}#%"),
                        Question.material_id.is_(None),
                    )
                    .values(material_id=material.id)
                )
                linked_questions += result.rowcount or 0

                # Refresh denormalized count
                await s.execute(
                    Material.__table__.update()
                    .where(Material.id == material.id)
                    .values(question_count=len(q_count))
                )

            print(
                f"  {doc_path}: subject={subject.code}, class={class_label}, "
                f"questions={len(q_count)}, "
                f"{'reused' if existing else 'created'} material"
            )

        if not dry_run:
            await s.commit()

        print()
        print("=" * 60)
        print("BACKFILL SUMMARY")
        print(f"  PDFs scanned:               {len(pdfs)}")
        print(f"  Materials created:          {created_materials}")
        print(f"  Materials reused (sha):     {reused_materials}")
        print(f"  PDFs skipped (no Qs):       {skipped_no_questions}")
        print(f"  Questions newly linked:     {linked_questions}")
        if dry_run:
            print("  (dry-run: no DB writes)")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    asyncio.run(run(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
