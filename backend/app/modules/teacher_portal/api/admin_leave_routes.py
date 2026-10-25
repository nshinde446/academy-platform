"""Admin leave-request management — ``/api/v1/admin/leave-requests``.

Academic head / branch admin review teacher leave requests and approve or
reject them (super_admin bypasses via ``require_roles``). Only an approved leave
blocks scheduling, so this queue is the gate between a teacher's request and the
timetable being affected.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.modules.auth.permissions.rbac import require_roles
from app.modules.teacher_portal.schemas.portal_schemas import LeaveDecision
from app.modules.teacher_portal.services import leave_service

leave_admin_router = APIRouter(prefix="/admin/leave-requests", tags=["teacher-leave"])

_ADMIN_ROLES = ["super_admin", "branch_admin", "academic_head"]


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@leave_admin_router.get("")
async def list_requests(
    branch_id: uuid.UUID = Query(...),
    status: str | None = Query(default=None),
    current_user: dict = Depends(require_roles(_ADMIN_ROLES)),
    session: AsyncSession = Depends(get_db),
):
    return await leave_service.list_requests(
        session, branch_id=branch_id, status_filter=status
    )


@leave_admin_router.post("/{leave_id}/approve")
async def approve(
    leave_id: uuid.UUID,
    request: Request,
    branch_id: uuid.UUID = Query(...),
    body: LeaveDecision | None = None,
    current_user: dict = Depends(require_roles(_ADMIN_ROLES)),
    session: AsyncSession = Depends(get_db),
):
    return await leave_service.decide(
        session, leave_id=leave_id, approve=True, actor_id=current_user["user_id"],
        branch_id=branch_id, note=body.note if body else None, ip=_ip(request),
    )


@leave_admin_router.post("/{leave_id}/reject")
async def reject(
    leave_id: uuid.UUID,
    request: Request,
    branch_id: uuid.UUID = Query(...),
    body: LeaveDecision | None = None,
    current_user: dict = Depends(require_roles(_ADMIN_ROLES)),
    session: AsyncSession = Depends(get_db),
):
    return await leave_service.decide(
        session, leave_id=leave_id, approve=False, actor_id=current_user["user_id"],
        branch_id=branch_id, note=body.note if body else None, ip=_ip(request),
    )
