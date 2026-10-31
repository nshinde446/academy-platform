"""Admin leave-request management — ``/api/v1/admin/leave-requests``.

Academic head / branch admin review teacher leave requests and approve or
reject them (super_admin bypasses via ``require_roles``). Only an approved leave
blocks scheduling, so this queue is the gate between a teacher's request and the
timetable being affected.
"""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.modules.auth.permissions.rbac import require_roles
from app.modules.teacher_portal.schemas.portal_schemas import LeaveDecision
from app.modules.teacher_portal.services import leave_service, leave_settings_service

leave_admin_router = APIRouter(prefix="/admin/leave-requests", tags=["teacher-leave"])
leave_settings_router = APIRouter(prefix="/admin/leave-settings", tags=["teacher-leave"])

_ADMIN_ROLES = ["super_admin", "branch_admin", "academic_head"]
_SETTINGS_ROLES = ["super_admin"]  # §3: Super Admin sets quotas / WOF openings


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


# ── Leave settings: quotas + WOF openings (Super Admin, §3 + WOF) ────────────


class QuotaUpdate(BaseModel):
    year: int
    quotas: dict[str, float]  # {casual, sick, paid}


class WofOpeningSet(BaseModel):
    teacher_id: uuid.UUID
    opening_balance: float
    as_of_date: date


@leave_settings_router.get("/quotas")
async def get_quotas(
    branch_id: uuid.UUID = Query(...),
    year: int = Query(...),
    current_user: dict = Depends(require_roles(_SETTINGS_ROLES)),
    session: AsyncSession = Depends(get_db),
):
    return await leave_settings_service.get_quotas(session, branch_id, year)


@leave_settings_router.put("/quotas")
async def set_quotas(
    body: QuotaUpdate,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(_SETTINGS_ROLES)),
    session: AsyncSession = Depends(get_db),
):
    out = await leave_settings_service.set_quotas(
        session, branch_id=branch_id, year=body.year, quotas=body.quotas,
        user_id=current_user["user_id"],
    )
    await session.commit()
    return out


@leave_settings_router.get("/wof")
async def list_wof(
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(_SETTINGS_ROLES)),
    session: AsyncSession = Depends(get_db),
):
    return await leave_settings_service.list_wof(session, branch_id)


@leave_settings_router.put("/wof")
async def set_wof(
    body: WofOpeningSet,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(_SETTINGS_ROLES)),
    session: AsyncSession = Depends(get_db),
):
    out = await leave_settings_service.set_wof_opening(
        session, branch_id=branch_id, teacher_id=body.teacher_id,
        opening_balance=body.opening_balance, as_of_date=body.as_of_date,
        user_id=current_user["user_id"],
    )
    await session.commit()
    return out


@leave_settings_router.get("/wof/export")
async def export_wof(
    branch_id: uuid.UUID = Query(...),
    fmt: str = Query("xlsx"),
    current_user: dict = Depends(require_roles(_SETTINGS_ROLES)),
    session: AsyncSession = Depends(get_db),
):
    name, data, media = await leave_settings_service.wof_report(
        session, branch_id=branch_id, fmt=fmt
    )
    return Response(
        content=data, media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )
