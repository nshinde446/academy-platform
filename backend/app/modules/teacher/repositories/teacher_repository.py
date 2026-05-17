import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.teacher.models.teacher_models import Teacher


async def create(session: AsyncSession, **kwargs) -> Teacher:
    teacher = Teacher(**kwargs)
    session.add(teacher)
    await session.flush()
    return teacher


async def get_by_id(session: AsyncSession, teacher_id: uuid.UUID) -> Teacher | None:
    result = await session.execute(
        select(Teacher).where(Teacher.id == teacher_id, Teacher.is_deleted == False)
    )
    return result.scalar_one_or_none()


async def list_by_branch(
    session: AsyncSession, branch_id: uuid.UUID, offset: int = 0, limit: int = 50
) -> list[Teacher]:
    result = await session.execute(
        select(Teacher)
        .where(Teacher.branch_id == branch_id, Teacher.is_deleted == False)
        .offset(offset)
        .limit(limit)
    )
    return list(result.scalars().all())


async def update(session: AsyncSession, teacher: Teacher, **kwargs) -> Teacher:
    for key, value in kwargs.items():
        if value is not None:
            setattr(teacher, key, value)
    await session.flush()
    return teacher


async def soft_delete(session: AsyncSession, teacher: Teacher) -> None:
    teacher.is_deleted = True
    await session.flush()
