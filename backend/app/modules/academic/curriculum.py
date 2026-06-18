"""Bundled master curriculum (chapters + topics) used to auto-populate a new
course's subject skeleton during a student import.

The data file ``data/master_curriculum.json`` is the class-tagged master
syllabus (NEET / JEE / MHT-CET, per exam-subject sheet). This module maps a
resolved syllabus key + subject name to the right sheet and returns ordered
chapters with their topics. Pairs with no backing sheet (e.g. Foundation)
return nothing, so those subjects stay skeleton-only.
"""

import json
from functools import lru_cache
from pathlib import Path

_DATA = Path(__file__).parent / "data" / "master_curriculum.json"

# (syllabus_key, subject) -> sheet name in master_curriculum.json.
# NEET's Botany/Zoology both map to the single NEET_Biology sheet; Foundation
# has no sheet (skeleton only).
_SHEET_FOR: dict[tuple[str, str], str] = {
    ("NEET", "Physics"): "NEET_Physics",
    ("NEET", "Chemistry"): "NEET_Chemistry",
    ("NEET", "Botany"): "NEET_Biology",
    ("NEET", "Zoology"): "NEET_Biology",
    ("NEET", "Biology"): "NEET_Biology",
    ("JEE", "Physics"): "JEE_Main_Physics",
    ("JEE", "Chemistry"): "JEE_Main_Chemistry",
    ("JEE", "Mathematics"): "JEE_Main_Maths",
    ("PCMB", "Physics"): "NEET_Physics",
    ("PCMB", "Chemistry"): "NEET_Chemistry",
    ("PCMB", "Biology"): "NEET_Biology",
    ("PCMB", "Mathematics"): "JEE_Main_Maths",
    ("MHT-CET-PCM", "Physics"): "MHTCET_Physics",
    ("MHT-CET-PCM", "Chemistry"): "MHTCET_Chemistry",
    ("MHT-CET-PCM", "Mathematics"): "MHTCET_Maths",
    ("MHT-CET-PCB", "Physics"): "MHTCET_Physics",
    ("MHT-CET-PCB", "Chemistry"): "MHTCET_Chemistry",
    ("MHT-CET-PCB", "Biology"): "MHTCET_Biology",
}


@lru_cache(maxsize=1)
def _raw() -> dict:
    if not _DATA.exists():
        return {}
    with open(_DATA, encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=None)
def chapters_for(
    syllabus_key: str, subject: str
) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """Ordered ``((chapter_name, (topic, ...)), ...)`` for a syllabus subject,
    from the bundled master curriculum. Empty when the pair has no backing
    sheet. Chapters keep sheet order; duplicate topics within a chapter are
    de-duplicated."""
    sheet = _SHEET_FOR.get((syllabus_key, subject))
    if not sheet:
        return ()
    chapters: dict[str, list[str]] = {}
    for r in _raw().get(sheet, []):
        main = (r.get("main") or "").strip()
        if not main:
            continue
        topics = chapters.setdefault(main, [])
        sub = (r.get("sub") or "").strip()
        if sub and sub not in topics:
            topics.append(sub)
    return tuple((name, tuple(tops)) for name, tops in chapters.items())
