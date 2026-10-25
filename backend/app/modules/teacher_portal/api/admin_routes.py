"""Admin management of teacher login accounts — ``/api/v1/admin/teacher-accounts``.

Role-gated (super_admin / branch_admin / accounts). Temporary passwords are
returned once in the response body and never stored in plain text or logged.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.modules.auth.permissions.rbac import require_roles
from app.modules.teacher_portal.services import admin_service

admin_router = APIRouter(prefix="/admin/teacher-accounts", tags=["teacher-accounts"])

# Who may manage teacher accounts (spec: configurable; super_admin always via
# require_roles' built-in bypass).
_ADMIN_ROLES = ["super_admin", "branch_admin", "accounts"]


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _branch(current_user: dict, branch_id: uuid.UUID | None) -> uuid.UUID:
    return branch_id or current_user.get("branch_id")


@admin_router.get("")
async def list_teacher_accounts(
    request: Request,
    branch_id: uuid.UUID = Query(...),
    status: str | None = Query(default=None),
    q: str | None = Query(default=None),
    current_user: dict = Depends(require_roles(_ADMIN_ROLES)),
    session: AsyncSession = Depends(get_db),
):
    return await admin_service.list_accounts(
        session, branch_id=branch_id, status_filter=status, q=q
    )


@admin_router.post("/bulk-create")
async def bulk_create(
    request: Request,
    branch_id: uuid.UUID = Query(...),
    body: dict | None = None,
    current_user: dict = Depends(require_roles(_ADMIN_ROLES)),
    session: AsyncSession = Depends(get_db),
):
    """Create accounts for active Teachers-department staff without one. Returns
    the temporary passwords ONCE (the admin downloads/hands them out)."""
    staff_ids = None
    if body and body.get("staff_ids"):
        staff_ids = [uuid.UUID(str(s)) for s in body["staff_ids"]]
    created = await admin_service.bulk_create(
        session, branch_id=branch_id, actor_id=current_user["user_id"],
        staff_ids=staff_ids, ip=_ip(request),
    )
    return {"created": created, "count": len(created)}


@admin_router.post("/{staff_id}/reset-password")
async def reset_password(
    staff_id: uuid.UUID,
    request: Request,
    current_user: dict = Depends(require_roles(_ADMIN_ROLES)),
    session: AsyncSession = Depends(get_db),
):
    return await admin_service.reset_password(
        session, staff_id=staff_id, actor_id=current_user["user_id"], ip=_ip(request)
    )


@admin_router.post("/{staff_id}/unlock")
async def unlock(
    staff_id: uuid.UUID,
    request: Request,
    current_user: dict = Depends(require_roles(_ADMIN_ROLES)),
    session: AsyncSession = Depends(get_db),
):
    await admin_service.unlock(
        session, staff_id=staff_id, actor_id=current_user["user_id"], ip=_ip(request)
    )
    return {"message": "unlocked"}


@admin_router.post("/{staff_id}/disable")
async def disable(
    staff_id: uuid.UUID,
    request: Request,
    current_user: dict = Depends(require_roles(_ADMIN_ROLES)),
    session: AsyncSession = Depends(get_db),
):
    await admin_service.set_enabled(
        session, staff_id=staff_id, enabled=False,
        actor_id=current_user["user_id"], ip=_ip(request),
    )
    return {"message": "disabled"}


@admin_router.post("/{staff_id}/enable")
async def enable(
    staff_id: uuid.UUID,
    request: Request,
    current_user: dict = Depends(require_roles(_ADMIN_ROLES)),
    session: AsyncSession = Depends(get_db),
):
    await admin_service.set_enabled(
        session, staff_id=staff_id, enabled=True,
        actor_id=current_user["user_id"], ip=_ip(request),
    )
    return {"message": "enabled"}
