"""RBAC access-control management: coordinator batch scope + accounts grants.

Manager-only operations. Every change is written to the audit log (§4 of the
RBAC spec) — no role, Managers included, is exempt.
"""

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.services import audit_service
from app.modules.auth.models.access_models import AccountsAttendanceGrant
from app.modules.auth.repositories import access_repository


async def get_coordinator_batches(
    session: AsyncSession, user_id: uuid.UUID
) -> list:
    rows = await access_repository.coordinator_rows(session, user_id)
    return await access_repository.batches_for(
        session, [r.batch_id for r in rows]
    )


async def set_coordinator_batches(
    session: AsyncSession,
    *,
    actor_id: uuid.UUID,
    branch_id: uuid.UUID,
    coordinator_id: uuid.UUID,
    batch_ids: list[uuid.UUID],
    ip_address: str | None = None,
) -> list:
    """Replace a coordinator's assigned batches. Validates every batch is in the
    acting Manager's branch, then records the change in the audit log."""
    unique_ids = list(dict.fromkeys(batch_ids))
    if unique_ids:
        batches = await access_repository.batches_for(session, unique_ids)
        found = {b.id: b for b in batches}
        for bid in unique_ids:
            b = found.get(bid)
            if b is None or b.branch_id != branch_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Batch not found in this branch",
                )

    before = await access_repository.assigned_batch_ids(session, coordinator_id)
    rows = await access_repository.set_coordinator_batches(
        session,
        user_id=coordinator_id,
        branch_id=branch_id,
        batch_ids=unique_ids,
    )
    await audit_service.log_action(
        session,
        user_id=actor_id,
        action="Permission Change",
        table_name="batch_coordinators",
        record_id=coordinator_id,
        old_values={"batch_ids": [str(b) for b in before]},
        new_values={"batch_ids": [str(b) for b in unique_ids]},
        ip_address=ip_address,
        branch_id=branch_id,
    )
    return await access_repository.batches_for(session, [r.batch_id for r in rows])


async def list_grants(
    session: AsyncSession,
    *,
    branch_id: uuid.UUID,
    user_id: uuid.UUID | None = None,
) -> list[AccountsAttendanceGrant]:
    return await access_repository.list_grants(
        session, branch_id=branch_id, user_id=user_id
    )


async def create_grant(
    session: AsyncSession,
    *,
    actor_id: uuid.UUID,
    branch_id: uuid.UUID,
    user_id: uuid.UUID,
    batch_id: uuid.UUID | None,
    expires_at: datetime | None,
    ip_address: str | None = None,
) -> AccountsAttendanceGrant:
    if expires_at is not None:
        # Normalise to aware UTC and reject an already-past expiry.
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at <= datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Expiry must be in the future",
            )
    if batch_id is not None:
        batches = await access_repository.batches_for(session, [batch_id])
        if not batches or batches[0].branch_id != branch_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Batch not found in this branch",
            )

    grant = await access_repository.create_grant(
        session,
        user_id=user_id,
        branch_id=branch_id,
        batch_id=batch_id,
        expires_at=expires_at,
        granted_by=actor_id,
    )
    await audit_service.log_action(
        session,
        user_id=actor_id,
        action="Permission Change",
        table_name="accounts_attendance_grants",
        record_id=grant.id,
        new_values={
            "user_id": str(user_id),
            "batch_id": str(batch_id) if batch_id else None,
            "expires_at": expires_at.isoformat() if expires_at else None,
        },
        ip_address=ip_address,
        branch_id=branch_id,
    )
    return grant


async def revoke_grant(
    session: AsyncSession,
    *,
    actor_id: uuid.UUID,
    branch_id: uuid.UUID,
    grant_id: uuid.UUID,
    ip_address: str | None = None,
) -> None:
    grant = await access_repository.get_grant(session, grant_id)
    if grant is None or grant.branch_id != branch_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Grant not found"
        )
    await access_repository.revoke_grant(session, grant)
    await audit_service.log_action(
        session,
        user_id=actor_id,
        action="Permission Change",
        table_name="accounts_attendance_grants",
        record_id=grant_id,
        old_values={"user_id": str(grant.user_id)},
        new_values={"revoked": True},
        ip_address=ip_address,
        branch_id=branch_id,
    )
