"""Admin configuration of the Star-System dropdown masters (SRD: Admin manages
dropdown masters; AssessmentItemMaster is admin-configurable).

Thin CRUD over the catalog, branch-scoped. Categories are seeded from defaults;
admins add/rename items, edit option sets and toggle items/categories active.
"""

from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.teacher_portal.models.workflow_models import (
    ASSESSMENT_INPUT_TYPES,
    AssessmentCategory,
    AssessmentItemMaster,
)
from app.modules.teacher_portal.services import assessment_catalog


async def catalog(session: AsyncSession, *, branch_id: uuid.UUID) -> dict:
    """Full catalog incl. inactive rows, for the admin editor."""
    await assessment_catalog.ensure_seeded(session, branch_id=branch_id)
    cats = list((await session.execute(
        select(AssessmentCategory).where(
            AssessmentCategory.branch_id == branch_id,
            AssessmentCategory.is_deleted == False,  # noqa: E712
        ).order_by(AssessmentCategory.sort_order.asc())
    )).scalars().all())
    items = list((await session.execute(
        select(AssessmentItemMaster).where(
            AssessmentItemMaster.branch_id == branch_id,
            AssessmentItemMaster.is_deleted == False,  # noqa: E712
        ).order_by(AssessmentItemMaster.sort_order.asc())
    )).scalars().all())
    by_cat: dict[uuid.UUID, list] = {}
    for it in items:
        by_cat.setdefault(it.category_id, []).append(it)
    return {
        "categories": [
            {
                "id": c.id, "name": c.name, "sort_order": c.sort_order,
                "is_deduction": c.is_deduction, "active": c.active,
                "items": [
                    {
                        "id": it.id, "name": it.item_name, "input_type": it.input_type,
                        "options": it.options, "sort_order": it.sort_order,
                        "active": it.active,
                    }
                    for it in by_cat.get(c.id, [])
                ],
            }
            for c in cats
        ]
    }


async def _item(session, branch_id, item_id) -> AssessmentItemMaster:
    it = (await session.execute(
        select(AssessmentItemMaster).where(
            AssessmentItemMaster.id == item_id,
            AssessmentItemMaster.branch_id == branch_id,
            AssessmentItemMaster.is_deleted == False,  # noqa: E712
        )
    )).scalar_one_or_none()
    if it is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found.")
    return it


async def add_item(
    session: AsyncSession, *, branch_id: uuid.UUID, user_id: uuid.UUID,
    category_id: uuid.UUID, item_name: str, input_type: str,
    options: list[str], sort_order: int = 0,
) -> dict:
    if input_type not in ASSESSMENT_INPUT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"input_type must be one of {sorted(ASSESSMENT_INPUT_TYPES)}.")
    cat = (await session.execute(
        select(AssessmentCategory).where(
            AssessmentCategory.id == category_id,
            AssessmentCategory.branch_id == branch_id,
            AssessmentCategory.is_deleted == False,  # noqa: E712
        )
    )).scalar_one_or_none()
    if cat is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found.")
    it = AssessmentItemMaster(
        branch_id=branch_id, category_id=category_id, item_name=item_name.strip(),
        input_type=input_type, options=list(options), sort_order=sort_order,
        active=True, created_by=user_id)
    session.add(it)
    await session.flush()
    return {"id": it.id}


async def update_item(
    session: AsyncSession, *, branch_id: uuid.UUID, user_id: uuid.UUID,
    item_id: uuid.UUID, item_name: str | None = None, options: list[str] | None = None,
    active: bool | None = None, sort_order: int | None = None,
) -> dict:
    it = await _item(session, branch_id, item_id)
    if item_name is not None:
        it.item_name = item_name.strip()
    if options is not None:
        it.options = list(options)
    if active is not None:
        it.active = active
    if sort_order is not None:
        it.sort_order = sort_order
    it.updated_by = user_id
    await session.flush()
    return {"id": it.id}


async def update_category(
    session: AsyncSession, *, branch_id: uuid.UUID, user_id: uuid.UUID,
    category_id: uuid.UUID, name: str | None = None, active: bool | None = None,
    sort_order: int | None = None,
) -> dict:
    cat = (await session.execute(
        select(AssessmentCategory).where(
            AssessmentCategory.id == category_id,
            AssessmentCategory.branch_id == branch_id,
            AssessmentCategory.is_deleted == False,  # noqa: E712
        )
    )).scalar_one_or_none()
    if cat is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found.")
    if name is not None:
        cat.name = name.strip()
    if active is not None:
        cat.active = active
    if sort_order is not None:
        cat.sort_order = sort_order
    cat.updated_by = user_id
    await session.flush()
    return {"id": cat.id}
