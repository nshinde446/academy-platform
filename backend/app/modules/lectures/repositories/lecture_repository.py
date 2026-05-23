import uuid
from datetime import datetime

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.lectures.models.lecture_models import (
    Lecture,
    LectureAttendanceMapping,
    LectureSession,
    LectureSessionBatch,
    LectureSessionPlan,
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


async def create_session(session: AsyncSession, **kwargs) -> LectureSession:
    s = LectureSession(**kwargs)
    session.add(s)
    await session.flush()
    return s


async def link_session_batch(
    session: AsyncSession,
    session_id: uuid.UUID,
    batch_id: uuid.UUID,
    branch_id: uuid.UUID,
) -> LectureSessionBatch:
    link = LectureSessionBatch(
        session_id=session_id, batch_id=batch_id, branch_id=branch_id
    )
    session.add(link)
    await session.flush()
    return link


async def link_session_plan(
    session: AsyncSession,
    session_id: uuid.UUID,
    lecture_id: uuid.UUID,
    branch_id: uuid.UUID,
) -> LectureSessionPlan:
    link = LectureSessionPlan(
        session_id=session_id, lecture_id=lecture_id, branch_id=branch_id
    )
    session.add(link)
    await session.flush()
    return link


async def get_session_by_id(
    session: AsyncSession, session_id: uuid.UUID
) -> LectureSession | None:
    result = await session.execute(
        select(LectureSession).where(
            LectureSession.id == session_id, LectureSession.is_deleted == False
        )
    )
    return result.scalar_one_or_none()


async def list_sessions_by_branch(
    session: AsyncSession, branch_id: uuid.UUID, offset: int = 0, limit: int = 50
) -> list[LectureSession]:
    result = await session.execute(
        select(LectureSession)
        .where(LectureSession.branch_id == branch_id, LectureSession.is_deleted == False)
        .order_by(LectureSession.actual_start.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(result.scalars().all())


async def list_session_batches(
    session: AsyncSession, session_id: uuid.UUID
) -> list[LectureSessionBatch]:
    result = await session.execute(
        select(LectureSessionBatch).where(
            LectureSessionBatch.session_id == session_id,
            LectureSessionBatch.is_deleted == False,
        )
    )
    return list(result.scalars().all())


async def list_session_plans(
    session: AsyncSession, session_id: uuid.UUID
) -> list[LectureSessionPlan]:
    result = await session.execute(
        select(LectureSessionPlan).where(
            LectureSessionPlan.session_id == session_id,
            LectureSessionPlan.is_deleted == False,
        )
    )
    return list(result.scalars().all())


async def list_session_batches_for_sessions(
    session: AsyncSession, session_ids: list[uuid.UUID]
) -> list[LectureSessionBatch]:
    if not session_ids:
        return []
    result = await session.execute(
        select(LectureSessionBatch).where(
            LectureSessionBatch.session_id.in_(session_ids),
            LectureSessionBatch.is_deleted == False,
        )
    )
    return list(result.scalars().all())


async def list_session_plans_for_sessions(
    session: AsyncSession, session_ids: list[uuid.UUID]
) -> list[LectureSessionPlan]:
    if not session_ids:
        return []
    result = await session.execute(
        select(LectureSessionPlan).where(
            LectureSessionPlan.session_id.in_(session_ids),
            LectureSessionPlan.is_deleted == False,
        )
    )
    return list(result.scalars().all())
