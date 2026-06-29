"""eTimeOffice admin endpoints.

GET  /api/v1/attendance/etimeoffice/status
    Whether the integration is enabled + configured (no secrets returned).

POST /api/v1/attendance/etimeoffice/pull?branch_id=&start=&end=
    Admin-triggered pull for a date range. The scheduled Celery job polls a
    rolling lookback automatically; this is the manual "sync now".
"""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config.settings import get_settings
from app.core.database.session import get_db
from app.modules.attendance.integrations.etimeoffice import service as eto_service
from app.modules.attendance.integrations.etimeoffice.client import ETimeOfficeError
from app.modules.auth.permissions.rbac import require_roles

router = APIRouter(prefix="/attendance/etimeoffice", tags=["attendance"])


def _resolve_branch(branch_id: uuid.UUID | None) -> uuid.UUID:
    """Use the explicit branch, else the configured default. 400 if neither."""
    if branch_id is not None:
        return branch_id
    configured = get_settings().ETO_BRANCH_ID
    if configured:
        try:
            return uuid.UUID(configured)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="ETO_BRANCH_ID is not a valid UUID.",
            ) from exc
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="No branch_id given and ETO_BRANCH_ID is not configured.",
    )


@router.get("/status")
async def eto_status(
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin"])),
):
    """Config presence only — never echoes credentials."""
    s = get_settings()
    return {
        "enabled": s.ETO_ENABLED,
        "configured": bool(s.ETO_CORP_ID and s.ETO_USERNAME and s.ETO_PASSWORD),
        "base_url": s.ETO_BASE_URL,
        "lookback_days": s.ETO_LOOKBACK_DAYS,
        "default_branch_id": s.ETO_BRANCH_ID or None,
    }


@router.post("/pull")
async def eto_pull(
    branch_id: uuid.UUID | None = Query(None),
    start: date = Query(..., description="From date (inclusive)"),
    end: date = Query(..., description="To date (inclusive)"),
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin"])),
    session: AsyncSession = Depends(get_db),
):
    if not get_settings().ETO_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="eTimeOffice integration is disabled (ETO_ENABLED=false).",
        )
    if start > end:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start must be on or before end.",
        )
    resolved = _resolve_branch(branch_id)
    try:
        return await eto_service.sync_range(
            session, branch_id=resolved, from_date=start, to_date=end
        )
    except ETimeOfficeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
        ) from exc
