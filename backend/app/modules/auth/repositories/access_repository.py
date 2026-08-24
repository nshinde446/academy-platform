"""Data access for RBAC scoping: coordinator batches + accounts attendance grants."""

import uuid
from datetime import datetime

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models.access_models import (
    AccountsAttendanceGrant,
    BatchCoordinator,
)
from app.modules.batch.models.batch_models import Batch


# ── Floor Coordinator → batches ──────────────────────────────────────────────


async def coordinator_rows(
    session: AsyncSession, user_id: uuid.UUID
) -> list[BatchCoordinator]:
    result = await session.execute(
        select(BatchCoordinator).where(
            BatchCoordinator.user_id == user_id,
            BatchCoordinator.is_deleted == False,  # noqa: E712
        )
    )
    return list(result.scalars().all())


async def assigned_batch_ids(
    session: AsyncSession, user_id: uuid.UUID
) -> list[uuid.UUID]:
    """The batch ids a coordinator may act on — the enforcement handle (used by
    a later increment to scope attendance/lecture reads and writes)."""
    result = await session.execute(
        select(BatchCoordinator.batch_id).where(
            BatchCoordinator.user_id == user_id,
            BatchCoordinator.is_deleted == False,  # noqa: E712
        )
    )
    return [r[0] for r in result.all()]


async def set_coordinator_batches(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    branch_id: uuid.UUID,
    batch_ids: list[uuid.UUID],
) -> list[BatchCoordinator]:
    """Replace a coordinator's batch list with exactly ``batch_ids``. Adds the
    new ones, removes the dropped ones. Returns the resulting live rows."""
    current = await coordinator_rows(session, user_id)
    current_by_batch = {r.batch_id: r for r in current}
    wanted = set(batch_ids)

    for batch_id in wanted - set(current_by_batch):
        session.add(
            BatchCoordinator(
                user_id=user_id, batch_id=batch_id, branch_id=branch_id
            )
        )
    for batch_id, row in current_by_batch.items():
        if batch_id not in wanted:
            await session.delete(row)

    await session.flush()
    return await coordinator_rows(session, user_id)


async def batches_for(
    session: AsyncSession, batch_ids: list[uuid.UUID]
) -> list[Batch]:
    if not batch_ids:
        return []
    result = await session.execute(
        select(Batch).where(
            Batch.id.in_(batch_ids),
            Batch.is_deleted == False,  # noqa: E712
        )
    )
    return list(result.scalars().all())


# ── Accounts attendance grants ───────────────────────────────────────────────


async def list_grants(
    session: AsyncSession,
    *,
    branch_id: uuid.UUID,
    user_id: uuid.UUID | None = None,
) -> list[AccountsAttendanceGrant]:
    filters = [
        AccountsAttendanceGrant.branch_id == branch_id,
        AccountsAttendanceGrant.is_deleted == False,  # noqa: E712
    ]
    if user_id is not None:
        filters.append(AccountsAttendanceGrant.user_id == user_id)
    result = await session.execute(
        select(AccountsAttendanceGrant).where(and_(*filters))
    )
    return list(result.scalars().all())


async def get_grant(
    session: AsyncSession, grant_id: uuid.UUID
) -> AccountsAttendanceGrant | None:
    result = await session.execute(
        select(AccountsAttendanceGrant).where(
            AccountsAttendanceGrant.id == grant_id,
            AccountsAttendanceGrant.is_deleted == False,  # noqa: E712
        )
    )
    return result.scalar_one_or_none()


async def create_grant(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    branch_id: uuid.UUID,
    batch_id: uuid.UUID | None,
    expires_at: datetime | None,
    granted_by: uuid.UUID,
) -> AccountsAttendanceGrant:
    grant = AccountsAttendanceGrant(
        user_id=user_id,
        branch_id=branch_id,
        batch_id=batch_id,
        expires_at=expires_at,
        granted_by=granted_by,
    )
    session.add(grant)
    await session.flush()
    return grant


async def revoke_grant(session: AsyncSession, grant: AccountsAttendanceGrant) -> None:
    await session.delete(grant)


async def active_grants_for(
    session: AsyncSession, user_id: uuid.UUID, now: datetime
) -> list[AccountsAttendanceGrant]:
    """Live, non-expired grants for a user — the read handle enforcement will
    use to decide whether an Accounts user may see attendance."""
    result = await session.execute(
        select(AccountsAttendanceGrant).where(
            AccountsAttendanceGrant.user_id == user_id,
            AccountsAttendanceGrant.is_deleted == False,  # noqa: E712
            or_(
                AccountsAttendanceGrant.expires_at.is_(None),
                AccountsAttendanceGrant.expires_at > now,
            ),
        )
    )
    return list(result.scalars().all())
