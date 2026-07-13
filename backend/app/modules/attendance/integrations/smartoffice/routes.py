"""SmartOffice admin endpoints.

GET  /api/v1/attendance/smartoffice/status
    Whether the integration is enabled + configured (no secrets returned).

POST /api/v1/attendance/smartoffice/pull?branch_id=&start=&end=
    Admin-triggered pull for a date range. The scheduled Celery job polls a
    rolling lookback automatically; this is the manual "sync now".
"""

from __future__ import annotations

import uuid
from datetime import date

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config.settings import get_settings
from app.core.database.session import get_db
from app.modules.attendance.integrations.smartoffice import service as so_service
from app.modules.attendance.integrations.smartoffice.client import SmartOfficeError
from app.modules.auth.permissions.rbac import require_roles

router = APIRouter(prefix="/attendance/smartoffice", tags=["attendance"])


class SmartOfficeIngestBody(BaseModel):
    """A batch of raw SmartOffice log rows pushed by the on-prem agent. Each row
    carries the SmartOffice field names (EmployeeCode / LogDate / SerialNumber /
    PunchDirection); the server maps + tz-converts + dedups them centrally."""

    rows: list[dict[str, Any]]


def _verify_agent_token(provided: str | None) -> None:
    """Authenticate the on-prem agent via a shared secret (fail-safe: when the
    token is unset we reject everything rather than accept spoofed punches)."""
    expected = get_settings().SMARTOFFICE_INGEST_TOKEN
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Agent ingest disabled. Set SMARTOFFICE_INGEST_TOKEN.",
        )
    if not provided or provided != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing agent token.",
        )


def _resolve_branch(branch_id: uuid.UUID | None) -> uuid.UUID:
    """Use the explicit branch, else the configured default. 400 if neither."""
    if branch_id is not None:
        return branch_id
    configured = get_settings().SMARTOFFICE_BRANCH_ID
    if configured:
        try:
            return uuid.UUID(configured)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="SMARTOFFICE_BRANCH_ID is not a valid UUID.",
            ) from exc
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="No branch_id given and SMARTOFFICE_BRANCH_ID is not configured.",
    )


@router.get("/status")
async def smartoffice_status(
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin"])),
):
    """Config presence only — never echoes the API key."""
    s = get_settings()
    return {
        "enabled": s.SMARTOFFICE_ENABLED,
        "configured": bool(s.SMARTOFFICE_BASE_URL and s.SMARTOFFICE_API_KEY),
        "base_url": s.SMARTOFFICE_BASE_URL,
        "lookback_days": s.SMARTOFFICE_LOOKBACK_DAYS,
        "default_branch_id": s.SMARTOFFICE_BRANCH_ID or None,
    }


@router.post("/pull")
async def smartoffice_pull(
    branch_id: uuid.UUID | None = Query(None),
    start: date = Query(..., description="From date (inclusive)"),
    end: date = Query(..., description="To date (inclusive)"),
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin"])),
    session: AsyncSession = Depends(get_db),
):
    if not get_settings().SMARTOFFICE_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SmartOffice integration is disabled (SMARTOFFICE_ENABLED=false).",
        )
    if start > end:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start must be on or before end.",
        )
    resolved = _resolve_branch(branch_id)
    try:
        return await so_service.sync_range(
            session, branch_id=resolved, from_date=start, to_date=end
        )
    except SmartOfficeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
        ) from exc


@router.post("/ingest")
async def smartoffice_ingest(
    body: SmartOfficeIngestBody,
    branch_id: uuid.UUID | None = Query(None),
    x_smartoffice_token: str | None = Header(None),
    session: AsyncSession = Depends(get_db),
):
    """Agent PUSH: the on-prem agent reads new rows from SmartOffice's SQL table
    and POSTs them here. Authenticated by the shared ``X-SmartOffice-Token``
    header (not a user login — the caller is a machine). Idempotent, so the agent
    can safely re-send a batch it isn't sure landed."""
    _verify_agent_token(x_smartoffice_token)
    resolved = _resolve_branch(branch_id)
    return await so_service.ingest_rows(session, branch_id=resolved, rows=body.rows)
