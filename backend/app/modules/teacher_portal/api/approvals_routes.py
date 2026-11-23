"""Approver inbox + decisions — ``/api/v1/admin/approvals`` (SRD §5.3).

Seniors / Admins (academic_head, branch_admin; super_admin bypasses) review the
PENDING Weekend Plans and Self-Assessments of their branch and Approve / Reject /
Mark ABSENT with a mandatory comment. The branch comes from the query (same shape
as the weekend-work admin routes); the approver identity comes from the session.
"""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.modules.auth.permissions.rbac import require_roles
from app.modules.teacher_portal.schemas.portal_schemas import ApprovalDecision
from app.modules.teacher_portal.services import approvals_service

approvals_router = APIRouter(prefix="/admin/approvals", tags=["approvals"])

_APPROVER_ROLES = ["super_admin", "branch_admin", "academic_head"]


@approvals_router.get("")
async def list_inbox(
    branch_id: uuid.UUID = Query(...),
    type: str | None = Query(default=None),
    teacher_staff_id: uuid.UUID | None = Query(default=None),
    from_: date | None = Query(default=None, alias="from"),
    to: date | None = Query(default=None),
    decision_status: str = Query(default="PENDING", alias="status"),
    current_user: dict = Depends(require_roles(_APPROVER_ROLES)),
    session: AsyncSession = Depends(get_db),
):
    """The approvals inbox (AP01), filterable by type, teacher, date and status."""
    return await approvals_service.inbox(
        session, branch_id=branch_id, record_type=type,
        teacher_staff_id=teacher_staff_id, start=from_, end=to,
        status_filter=decision_status)


@approvals_router.get("/{record_type}/{record_id}")
async def get_detail(
    record_type: str,
    record_id: uuid.UUID,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(_APPROVER_ROLES)),
    session: AsyncSession = Depends(get_db),
):
    """Read-only full view of one submission with its history (AP02)."""
    return await approvals_service.detail(
        session, branch_id=branch_id, record_type=record_type.upper(), record_id=record_id)


@approvals_router.post("/{record_type}/{record_id}/decide")
async def decide(
    record_type: str,
    record_id: uuid.UUID,
    body: ApprovalDecision,
    request: Request,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(_APPROVER_ROLES)),
    session: AsyncSession = Depends(get_db),
):
    """Approve / Reject / Mark ABSENT with a mandatory comment (AP03–AP09)."""
    return await approvals_service.decide(
        session, branch_id=branch_id, record_type=record_type.upper(),
        record_id=record_id, approver_user_id=current_user["user_id"],
        action=body.action.upper(), comment=body.comment)
