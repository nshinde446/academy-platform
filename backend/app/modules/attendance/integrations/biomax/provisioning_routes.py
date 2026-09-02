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
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config.settings import get_settings
from app.core.database.session import get_db
from app.modules.attendance.integrations.biomax.iclock import (
    _allowed_serials,
    _require_known_device,
    _resolve_branch,
)
from app.modules.attendance.models.provisioning_models import STATUS_PENDING
from app.modules.attendance.integrations.biomax import biometrics
from app.modules.attendance.repositories import device_command_repo
from app.modules.attendance.schemas.provisioning_schemas import (
    BiometricStatusResponse,
    CrossDeviceRestoreRequest,
    DeviceCommandResponse,
    InstituteReconcileResponse,
    DeviceStatusResponse,
    DeviceUserSnapshotRequest,
    DeviceUserSnapshotResponse,
    ProvisionDevice,
    RefreshUserInfoResponse,
    RestoreResponse,
    ProvisionDevicesResponse,
    ProvisionDryRunRequest,
    ProvisionPlanResponse,
    ProvisionPushRequest,
    ProvisionPushResponse,
    ReconcileResponse,
)
from app.modules.attendance.services import provisioning_service
from app.modules.auth.permissions.rbac import get_current_user, require_roles

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


@router.get("/reconcile-institute", response_model=InstituteReconcileResponse)
async def reconcile_institute(
    _enabled: None = Depends(_require_enabled),
    _user: dict = Depends(_ADMIN),
    session: AsyncSession = Depends(get_db),
):
    """Institute-wide enrollment status across ALL configured terminals, each
    student counted once (a student enrolled on either machine is one 'face
    enrolled'). This is the simple, deduplicated dashboard view; the per-machine
    live counts come back as a small health strip, not a second roster."""
    branch_id = _resolve_branch()
    return await provisioning_service.reconcile_institute(
        session, branch_id, sorted(_allowed_serials())
    )


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


@router.post("/refresh-user-info", response_model=RefreshUserInfoResponse)
async def refresh_user_info(
    dev_id: str = Query(...),
    scope: str = Query("awaiting", pattern="^(awaiting|all)$"),
    x_biomax_sync_token: str | None = Header(None),
    _enabled: None = Depends(_require_enabled),
    session: AsyncSession = Depends(get_db),
):
    """Cloud-async mirror refresh: queue GET_USER_INFO commands the device drains
    on its normal VPS poll, then returns each user's has-face in the result body
    (folded into the mirror by the aidata receiver). No on-site PC needed.

    Headless (meant to run from a daily cron), so it authenticates with the shared
    ``X-BioMax-Sync-Token`` — same secret as the device-user sync — rather than an
    admin session. ``scope=awaiting`` (default) only re-checks students still
    'awaiting face' — small and cheap; ``scope=all`` refreshes every platform
    userId."""
    _verify_sync_token(x_biomax_sync_token)
    _require_known_device(dev_id)
    branch_id = _resolve_branch()
    user_ids = await provisioning_service.user_ids_for_refresh(
        session, branch_id, dev_id, scope
    )
    enqueued = await provisioning_service.enqueue_user_info_refresh(
        session, branch_id, dev_id, user_ids
    )
    await session.commit()
    return RefreshUserInfoResponse(
        dev_id=dev_id, scope=scope,
        targeted_users=len(user_ids), commands_enqueued=enqueued,
    )


def _require_biometric_key() -> None:
    if not biometrics.biometric_backup_enabled():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Biometric backup is disabled (set BIOMAX_BIOMETRIC_KEY).",
        )


@router.get("/device-status", response_model=DeviceStatusResponse)
async def device_status(
    dev_id: str = Query(...),
    _enabled: None = Depends(_require_enabled),
    _user: dict = Depends(_ADMIN),
    session: AsyncSession = Depends(get_db),
):
    """The device's own live counts (userCount/faceCount/…) + last-seen heartbeat,
    from the status block it sends on every poll. All-null until its first poll."""
    _require_known_device(dev_id)
    row = await device_command_repo.get_device_status(session, dev_id)
    if row is None:
        return DeviceStatusResponse(dev_id=dev_id)
    snap = row.snapshot or {}

    def _int(key: str) -> int | None:
        v = snap.get(key)
        try:
            return int(v) if v is not None else None
        except (TypeError, ValueError):
            return None

    return DeviceStatusResponse(
        dev_id=dev_id,
        last_seen_at=row.last_seen_at,
        user_count=_int("userCount"),
        face_count=_int("faceCount"),
        fp_count=_int("fpCount"),
        card_count=_int("cardCount"),
        user_limit=_int("userLimit"),
        face_limit=_int("faceLimit"),
        firmware=(str(snap.get("firmware")) if snap.get("firmware") else None),
    )


@router.get("/biometrics/{student_id}/photo")
async def student_face_photo(
    student_id: uuid.UUID,
    _user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """The student's enrolled face photo (JPEG) from the biometric backup, for the
    student profile avatar. Any signed-in staff may view it (cookie auth, so an
    ``<img>`` works). 404 when we have no photo for the student."""
    branch_id = _resolve_branch()
    jpeg = await provisioning_service.student_face_photo(session, branch_id, student_id)
    if jpeg is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No face photo.")
    return Response(
        content=jpeg,
        media_type="image/jpeg",
        headers={"Cache-Control": "private, max-age=300"},
    )


@router.get("/biometrics/status", response_model=BiometricStatusResponse)
async def biometric_status(
    dev_id: str = Query(...),
    _enabled: None = Depends(_require_enabled),
    _user: dict = Depends(_ADMIN),
    session: AsyncSession = Depends(get_db),
):
    """How many users have a biometric backup for this device (restore coverage)."""
    _require_known_device(dev_id)
    branch_id = _resolve_branch()
    rows = await device_command_repo.list_backed_up_users(session, branch_id, dev_id)
    return BiometricStatusResponse(dev_id=dev_id, backed_up=len(rows))


@router.post("/restore", response_model=RestoreResponse)
async def restore(
    dev_id: str = Query(...),
    x_biomax_sync_token: str | None = Header(None),
    _enabled: None = Depends(_require_enabled),
    session: AsyncSession = Depends(get_db),
):
    """Queue a biometric RESTORE for a (replaced/reset) device: for every user we
    have a backup for, a SET_USER_INFO carrying the stored face/photo/fingerprint
    is queued; the device applies them on its poll — re-creating enrolled users
    with no manual re-enrollment. Templates are decrypted + injected at emit time,
    never stored in the queue in cleartext. Headless (token-authed) so DR can be
    scripted; needs the biometric key to decrypt."""
    _verify_sync_token(x_biomax_sync_token)
    _require_biometric_key()
    _require_known_device(dev_id)
    branch_id = _resolve_branch()
    enqueued = await provisioning_service.enqueue_restore(session, branch_id, dev_id)
    await session.commit()
    return RestoreResponse(dev_id=dev_id, commands_enqueued=enqueued)


@router.post("/restore-cross-device", response_model=RestoreResponse)
async def restore_cross_device(
    body: CrossDeviceRestoreRequest,
    dev_id: str = Query(..., description="target device to enrol onto"),
    source_dev_id: str = Query(..., description="device whose backups to read"),
    x_biomax_sync_token: str | None = Header(None),
    _enabled: None = Depends(_require_enabled),
    session: AsyncSession = Depends(get_db),
):
    """Enrol an EXPLICIT student set onto ``dev_id`` using the faces backed up from
    ``source_dev_id`` — e.g. put two batches onto a second-floor terminal from the
    first terminal's backups. Only students with a face backup on the source are
    queued; the template is decrypted + injected at emit time. Token + key authed."""
    _verify_sync_token(x_biomax_sync_token)
    _require_biometric_key()
    _require_known_device(dev_id)
    _require_known_device(source_dev_id)
    branch_id = _resolve_branch()
    enqueued = await provisioning_service.enqueue_cross_device_restore(
        session,
        branch_id,
        source_dev_id=source_dev_id,
        target_dev_id=dev_id,
        student_ids=body.student_ids,
    )
    await session.commit()
    return RestoreResponse(dev_id=dev_id, commands_enqueued=enqueued)


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
