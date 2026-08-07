"""BioMax device provisioning API — enqueue/reconcile/dry-run (read + write queue).

All routes are branch-scoped to the device's configured branch, admin-gated, and
**dormant unless ``BIOMAX_PROVISIONING_ENABLED``** — off by default, so shipping
this plumbing cannot affect a live deployment. Building the queue never touches
the terminal; the emission step that actually pushes commands to the device is a
separate, capture-gated increment.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config.settings import get_settings
from app.core.database.session import get_db
from app.modules.attendance.integrations.biomax.iclock import (
    _allowed_serials,
    _require_known_device,
    _resolve_branch,
)
from app.modules.attendance.models.provisioning_models import STATUS_PENDING
from app.modules.attendance.repositories import device_command_repo
from app.modules.attendance.schemas.provisioning_schemas import (
    DeviceCommandResponse,
    DeviceUserSnapshotRequest,
    DeviceUserSnapshotResponse,
    ProvisionDevice,
    ProvisionDevicesResponse,
    ProvisionDryRunRequest,
    ProvisionPlanResponse,
    ProvisionPushRequest,
    ProvisionPushResponse,
    ReconcileResponse,
)
from app.modules.attendance.services import provisioning_service
from app.modules.auth.permissions.rbac import require_roles

router = APIRouter(prefix="/attendance/provisioning", tags=["attendance"])

_ADMIN = require_roles(["super_admin", "branch_admin"])


def _require_enabled() -> None:
    """Fail-safe gate: the whole feature is a no-op until explicitly enabled."""
    if not get_settings().BIOMAX_PROVISIONING_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="BioMax provisioning is disabled (BIOMAX_PROVISIONING_ENABLED).",
        )


def _verify_sync_token(provided: str | None) -> None:
    """Authenticate the headless on-site sync agent via a shared secret. Fail-safe:
    when the token is unset the endpoint rejects everything (a spoofed snapshot
    could hide/forge who's enrolled), so the agent is disabled until a token is
    configured on both the agent PC and this server."""
    expected = get_settings().BIOMAX_SYNC_TOKEN
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Device-user sync disabled. Set BIOMAX_SYNC_TOKEN.",
        )
    if not provided or provided != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing sync token.",
        )


@router.get("/devices", response_model=ProvisionDevicesResponse)
async def list_devices(
    _user: dict = Depends(_ADMIN),
):
    """Configured devices + the enabled flag, so the UI renders the right state.

    Deliberately NOT behind ``_require_enabled``: the UI needs to distinguish
    "feature off" from "no devices configured", and this leaks nothing beyond
    the serials an admin already set.
    """
    return ProvisionDevicesResponse(
        enabled=get_settings().BIOMAX_PROVISIONING_ENABLED,
        devices=[ProvisionDevice(dev_id=s) for s in sorted(_allowed_serials())],
    )


@router.get("/reconcile", response_model=ReconcileResponse)
async def reconcile(
    dev_id: str = Query(...),
    _enabled: None = Depends(_require_enabled),
    _user: dict = Depends(_ADMIN),
    session: AsyncSession = Depends(get_db),
):
    """Three-way diff between platform students and the device's user mirror."""
    _require_known_device(dev_id)
    branch_id = _resolve_branch()
    return await provisioning_service.reconcile(session, branch_id, dev_id)


@router.post("/dry-run", response_model=ProvisionPlanResponse)
async def dry_run(
    body: ProvisionDryRunRequest,
    _enabled: None = Depends(_require_enabled),
    _user: dict = Depends(_ADMIN),
    session: AsyncSession = Depends(get_db),
):
    """Render what a push WOULD do for an explicit student set — no side effects."""
    _require_known_device(body.dev_id)
    branch_id = _resolve_branch()
    return await provisioning_service.render_dry_run(
        session, branch_id, body.dev_id, body.student_ids
    )


@router.post("/push", response_model=ProvisionPushResponse)
async def push(
    body: ProvisionPushRequest,
    _enabled: None = Depends(_require_enabled),
    _user: dict = Depends(_ADMIN),
    session: AsyncSession = Depends(get_db),
):
    """Enqueue register commands for an explicit student set (idempotent)."""
    _require_known_device(body.dev_id)
    branch_id = _resolve_branch()
    result = await provisioning_service.enqueue_students(
        session, branch_id, body.dev_id, body.student_ids
    )
    await session.commit()
    return result


@router.post("/device-users/sync", response_model=DeviceUserSnapshotResponse)
async def sync_device_users(
    body: DeviceUserSnapshotRequest,
    x_biomax_sync_token: str | None = Header(None),
    session: AsyncSession = Depends(get_db),
):
    """Rebuild the device-user mirror from a snapshot the on-site agent read off
    the terminal's local API (``GetUserIdList`` + ``GetUserInfo``). This is the
    ground-truth path for who's actually enrolled (and who has a face), so
    reconcile stops depending on catching the device's one-time enrollment
    pushes. Headless: authenticated by the shared ``X-BioMax-Sync-Token``, not an
    admin session. Full-replace — users the device no longer holds are dropped."""
    _verify_sync_token(x_biomax_sync_token)
    _require_known_device(body.dev_id)
    branch_id = _resolve_branch()
    upserted, removed = await provisioning_service.sync_device_users(
        session, branch_id, body.dev_id, body.users
    )
    await session.commit()
    return DeviceUserSnapshotResponse(
        dev_id=body.dev_id, upserted=upserted, removed=removed, total=len(body.users)
    )


@router.get("/commands", response_model=list[DeviceCommandResponse])
async def list_commands(
    dev_id: str | None = Query(None),
    command_status: str | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    _enabled: None = Depends(_require_enabled),
    _user: dict = Depends(_ADMIN),
    session: AsyncSession = Depends(get_db),
):
    """Queue view for the UI — filter by device and/or status."""
    branch_id = _resolve_branch()
    return await device_command_repo.list_commands(
        session, branch_id, dev_id, command_status, offset, limit
    )


@router.post("/commands/{command_id}/cancel", response_model=DeviceCommandResponse)
async def cancel_command(
    command_id: uuid.UUID,
    _enabled: None = Depends(_require_enabled),
    _user: dict = Depends(_ADMIN),
    session: AsyncSession = Depends(get_db),
):
    """Pull a still-pending command out of the queue. A sent command can't be
    cancelled — the device already has it."""
    branch_id = _resolve_branch()
    command = await device_command_repo.get_command(session, command_id, branch_id)
    if command is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found.")
    if command.command_status != STATUS_PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Only pending commands can be cancelled (is {command.command_status}).",
        )
    command = await device_command_repo.cancel_pending(session, command)
    await session.commit()
    return command
