import uuid
from datetime import datetime

from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.academic.models.academic_models import AcademicYear, Chapter, Topic
from app.modules.batch.models.batch_models import Batch, BatchSubjectMapping
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


async def list_lectures_for_day(
    session: AsyncSession,
    branch_id: uuid.UUID,
    day_start: datetime,
    day_end: datetime,
) -> list[Lecture]:
    """All lectures whose scheduled_start falls in the day window."""
    result = await session.execute(
        select(Lecture)
        .where(
            Lecture.branch_id == branch_id,
            Lecture.is_deleted == False,
            Lecture.scheduled_start >= day_start,
            Lecture.scheduled_start <= day_end,
        )
        .order_by(Lecture.scheduled_start.asc())
    )
    return list(result.scalars().all())


async def list_sessions_for_day(
    session: AsyncSession,
    branch_id: uuid.UUID,
    day_start: datetime,
    day_end: datetime,
) -> list[LectureSession]:
    """All sessions whose actual_start falls in the day window."""
    result = await session.execute(
        select(LectureSession)
        .where(
            LectureSession.branch_id == branch_id,
            LectureSession.is_deleted == False,
            LectureSession.actual_start >= day_start,
            LectureSession.actual_start <= day_end,
        )
        .order_by(LectureSession.actual_start.asc())
    )
    return list(result.scalars().all())


async def list_session_plans_by_lecture_ids(
    session: AsyncSession, lecture_ids: list[uuid.UUID]
) -> list[LectureSessionPlan]:
    """All session-plan links for the given lecture IDs (any date) —
    drives the 'made up' indicator for today's missed lectures."""
    if not lecture_ids:
        return []
    result = await session.execute(
        select(LectureSessionPlan).where(
            LectureSessionPlan.lecture_id.in_(lecture_ids),
            LectureSessionPlan.is_deleted == False,
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
    no_show = Lecture.lecture_status == "no_show"
    rescheduled = Lecture.lecture_status == "rescheduled"

    stmt = select(
        func.count().label("planned"),
        func.count().filter(completed & ~substituted).label("completed_as_planned"),
        func.count().filter(substituted).label("substituted"),
        func.count().filter(cancelled).label("cancelled"),
        func.count().filter(no_show).label("no_show"),
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
        "no_show": int(row.no_show or 0),
        "rescheduled": int(row.rescheduled or 0),
    }


async def no_show_breakdown_in_range(
    session: AsyncSession,
    branch_id: uuid.UUID,
    from_dt: datetime | None,
    to_dt: datetime | None,
) -> dict[str, int]:
    """Count no_show lectures grouped by no_show_reason.

    Distinguishes teacher-attributable no-shows (the real reliability
    signal) from student / external / other ones. Filtered on
    scheduled_start matching the totals query.
    """
    stmt = (
        select(Lecture.no_show_reason, func.count())
        .where(
            Lecture.branch_id == branch_id,
            Lecture.is_deleted == False,
            Lecture.lecture_status == "no_show",
        )
        .group_by(Lecture.no_show_reason)
    )
    if from_dt is not None:
        stmt = stmt.where(Lecture.scheduled_start >= from_dt)
    if to_dt is not None:
        stmt = stmt.where(Lecture.scheduled_start <= to_dt)

    rows = (await session.execute(stmt)).all()
    by_reason = {r[0]: int(r[1] or 0) for r in rows}
    return {
        "teacher": by_reason.get("TEACHER_NO_SHOW", 0),
        "student": by_reason.get("STUDENT_NO_SHOW", 0),
        "external": by_reason.get("EXTERNAL", 0),
        "other": by_reason.get("OTHER", 0)
        + by_reason.get(None, 0),
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


async def batch_syllabus_coverage(
    session: AsyncSession,
    branch_id: uuid.UUID,
) -> list[dict]:
    """Per-batch syllabus coverage.

    total_topics    = topics whose subject is mapped to the batch via
                      batch_subject_mappings (this branch only).
    delivered_topics = distinct topic_ids actually taught — completed
                      lectures + recorded sessions tied to the batch.

    Returned shape per batch:
        {
          "batch_id": UUID, "batch_name": str, "batch_code": str,
          "total_topics": int, "delivered_topics": int, "coverage_pct": float,
        }
    """
    # All active batches in this branch.
    batch_rows = (
        await session.execute(
            select(Batch).where(
                Batch.branch_id == branch_id, Batch.is_deleted == False
            )
        )
    ).scalars().all()
    if not batch_rows:
        return []

    batch_ids = [b.id for b in batch_rows]

    # Step 1: subject_ids per batch via batch_subject_mappings.
    msm_rows = (
        await session.execute(
            select(BatchSubjectMapping.batch_id, BatchSubjectMapping.subject_id).where(
                BatchSubjectMapping.batch_id.in_(batch_ids),
                BatchSubjectMapping.is_deleted == False,
            )
        )
    ).all()
    subjects_by_batch: dict[uuid.UUID, list[uuid.UUID]] = {}
    for r in msm_rows:
        subjects_by_batch.setdefault(r.batch_id, []).append(r.subject_id)

    # Step 2: total topics per batch = SUM of topics whose chapter.subject_id is
    # in the batch's mapped subjects.
    total_by_batch: dict[uuid.UUID, int] = {bid: 0 for bid in batch_ids}
    all_subject_ids = {sid for ids in subjects_by_batch.values() for sid in ids}
    topic_count_by_subject: dict[uuid.UUID, int] = {}
    if all_subject_ids:
        topic_rows = (
            await session.execute(
                select(Chapter.subject_id, func.count(Topic.id))
                .join(Topic, Topic.chapter_id == Chapter.id)
                .where(
                    Chapter.subject_id.in_(all_subject_ids),
                    Chapter.is_deleted == False,
                    Topic.is_deleted == False,
                )
                .group_by(Chapter.subject_id)
            )
        ).all()
        topic_count_by_subject = {r[0]: int(r[1]) for r in topic_rows}
    for bid, sids in subjects_by_batch.items():
        total_by_batch[bid] = sum(topic_count_by_subject.get(sid, 0) for sid in sids)

    # Step 3: delivered topic_ids per batch.
    #   a) completed lectures with topic_id
    completed_topic_rows = (
        await session.execute(
            select(Lecture.batch_id, Lecture.topic_id).where(
                Lecture.batch_id.in_(batch_ids),
                Lecture.is_deleted == False,
                Lecture.lecture_status == "completed",
                Lecture.topic_id.is_not(None),
            )
        )
    ).all()
    delivered_topic_ids_by_batch: dict[uuid.UUID, set[uuid.UUID]] = {
        bid: set() for bid in batch_ids
    }
    for r in completed_topic_rows:
        delivered_topic_ids_by_batch[r.batch_id].add(r.topic_id)

    #   b) sessions linked to batch with topic_id set
    session_topic_rows = (
        await session.execute(
            select(LectureSessionBatch.batch_id, LectureSession.topic_id)
            .join(
                LectureSession,
                LectureSession.id == LectureSessionBatch.session_id,
            )
            .where(
                LectureSessionBatch.batch_id.in_(batch_ids),
                LectureSessionBatch.is_deleted == False,
                LectureSession.is_deleted == False,
                LectureSession.topic_id.is_not(None),
            )
        )
    ).all()
    for r in session_topic_rows:
        delivered_topic_ids_by_batch.setdefault(r.batch_id, set()).add(
            r.topic_id
        )

    # Load academic year start/end years for each batch so the service can
    # compute time-weighted pace (Tier 7). We deliberately stop at raw data
    # here — the pacing formula and thresholds live in the service layer.
    ay_ids = {b.start_academic_year_id for b in batch_rows} | {
        b.end_academic_year_id for b in batch_rows
    }
    academic_years: dict[uuid.UUID, AcademicYear] = {}
    if ay_ids:
        ay_result = await session.execute(
            select(AcademicYear).where(AcademicYear.id.in_(ay_ids))
        )
        academic_years = {ay.id: ay for ay in ay_result.scalars().all()}

    # Assemble.
    result: list[dict] = []
    for b in batch_rows:
        total = total_by_batch.get(b.id, 0)
        delivered = len(delivered_topic_ids_by_batch.get(b.id, set()))
        coverage = round((delivered * 100) / total, 1) if total > 0 else 0.0
        start_ay = academic_years.get(b.start_academic_year_id)
        end_ay = academic_years.get(b.end_academic_year_id)
        result.append(
            {
                "batch_id": b.id,
                "batch_name": b.name,
                "batch_code": b.code,
                "course_id": b.course_id,
                "total_topics": total,
                "delivered_topics": delivered,
                "coverage_pct": coverage,
                "target_exam_date": b.target_exam_date,
                "start_year": start_ay.start_year if start_ay else None,
                "end_year": end_ay.end_year if end_ay else None,
            }
        )
    result.sort(key=lambda r: r["coverage_pct"])
    return result


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
