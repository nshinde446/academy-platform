"""Admin Saturday/Sunday work management — ``/api/v1/admin/weekend-work``.

Seniors (HR / branch admin / academic head; super_admin bypasses) pre-approve a
weekend date for a set of staff, review the report (biometric IN/OUT + the
teacher's work content + a warning flag), approve/reject each day, and apply the
management ABSENT override (Rule 5). The report downloads in the client's sheet
format with the rules note.
"""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config.settings import get_settings
from app.core.database.session import get_db
from app.modules.auth.permissions.rbac import require_roles
from app.modules.teacher_portal.schemas.portal_schemas import (
    WeekendAbsentOverride,
    WeekendDecision,
    WeekendPreapprove,
)
from app.modules.teacher_portal.services import weekend_work_service
from app.modules.teacher_portal.services import weekend_work_export as export

weekend_admin_router = APIRouter(
    prefix="/admin/weekend-work", tags=["weekend-work"]
)

_ADMIN_ROLES = ["super_admin", "branch_admin", "academic_head"]


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@weekend_admin_router.post("/preapprove")
async def preapprove(
    body: WeekendPreapprove,
    request: Request,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(_ADMIN_ROLES)),
    session: AsyncSession = Depends(get_db),
):
    """Step 1 — pre-approve a Saturday/Sunday for a set of staff."""
    return await weekend_work_service.preapprove(
        session, branch_id=branch_id, staff_ids=body.staff_ids,
        work_date=body.work_date, user_id=current_user["user_id"], ip=_ip(request),
    )


@weekend_admin_router.get("")
async def report(
    branch_id: uuid.UUID = Query(...),
    from_: date = Query(..., alias="from"),
    to: date = Query(...),
    staff_id: uuid.UUID | None = Query(default=None),
    approval_status: str | None = Query(default=None, alias="status"),
    current_user: dict = Depends(require_roles(_ADMIN_ROLES)),
    session: AsyncSession = Depends(get_db),
):
    """The weekend-work report over [from, to], optionally filtered by teacher and
    approval status."""
    if to < from_:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="'to' is before 'from'.")
    return await weekend_work_service.report(
        session, branch_id=branch_id, start=from_, end=to,
        staff_id=staff_id, approval_status=approval_status,
    )


@weekend_admin_router.get("/export")
async def export_report(
    branch_id: uuid.UUID = Query(...),
    from_: date = Query(..., alias="from"),
    to: date = Query(...),
    staff_id: uuid.UUID | None = Query(default=None),
    approval_status: str | None = Query(default=None, alias="status"),
    current_user: dict = Depends(require_roles(_ADMIN_ROLES)),
    session: AsyncSession = Depends(get_db),
):
    """Download the weekend-work report as Excel, in the client's sheet layout."""
    if to < from_:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="'to' is before 'from'.")
    data = await weekend_work_service.report(
        session, branch_id=branch_id, start=from_, end=to,
        staff_id=staff_id, approval_status=approval_status,
    )
    title = f"Weekend Work Report — {from_} to {to}"
    content = export.weekend_report_xlsx(
        brand=get_settings().ACADEMY_BRAND_NAME, title=title,
        rows=data["rows"], rules=data["rules"],
    )
    return Response(
        content=content, media_type=export.XLSX_MIME,
        headers={"Content-Disposition": 'attachment; filename="weekend-work.xlsx"'},
    )


@weekend_admin_router.post("/{work_id}/approve")
async def approve(
    work_id: uuid.UUID,
    request: Request,
    branch_id: uuid.UUID = Query(...),
    body: WeekendDecision | None = None,
    current_user: dict = Depends(require_roles(_ADMIN_ROLES)),
    session: AsyncSession = Depends(get_db),
):
    return await weekend_work_service.decide(
        session, work_id=work_id, branch_id=branch_id, approve=True,
        note=body.note if body else None, user_id=current_user["user_id"], ip=_ip(request),
    )


@weekend_admin_router.post("/{work_id}/reject")
async def reject(
    work_id: uuid.UUID,
    request: Request,
    branch_id: uuid.UUID = Query(...),
    body: WeekendDecision | None = None,
    current_user: dict = Depends(require_roles(_ADMIN_ROLES)),
    session: AsyncSession = Depends(get_db),
):
    return await weekend_work_service.decide(
        session, work_id=work_id, branch_id=branch_id, approve=False,
        note=body.note if body else None, user_id=current_user["user_id"], ip=_ip(request),
    )


@weekend_admin_router.post("/{work_id}/mark-absent")
async def mark_absent(
    work_id: uuid.UUID,
    request: Request,
    branch_id: uuid.UUID = Query(...),
    body: WeekendAbsentOverride | None = None,
    current_user: dict = Depends(require_roles(_ADMIN_ROLES)),
    session: AsyncSession = Depends(get_db),
):
    """Management override (Rule 5) — force the day ABSENT (or clear it)."""
    return await weekend_work_service.set_marked_absent(
        session, work_id=work_id, branch_id=branch_id,
        absent=body.absent if body else True,
        user_id=current_user["user_id"], ip=_ip(request),
    )
