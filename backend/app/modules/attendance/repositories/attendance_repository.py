import uuid
from datetime import datetime

from sqlalchemy import and_, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.attendance.models.attendance_models import (
    AttendanceException,
    AttendanceRecord,
    RawPunchLog,
)


async def create_raw_punch_log(session: AsyncSession, **kwargs) -> RawPunchLog:
    log = RawPunchLog(**kwargs)
    session.add(log)
    await session.flush()
    return log


async def create_raw_punch_logs_batch(
    session: AsyncSession, logs: list[dict]
) -> list[RawPunchLog]:
    objects = [RawPunchLog(**log) for log in logs]
    session.add_all(objects)
    await session.flush()
    return objects


async def get_raw_punches_for_lecture(
    session: AsyncSession,
    student_ids: list[uuid.UUID],
    start: datetime,
    end: datetime,
    branch_id: uuid.UUID,
) -> list[RawPunchLog]:
    result = await session.execute(
        select(RawPunchLog)
        .where(
            RawPunchLog.student_id.in_(student_ids),
            RawPunchLog.punch_timestamp >= start,
            RawPunchLog.punch_timestamp <= end,
            RawPunchLog.branch_id == branch_id,
            RawPunchLog.is_deleted == False,
        )
        .order_by(RawPunchLog.punch_timestamp)
    )
    return list(result.scalars().all())


async def student_ids_with_punches(
    session: AsyncSession, branch_id: uuid.UUID
) -> set[uuid.UUID]:
    """Distinct students who have ever punched on this branch's device(s).

    A punch is physical proof the identity is on the device AND has a face
    enrolled (a face template can only be created at the terminal). This is the
    ground-truth enrolment signal — used by provisioning reconcile instead of the
    device-user mirror, which isn't reliably populated in prod.
    """
    result = await session.execute(
        select(RawPunchLog.student_id).where(
            RawPunchLog.branch_id == branch_id,
            RawPunchLog.is_deleted == False,
        )
    )
    return {row[0] for row in result.all()}


async def create_attendance_record(session: AsyncSession, **kwargs) -> AttendanceRecord:
    record = AttendanceRecord(**kwargs)
    session.add(record)
    await session.flush()
    return record


async def get_attendance_by_lecture(
    session: AsyncSession, lecture_id: uuid.UUID
) -> list[AttendanceRecord]:
    result = await session.execute(
        select(AttendanceRecord).where(
            AttendanceRecord.lecture_id == lecture_id,
            AttendanceRecord.is_deleted == False,
        )
    )
    return list(result.scalars().all())


async def get_attendance_by_student(
    session: AsyncSession, student_id: uuid.UUID, branch_id: uuid.UUID,
    offset: int = 0, limit: int = 50,
) -> list[AttendanceRecord]:
    result = await session.execute(
        select(AttendanceRecord)
        .where(
            AttendanceRecord.student_id == student_id,
            AttendanceRecord.branch_id == branch_id,
            AttendanceRecord.is_deleted == False,
        )
        .order_by(AttendanceRecord.marked_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_existing_attendance(
    session: AsyncSession, student_id: uuid.UUID, lecture_id: uuid.UUID
) -> AttendanceRecord | None:
    result = await session.execute(
        select(AttendanceRecord).where(
            AttendanceRecord.student_id == student_id,
            AttendanceRecord.lecture_id == lecture_id,
            AttendanceRecord.is_deleted == False,
        )
    )
    return result.scalar_one_or_none()


async def update_attendance_record(
    session: AsyncSession, record: AttendanceRecord, **kwargs
) -> AttendanceRecord:
    for key, value in kwargs.items():
        if value is not None:
            setattr(record, key, value)
    await session.flush()
    return record


async def create_exception(session: AsyncSession, **kwargs) -> AttendanceException:
    exc = AttendanceException(**kwargs)
    session.add(exc)
    await session.flush()
    return exc


async def get_exception_by_id(
    session: AsyncSession, exception_id: uuid.UUID
) -> AttendanceException | None:
    result = await session.execute(
        select(AttendanceException).where(
            AttendanceException.id == exception_id,
            AttendanceException.is_deleted == False,
        )
    )
    return result.scalar_one_or_none()


async def resolve_exception(
    session: AsyncSession, exc: AttendanceException, **kwargs
) -> AttendanceException:
    for key, value in kwargs.items():
        if value is not None:
            setattr(exc, key, value)
    await session.flush()
    return exc


async def get_attendance_summary(
    session: AsyncSession, lecture_id: uuid.UUID
) -> dict:
    result = await session.execute(
        select(
            AttendanceRecord.attendance_status,
            func.count(AttendanceRecord.id),
        )
        .where(
            AttendanceRecord.lecture_id == lecture_id,
            AttendanceRecord.is_deleted == False,
        )
        .group_by(AttendanceRecord.attendance_status)
    )
    counts = {row[0]: row[1] for row in result.all()}
    return counts
