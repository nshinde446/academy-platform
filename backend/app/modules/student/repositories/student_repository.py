import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.student.models.student_models import Student


async def create(session: AsyncSession, **kwargs) -> Student:
    student = Student(**kwargs)
    session.add(student)
    await session.flush()
    return student


async def get_by_id(session: AsyncSession, student_id: uuid.UUID) -> Student | None:
    result = await session.execute(
        select(Student).where(Student.id == student_id, Student.is_deleted == False)
    )
    return result.scalar_one_or_none()


async def list_by_branch(
    session: AsyncSession, branch_id: uuid.UUID, offset: int = 0, limit: int = 50
) -> list[Student]:
    result = await session.execute(
        select(Student)
        .where(Student.branch_id == branch_id, Student.is_deleted == False)
        .offset(offset)
        .limit(limit)
    )
    return list(result.scalars().all())


async def update(session: AsyncSession, student: Student, **kwargs) -> Student:
    for key, value in kwargs.items():
        if value is not None:
            setattr(student, key, value)
    await session.flush()
    return student


async def soft_delete(session: AsyncSession, student: Student) -> None:
    student.is_deleted = True
    await session.flush()
