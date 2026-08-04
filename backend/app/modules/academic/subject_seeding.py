"""Subject-skeleton seeding — the academic-domain knowledge of which subjects a
syllabus carries, and how to materialise them (with their chapter/topic tree)
onto a course.

Historically this lived inside the student import service (subjects were only
ever auto-created as a side effect of a curriculum-aware import). It is academic
knowledge, so it lives here and is shared by both callers:

- student import — seeds a newly derived course's subjects, tagged with the
  ``import_id`` so "undo import" can reclaim them;
- the Courses "Subjects" manager — lets an admin seed subjects for ANY course
  (e.g. a manually created batch's course) from a chosen syllabus.

Both go through :func:`build_subject_skeleton`, which is idempotent: it only ever
creates when the course has no subjects yet, so a re-run (or a later syllabus
import) never duplicates or clobbers an existing skeleton.
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.academic import curriculum
from app.modules.academic.repositories import academic_repository

# Subject skeletons per syllabus (design §2/§5). DEFAULTS the coaching can edit
# — §6 leaves Biology-vs-Botany/Zoology and the MHT-CET stream split as open
# decisions, so we only auto-create for the unambiguous tracks and skip the
# rest (no subjects rather than a wrong guess).
SUBJECT_SETS: dict[str, list[str]] = {
    "NEET": ["Physics", "Chemistry", "Botany", "Zoology"],
    "JEE": ["Physics", "Chemistry", "Mathematics"],
    "PCMB": ["Physics", "Chemistry", "Mathematics", "Biology"],
    "MHT-CET-PCM": ["Physics", "Chemistry", "Mathematics"],
    "MHT-CET-PCB": ["Physics", "Chemistry", "Biology"],
    # MHT-CET with no explicit stream: carry the *union* on the course (P/C are
    # shared; Maths is PCM-only; Biology is PCB-only) and let each student's
    # `stream` select their subset at read time.
    "MHT-CET": ["Physics", "Chemistry", "Mathematics", "Biology"],
    "FOUNDATION": ["Science", "Mathematics", "Mental Ability"],
}

# Free-text Syllabus values normalized to a SUBJECT_SETS key.
SYLLABUS_ALIASES: dict[str, str] = {
    "neet": "NEET",
    "pcb": "NEET",
    "jee": "JEE",
    "pcm": "JEE",
    "pcmb": "PCMB",
    "both": "PCMB",
    "mht-cet-pcm": "MHT-CET-PCM",
    "mhtcet-pcm": "MHT-CET-PCM",
    "mht-cet-pcb": "MHT-CET-PCB",
    "mhtcet-pcb": "MHT-CET-PCB",
    "foundation": "FOUNDATION",
}

SUBJECT_CODES: dict[str, str] = {
    "Physics": "PHY",
    "Chemistry": "CHE",
    "Mathematics": "MAT",
    "Biology": "BIO",
    "Botany": "BOT",
    "Zoology": "ZOO",
    "Science": "SCI",
    "Mental Ability": "MA",
}

# Human-facing syllabus choices for the "Seed from syllabus" picker, in the
# order the UI should show them. Only keys with a subject set are offered.
AVAILABLE_SYLLABI: list[dict[str, object]] = [
    {"key": key, "label": label, "subjects": SUBJECT_SETS[key]}
    for key, label in (
        ("JEE", "JEE (Physics, Chemistry, Maths)"),
        ("NEET", "NEET (Physics, Chemistry, Botany, Zoology)"),
        ("MHT-CET", "MHT-CET (all four — per-student stream filters)"),
        ("MHT-CET-PCM", "MHT-CET PCM (Physics, Chemistry, Maths)"),
        ("MHT-CET-PCB", "MHT-CET PCB (Physics, Chemistry, Biology)"),
        ("PCMB", "PCB + PCM (all four subjects)"),
        ("FOUNDATION", "Foundation (Science, Maths, Mental Ability)"),
    )
]


def subjects_for(key: str | None) -> list[str]:
    return SUBJECT_SETS.get(key or "", [])


def subject_code(name: str) -> str:
    return SUBJECT_CODES.get(name, name[:3].upper())


async def build_subject_skeleton(
    session: AsyncSession,
    branch_id: uuid.UUID,
    course,
    academic_year,
    syllabus_key: str | None,
    import_id: uuid.UUID | None = None,
) -> int:
    """Create the course's subject skeleton from the resolved syllabus (design
    §4 step 3). The §8 protection: only ever create when the course has *no*
    subjects yet — never overwrite an existing skeleton or a curriculum that a
    syllabus import has since loaded (§7.4). Returns how many were created.

    Matched by ``(course, name)`` ignoring AY, so the later syllabus import
    finds and reuses these subjects when it attaches chapters."""
    names = subjects_for(syllabus_key)
    if not names:
        return 0
    existing = await academic_repository.list_subjects(session, branch_id, course.id)
    if existing:
        return 0

    from app.modules.academic.models.academic_models import (
        Chapter,
        Subject,
        Topic,
    )

    # Build the whole subject -> chapter -> topic tree in memory (ids
    # pre-generated so children can reference parents) and insert it level by
    # level — subjects, then chapters, then topics — flushing between levels so
    # every parent row exists before its children. (One bulk add_all of the
    # whole tree doesn't guarantee insert order without ORM relationships, which
    # Postgres rejects as a FK violation; SQLite silently allowed it.) Tagged
    # with import_id so undo can reclaim them. Foundation/Other have no
    # curriculum and add nothing beyond the bare subjects.
    subjects: list = []
    chapters: list = []
    topics_rows: list = []
    for name in names:
        subject_id = uuid.uuid4()
        subjects.append(
            Subject(
                id=subject_id,
                branch_id=branch_id,
                academic_year_id=academic_year.id,
                course_id=course.id,
                name=name,
                code=subject_code(name),
                import_id=import_id,
            )
        )
        for ch_order, (ch_name, topics) in enumerate(
            curriculum.chapters_for(syllabus_key or "", name)
        ):
            chapter_id = uuid.uuid4()
            chapters.append(
                Chapter(
                    id=chapter_id,
                    branch_id=branch_id,
                    academic_year_id=academic_year.id,
                    subject_id=subject_id,
                    name=ch_name,
                    order=ch_order,
                    import_id=import_id,
                )
            )
            for t_order, t_name in enumerate(topics):
                topics_rows.append(
                    Topic(
                        id=uuid.uuid4(),
                        branch_id=branch_id,
                        academic_year_id=academic_year.id,
                        chapter_id=chapter_id,
                        name=t_name,
                        order=t_order,
                        import_id=import_id,
                    )
                )
    session.add_all(subjects)
    await session.flush()
    session.add_all(chapters)
    await session.flush()
    session.add_all(topics_rows)
    await session.flush()
    return len(names)
