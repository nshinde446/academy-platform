"""Admin config of the Star-System dropdown masters — ``/api/v1/admin/assessment-catalog``.

Admins manage the categories/items/option sets teachers choose from. Role-gated
to admins (super_admin bypasses), branch-scoped.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.modules.auth.permissions.rbac import require_roles
from app.modules.teacher_portal.services import assessment_config_service as cfg

assessment_config_router = APIRouter(
    prefix="/admin/assessment-catalog", tags=["assessment-config"])

_ADMIN_ROLES = ["super_admin", "branch_admin", "academic_head"]


class ItemCreate(BaseModel):
    category_id: uuid.UUID
    item_name: str
    input_type: str
    options: list[str] = []
    sort_order: int = 0


class ItemUpdate(BaseModel):
    item_name: str | None = None
    options: list[str] | None = None
    active: bool | None = None
    sort_order: int | None = None


class CategoryUpdate(BaseModel):
    name: str | None = None
    active: bool | None = None
    sort_order: int | None = None


@assessment_config_router.get("")
async def get_catalog(
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(_ADMIN_ROLES)),
    session: AsyncSession = Depends(get_db),
):
    return await cfg.catalog(session, branch_id=branch_id)


@assessment_config_router.post("/items")
async def add_item(
    body: ItemCreate,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(_ADMIN_ROLES)),
    session: AsyncSession = Depends(get_db),
):
    return await cfg.add_item(
        session, branch_id=branch_id, user_id=current_user["user_id"],
        category_id=body.category_id, item_name=body.item_name,
        input_type=body.input_type, options=body.options, sort_order=body.sort_order)


@assessment_config_router.patch("/items/{item_id}")
async def update_item(
    item_id: uuid.UUID,
    body: ItemUpdate,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(_ADMIN_ROLES)),
    session: AsyncSession = Depends(get_db),
):
    return await cfg.update_item(
        session, branch_id=branch_id, user_id=current_user["user_id"], item_id=item_id,
        item_name=body.item_name, options=body.options, active=body.active,
        sort_order=body.sort_order)


@assessment_config_router.patch("/categories/{category_id}")
async def update_category(
    category_id: uuid.UUID,
    body: CategoryUpdate,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(_ADMIN_ROLES)),
    session: AsyncSession = Depends(get_db),
):
    return await cfg.update_category(
        session, branch_id=branch_id, user_id=current_user["user_id"],
        category_id=category_id, name=body.name, active=body.active,
        sort_order=body.sort_order)
