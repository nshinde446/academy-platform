import uuid
from datetime import datetime

from sqlalchemy import and_, case, func, select
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


async def lecture_totals_in_range(
    session: AsyncSession,
    branch_id: uuid.UUID,
    from_dt: datetime | None,
    to_dt: datetime | None,
) -> dict[str, int]:
    """Aggregate lecture counts for an adherence dashboard.

    Counts are filtered to a date window on scheduled_start. The
    ``completed_as_planned`` bucket is "completed AND no substitute" — so
    substituted lectures are pulled out into their own bucket and aren't
    double-counted.
    """
    completed = Lecture.lecture_status == "completed"
    substituted = Lecture.actual_teacher_id.is_not(None)
    cancelled = Lecture.lecture_status == "cancelled"
    rescheduled = Lecture.lecture_status == "rescheduled"

    stmt = select(
        func.count().label("planned"),
        func.count().filter(completed & ~substituted).label("completed_as_planned"),
        func.count().filter(substituted).label("substituted"),
        func.count().filter(cancelled).label("cancelled"),
        func.count().filter(rescheduled).label("rescheduled"),
    ).where(Lecture.branch_id == branch_id, Lecture.is_deleted == False)
    if from_dt is not None:
        stmt = stmt.where(Lecture.scheduled_start >= from_dt)
    if to_dt is not None:
        stmt = stmt.where(Lecture.scheduled_start <= to_dt)

    row = (await session.execute(stmt)).one()
    return {
        "planned": int(row.planned or 0),
        "completed_as_planned": int(row.completed_as_planned or 0),
        "substituted": int(row.substituted or 0),
        "cancelled": int(row.cancelled or 0),
        "rescheduled": int(row.rescheduled or 0),
    }


async def session_origin_totals_in_range(
    session: AsyncSession,
    branch_id: uuid.UUID,
    from_dt: datetime | None,
    to_dt: datetime | None,
) -> dict[str, int]:
    """Group lecture_sessions by origin and separately count merged sessions
    (those with 2+ plan links). Filtered by actual_start.
    """
    base = select(LectureSession.id, LectureSession.origin).where(
        LectureSession.branch_id == branch_id,
        LectureSession.is_deleted == False,
    )
    if from_dt is not None:
        base = base.where(LectureSession.actual_start >= from_dt)
    if to_dt is not None:
        base = base.where(LectureSession.actual_start <= to_dt)

    sub = base.subquery()
    origin_stmt = select(sub.c.origin, func.count()).group_by(sub.c.origin)
    rows = (await session.execute(origin_stmt)).all()
    by_origin = {r[0]: int(r[1] or 0) for r in rows}

    # Merged = sessions with >= 2 distinct linked plans.
    merged_stmt = (
        select(func.count())
        .select_from(
            select(LectureSessionPlan.session_id)
            .where(
                LectureSessionPlan.is_deleted == False,
                LectureSessionPlan.session_id.in_(select(sub.c.id)),
            )
            .group_by(LectureSessionPlan.session_id)
            .having(func.count(LectureSessionPlan.lecture_id) >= 2)
            .subquery()
        )
    )
    merged_count = int((await session.execute(merged_stmt)).scalar() or 0)

    return {
        "planned": by_origin.get("planned", 0),
        "makeup": by_origin.get("makeup", 0),
        "ad_hoc": by_origin.get("ad_hoc", 0),
        "merged": merged_count,
    }


async def per_teacher_adherence_in_range(
    session: AsyncSession,
    branch_id: uuid.UUID,
    from_dt: datetime | None,
    to_dt: datetime | None,
) -> list[dict]:
    """Return per-teacher KPI rows.

    Two passes joined in Python:
      1) group by Lecture.teacher_id — planned / substituted_out / cancelled
      2) group by Lecture.actual_teacher_id (not null) — substituted_in

    Sorted by substitute_rate_pct desc by the caller's service layer.
    """
    substituted = Lecture.actual_teacher_id.is_not(None)
    cancelled = Lecture.lecture_status == "cancelled"

    base_filters = [Lecture.branch_id == branch_id, Lecture.is_deleted == False]
    if from_dt is not None:
        base_filters.append(Lecture.scheduled_start >= from_dt)
    if to_dt is not None:
        base_filters.append(Lecture.scheduled_start <= to_dt)

    out_stmt = (
        select(
            Lecture.teacher_id.label("teacher_id"),
            func.count().label("planned"),
            func.count().filter(substituted).label("substituted_out"),
            func.count().filter(cancelled).label("cancelled"),
        )
        .where(and_(*base_filters))
        .group_by(Lecture.teacher_id)
    )
    in_stmt = (
        select(
            Lecture.actual_teacher_id.label("teacher_id"),
            func.count().label("substituted_in"),
        )
        .where(and_(*base_filters, substituted))
        .group_by(Lecture.actual_teacher_id)
    )

    out_rows = (await session.execute(out_stmt)).all()
    in_rows = (await session.execute(in_stmt)).all()

    by_id: dict[uuid.UUID, dict] = {}
    for r in out_rows:
        by_id[r.teacher_id] = {
            "teacher_id": r.teacher_id,
            "planned": int(r.planned or 0),
            "substituted_out": int(r.substituted_out or 0),
            "substituted_in": 0,
            "cancelled": int(r.cancelled or 0),
        }
    for r in in_rows:
        bucket = by_id.setdefault(
            r.teacher_id,
            {
                "teacher_id": r.teacher_id,
                "planned": 0,
                "substituted_out": 0,
                "substituted_in": 0,
                "cancelled": 0,
            },
        )
        bucket["substituted_in"] = int(r.substituted_in or 0)
    return list(by_id.values())


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
