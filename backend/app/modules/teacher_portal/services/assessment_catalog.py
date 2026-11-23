"""Default Teacher Star-System catalog (SRD 5.2.1) + idempotent per-branch seeding.

The categories, items and their dropdown option sets are admin-configurable
(``AssessmentItemMaster``), but every branch starts from this default so the form
works out of the box. ``ensure_seeded`` is safe to call repeatedly: it only adds
what's missing, never overwrites an admin's edits.

Input-type assignments below are sensible defaults drawn from the SRD examples
and the wireframe (§7.2); the client can change any item's type/options later.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.teacher_portal.models.workflow_models import (
    AssessmentCategory,
    AssessmentItemMaster,
)

# Option sets (SRD 5.2.1 "Proposed option sets").
COUNT_OPTIONS = ["0", "1", "2", "3", "4", "5", "6", "7", "8+"]
STATUS_OPTIONS = ["Not Applicable", "Not Done", "Partially Done", "Done"]
DEDUCTION_YESNO = ["No", "Yes"]
DEDUCTION_COUNT = ["0", "1", "2", "3", "4", "5"]

_OPTIONS_FOR = {
    "COUNT": COUNT_OPTIONS,
    "STATUS": STATUS_OPTIONS,
    "DEDUCTION_YESNO": DEDUCTION_YESNO,
    "DEDUCTION_COUNT": DEDUCTION_COUNT,
}

# (category_name, is_deduction, [(item_name, input_type_key), ...])
# input_type_key maps to the stored input_type + its options; DEDUCTION_* collapse
# to input_type "DEDUCTION" with the matching option set.
DEFAULT_CATALOG: list[tuple[str, bool, list[tuple[str, str]]]] = [
    ("Classroom Work", False, [
        ("Lectures Conducted", "COUNT"),
        ("Notebook/Test Checking", "STATUS"),
        ("Doubt Solving", "COUNT"),
        ("Lecture Recording", "STATUS"),
        ("Supervision", "STATUS"),
    ]),
    ("Student & Parent Engagement", False, [
        ("Student Viva", "COUNT"),
        ("Student Counselling", "COUNT"),
        ("Parent Counselling", "COUNT"),
        ("Parent Meeting", "COUNT"),
    ]),
    ("Evaluation System", False, [
        ("Test Paper Preparation", "STATUS"),
        ("Academic Records Update", "STATUS"),
        ("Monthly Analysis", "STATUS"),
        ("Weekly Test Responsibility", "STATUS"),
    ]),
    ("General Work", False, [
        ("Paper Checking", "STATUS"),
        ("School Relations", "STATUS"),
        ("Agam Entries", "COUNT"),
        ("Lecture Replacement", "COUNT"),
    ]),
    ("Discipline Deductions", True, [
        ("Planned Leave", "DEDUCTION_YESNO"),
        ("Informed Leave", "DEDUCTION_YESNO"),
        ("Uninformed Leave", "DEDUCTION_YESNO"),
        ("Late Entry", "DEDUCTION_COUNT"),
        ("Off Lecture", "DEDUCTION_COUNT"),
        ("Half Day", "DEDUCTION_COUNT"),
    ]),
]

# The four star-rated categories (everything that isn't the deduction category),
# in order — used to validate star submissions and compute the final total.
RATED_CATEGORY_NAMES = [name for name, is_ded, _ in DEFAULT_CATALOG if not is_ded]
MAX_FINAL_STAR = 5 * len(RATED_CATEGORY_NAMES)  # 20


def _stored_input_type(key: str) -> str:
    return "DEDUCTION" if key.startswith("DEDUCTION") else key


async def ensure_seeded(
    session: AsyncSession, *, branch_id: uuid.UUID
) -> None:
    """Seed the default categories/items for ``branch_id`` if absent. Idempotent:
    adds only missing categories and missing items, preserving admin edits."""
    existing_cats = {
        c.name: c
        for c in (await session.execute(
            select(AssessmentCategory).where(
                AssessmentCategory.branch_id == branch_id,
                AssessmentCategory.is_deleted == False,  # noqa: E712
            )
        )).scalars().all()
    }

    for cat_order, (cat_name, is_ded, items) in enumerate(DEFAULT_CATALOG):
        cat = existing_cats.get(cat_name)
        if cat is None:
            cat = AssessmentCategory(
                branch_id=branch_id, name=cat_name, sort_order=cat_order,
                is_deduction=is_ded, active=True,
            )
            session.add(cat)
            await session.flush()
            existing_cats[cat_name] = cat

        existing_items = {
            i.item_name
            for i in (await session.execute(
                select(AssessmentItemMaster).where(
                    AssessmentItemMaster.category_id == cat.id,
                    AssessmentItemMaster.is_deleted == False,  # noqa: E712
                )
            )).scalars().all()
        }
        for item_order, (item_name, type_key) in enumerate(items):
            if item_name in existing_items:
                continue
            session.add(AssessmentItemMaster(
                branch_id=branch_id,
                category_id=cat.id,
                item_name=item_name,
                input_type=_stored_input_type(type_key),
                options=list(_OPTIONS_FOR[type_key]),
                sort_order=item_order,
                active=True,
            ))
    await session.flush()
