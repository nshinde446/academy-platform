import uuid
from datetime import datetime

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.lectures.models.lecture_models import (
    Lecture,
    LectureAttendanceMapping,
    LectureTopicMapping,
)


async def create(session: AsyncSession, **kwargs) -> Lecture:
    lecture = Lecture(**kwargs)
    session.add(lecture)
    await session.flush()
    return lecture


async def get_by_id(session: AsyncSession, lecture_id: uuid.UUID) -> Lecture | None:
    result = await session.execute(
        select(Lecture).where(Lecture.id == lecture_id, Lecture.is_deleted == False)
    )
    return result.scalar_one_or_none()


async def list_by_branch(
    session: AsyncSession, branch_id: uuid.UUID, offset: int = 0, limit: int = 50
) -> list[Lecture]:
    result = await session.execute(
        select(Lecture)
        .where(Lecture.branch_id == branch_id, Lecture.is_deleted == False)
        .order_by(Lecture.scheduled_start.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(result.scalars().all())


async def update(session: AsyncSession, lecture: Lecture, **kwargs) -> Lecture:
    for key, value in kwargs.items():
        if value is not None:
            setattr(lecture, key, value)
    await session.flush()
    return lecture


async def soft_delete(session: AsyncSession, lecture: Lecture) -> None:
    lecture.is_deleted = True
    await session.flush()


async def check_teacher_conflict(
    session: AsyncSession,
    teacher_id: uuid.UUID,
    scheduled_start: datetime,
    scheduled_end: datetime,
    exclude_lecture_id: uuid.UUID | None = None,
) -> bool:
    query = select(Lecture.id).where(
        Lecture.teacher_id == teacher_id,
        Lecture.is_deleted == False,
        Lecture.lecture_status.in_(["scheduled", "started", "paused"]),
        Lecture.scheduled_start < scheduled_end,
        Lecture.scheduled_end > scheduled_start,
    )
    if exclude_lecture_id:
        query = query.where(Lecture.id != exclude_lecture_id)
    result = await session.execute(query.limit(1))
    return result.scalar_one_or_none() is not None


async def check_classroom_conflict(
    session: AsyncSession,
    classroom_id: uuid.UUID,
    scheduled_start: datetime,
    scheduled_end: datetime,
    exclude_lecture_id: uuid.UUID | None = None,
) -> bool:
    query = select(Lecture.id).where(
        Lecture.classroom_id == classroom_id,
        Lecture.is_deleted == False,
        Lecture.lecture_status.in_(["scheduled", "started", "paused"]),
        Lecture.scheduled_start < scheduled_end,
        Lecture.scheduled_end > scheduled_start,
    )
    if exclude_lecture_id:
        query = query.where(Lecture.id != exclude_lecture_id)
    result = await session.execute(query.limit(1))
    return result.scalar_one_or_none() is not None


async def check_batch_conflict(
    session: AsyncSession,
    batch_id: uuid.UUID,
    scheduled_start: datetime,
    scheduled_end: datetime,
    exclude_lecture_id: uuid.UUID | None = None,
) -> bool:
    query = select(Lecture.id).where(
        Lecture.batch_id == batch_id,
        Lecture.is_deleted == False,
        Lecture.lecture_status.in_(["scheduled", "started", "paused"]),
        Lecture.scheduled_start < scheduled_end,
        Lecture.scheduled_end > scheduled_start,
    )
    if exclude_lecture_id:
        query = query.where(Lecture.id != exclude_lecture_id)
    result = await session.execute(query.limit(1))
    return result.scalar_one_or_none() is not None


async def create_attendance(
    session: AsyncSession, **kwargs
) -> LectureAttendanceMapping:
    att = LectureAttendanceMapping(**kwargs)
    session.add(att)
    await session.flush()
    return att


async def get_attendance(
    session: AsyncSession, lecture_id: uuid.UUID
) -> list[LectureAttendanceMapping]:
    result = await session.execute(
        select(LectureAttendanceMapping).where(
            LectureAttendanceMapping.lecture_id == lecture_id,
            LectureAttendanceMapping.is_deleted == False,
        )
    )
    return list(result.scalars().all())
