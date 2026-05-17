import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.classroom.models.classroom_models import Classroom


async def create(session: AsyncSession, **kwargs) -> Classroom:
    classroom = Classroom(**kwargs)
    session.add(classroom)
    await session.flush()
    return classroom


async def get_by_id(session: AsyncSession, classroom_id: uuid.UUID) -> Classroom | None:
    result = await session.execute(
        select(Classroom).where(Classroom.id == classroom_id, Classroom.is_deleted == False)
    )
    return result.scalar_one_or_none()


async def list_by_branch(
    session: AsyncSession, branch_id: uuid.UUID, offset: int = 0, limit: int = 50
) -> list[Classroom]:
    result = await session.execute(
        select(Classroom)
        .where(Classroom.branch_id == branch_id, Classroom.is_deleted == False)
        .offset(offset)
        .limit(limit)
    )
    return list(result.scalars().all())


async def update(session: AsyncSession, classroom: Classroom, **kwargs) -> Classroom:
    for key, value in kwargs.items():
        if value is not None:
            setattr(classroom, key, value)
    await session.flush()
    return classroom


async def soft_delete(session: AsyncSession, classroom: Classroom) -> None:
    classroom.is_deleted = True
    await session.flush()
