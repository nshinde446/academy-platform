import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.batch.models.batch_models import Batch, BatchSchedule


async def create(session: AsyncSession, **kwargs) -> Batch:
    batch = Batch(**kwargs)
    session.add(batch)
    await session.flush()
    return batch


async def get_by_id(session: AsyncSession, batch_id: uuid.UUID) -> Batch | None:
    result = await session.execute(
        select(Batch).where(Batch.id == batch_id, Batch.is_deleted == False)
    )
    return result.scalar_one_or_none()


async def list_by_branch(
    session: AsyncSession, branch_id: uuid.UUID, offset: int = 0, limit: int = 50
) -> list[Batch]:
    result = await session.execute(
        select(Batch)
        .where(Batch.branch_id == branch_id, Batch.is_deleted == False)
        .offset(offset)
        .limit(limit)
    )
    return list(result.scalars().all())


async def update(session: AsyncSession, batch: Batch, **kwargs) -> Batch:
    for key, value in kwargs.items():
        if value is not None:
            setattr(batch, key, value)
    await session.flush()
    return batch


async def soft_delete(session: AsyncSession, batch: Batch) -> None:
    batch.is_deleted = True
    await session.flush()


async def soft_delete_schedules(session: AsyncSession, batch_id: uuid.UUID) -> int:
    """Soft-delete a batch's weekly timetable slots — called when the batch is
    deleted so its patterns don't linger as orphans the generator must skip.
    Returns how many were cleared."""
    result = await session.execute(
        select(BatchSchedule).where(
            BatchSchedule.batch_id == batch_id,
            BatchSchedule.is_deleted == False,
        )
    )
    rows = list(result.scalars().all())
    for slot in rows:
        slot.is_deleted = True
    await session.flush()
    return len(rows)
