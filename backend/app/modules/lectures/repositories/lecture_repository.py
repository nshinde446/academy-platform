import uuid
from datetime import datetime

from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.academic.models.academic_models import AcademicYear, Chapter, Topic, Subject
from app.modules.batch.models.batch_models import (
    Batch,
    BatchSchedule,
    BatchSubjectMapping,
)
from app.modules.tests.models.test_models import StudentMark, Test
from app.modules.lectures.models.lecture_models import (
    Holiday,
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


# --- Weekly timetable (batch_schedules) -------------------------------------

async def list_batch_schedule(
    session: AsyncSession, batch_id: uuid.UUID
) -> list[BatchSchedule]:
    result = await session.execute(
        select(BatchSchedule)
        .where(
            BatchSchedule.batch_id == batch_id,
            BatchSchedule.is_deleted == False,
        )
        .order_by(BatchSchedule.day_of_week, BatchSchedule.start_time)
    )
    return list(result.scalars().all())


async def list_branch_schedule(
    session: AsyncSession, branch_id: uuid.UUID
) -> list[BatchSchedule]:
    result = await session.execute(
        select(BatchSchedule)
        .where(
            BatchSchedule.branch_id == branch_id,
            BatchSchedule.is_deleted == False,
        )
        .order_by(BatchSchedule.day_of_week, BatchSchedule.start_time)
    )
    return list(result.scalars().all())


async def delete_batch_schedule(session: AsyncSession, batch_id: uuid.UUID) -> None:
    """Soft-delete every existing slot for a batch — used to replace the whole
    weekly pattern in one shot (set_batch_timetable)."""
    existing = await list_batch_schedule(session, batch_id)
    for slot in existing:
        slot.is_deleted = True
    await session.flush()


async def create_schedule_slot(session: AsyncSession, **kwargs) -> BatchSchedule:
    slot = BatchSchedule(**kwargs)
    session.add(slot)
    await session.flush()
    return slot


# --- Holiday calendar (S4) --------------------------------------------------

async def list_holidays(
    session: AsyncSession,
    branch_id: uuid.UUID,
    from_date=None,
    to_date=None,
) -> list[Holiday]:
    query = select(Holiday).where(
        Holiday.branch_id == branch_id,
        Holiday.is_deleted == False,
    )
    if from_date is not None:
        query = query.where(Holiday.holiday_date >= from_date)
    if to_date is not None:
        query = query.where(Holiday.holiday_date <= to_date)
    result = await session.execute(query.order_by(Holiday.holiday_date))
    return list(result.scalars().all())


async def get_holiday_by_id(
    session: AsyncSession, holiday_id: uuid.UUID
) -> Holiday | None:
    result = await session.execute(
        select(Holiday).where(
            Holiday.id == holiday_id, Holiday.is_deleted == False
        )
    )
    return result.scalar_one_or_none()


async def create_holiday(session: AsyncSession, **kwargs) -> Holiday:
    holiday = Holiday(**kwargs)
    session.add(holiday)
    await session.flush()
    return holiday


async def soft_delete_holiday(session: AsyncSession, holiday: Holiday) -> None:
    holiday.is_deleted = True
    await session.flush()


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


async def list_pending_actuals(
    session: AsyncSession, branch_id: uuid.UUID, now: datetime, limit: int = 100
) -> list[Lecture]:
    """Lectures whose scheduled end has passed but that were never closed out —
    still scheduled/started/paused with no recorded outcome. These need an
    end-of-day update (record actuals, or mark cancelled/no-show). Oldest first
    so the longest-overdue surface at the top."""
    result = await session.execute(
        select(Lecture)
        .where(
            Lecture.branch_id == branch_id,
            Lecture.is_deleted == False,
            Lecture.lecture_status.in_(
                ["scheduled", "rescheduled", "started", "paused"]
            ),
            Lecture.scheduled_end < now,
        )
        .order_by(Lecture.scheduled_start.asc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def list_pending_makeups(
    session: AsyncSession, branch_id: uuid.UUID, limit: int = 100
) -> list[Lecture]:
    """Cancelled / no-show lectures that haven't been made up yet — i.e. no
    LectureSession is linked to them. The missed topic is owed a makeup until
    one is recorded. Oldest first."""
    covered = select(LectureSessionPlan.lecture_id).where(
        LectureSessionPlan.is_deleted == False
    )
    result = await session.execute(
        select(Lecture)
        .where(
            Lecture.branch_id == branch_id,
            Lecture.is_deleted == False,
            Lecture.lecture_status.in_(["cancelled", "no_show"]),
            Lecture.id.not_in(covered),
        )
        .order_by(Lecture.scheduled_start.asc())
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


async def list_in_range(
    session: AsyncSession,
    branch_id: uuid.UUID,
    from_dt: datetime,
    to_dt: datetime,
    limit: int = 500,
) -> list[Lecture]:
    """All lectures whose scheduled_start falls in [from_dt, to_dt) — powers the
    week/calendar view. Ascending so the grid fills chronologically."""
    result = await session.execute(
        select(Lecture)
        .where(
            Lecture.branch_id == branch_id,
            Lecture.is_deleted == False,
            Lecture.scheduled_start >= from_dt,
            Lecture.scheduled_start < to_dt,
        )
        .order_by(Lecture.scheduled_start.asc())
        .limit(limit)
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


async def teacher_productivity_in_range(
    session: AsyncSession,
    branch_id: uuid.UUID,
    from_dt: datetime | None,
    to_dt: datetime | None,
) -> list[dict]:
    """Per effective-teacher productivity over completed lectures in window.

    The effective teacher is ``coalesce(actual_teacher_id, teacher_id)`` so a
    substitute earns the credit for the class they actually delivered. Returns
    raw counts; the service derives hours / punctuality / averages.
    """
    effective_teacher = func.coalesce(
        Lecture.actual_teacher_id, Lecture.teacher_id
    ).label("teacher_id")

    filters = [
        Lecture.branch_id == branch_id,
        Lecture.is_deleted == False,  # noqa: E712
        Lecture.lecture_status == "completed",
    ]
    if from_dt is not None:
        filters.append(Lecture.scheduled_start >= from_dt)
    if to_dt is not None:
        filters.append(Lecture.scheduled_start <= to_dt)

    late = Lecture.late_flag.is_(True)
    on_time = Lecture.late_flag.is_(False)

    stmt = (
        select(
            effective_teacher,
            func.count().label("lectures_taught"),
            func.coalesce(func.sum(Lecture.actual_duration_min), 0).label(
                "total_minutes"
            ),
            func.count(Lecture.actual_duration_min).label("timed_lectures"),
            func.count().filter(late).label("late_count"),
            func.count().filter(on_time).label("on_time_count"),
            func.count(func.distinct(Lecture.topic_id)).label("distinct_topics"),
        )
        .where(and_(*filters))
        .group_by(effective_teacher)
    )
    rows = (await session.execute(stmt)).all()
    return [
        {
            "teacher_id": r.teacher_id,
            "lectures_taught": int(r.lectures_taught or 0),
            "total_minutes": int(r.total_minutes or 0),
            "timed_lectures": int(r.timed_lectures or 0),
            "late_count": int(r.late_count or 0),
            "on_time_count": int(r.on_time_count or 0),
            "distinct_topics": int(r.distinct_topics or 0),
        }
        for r in rows
    ]


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


async def teacher_outcome_rows(
    session: AsyncSession,
    branch_id: uuid.UUID,
    from_dt: datetime | None,
    to_dt: datetime | None,
) -> list[dict]:
    """Per (teacher, subject) average test percentage.

    Algorithm:
      1. For each (teacher, subject), find batches where the teacher
         delivered at least one completed lecture in the date window.
      2. Find tests for those (batch, subject) pairs whose scheduled_at
         falls in the window.
      3. Average StudentMark.percentage across attended marks
         (is_absent=False).

    The teacher_id used is the EFFECTIVE teacher — if a substitute
    actually taught a lecture, the substitute earns the credit. We
    treat actual_teacher_id IS NOT NULL as the override.
    """
    # Step 1: teacher × subject × batch participation.
    base_filters = [
        Lecture.branch_id == branch_id,
        Lecture.is_deleted == False,
        Lecture.lecture_status == "completed",
    ]
    if from_dt is not None:
        base_filters.append(Lecture.scheduled_start >= from_dt)
    if to_dt is not None:
        base_filters.append(Lecture.scheduled_start <= to_dt)

    effective_teacher = func.coalesce(
        Lecture.actual_teacher_id, Lecture.teacher_id
    ).label("effective_teacher_id")

    participation_stmt = (
        select(
            effective_teacher,
            Lecture.subject_id,
            Lecture.batch_id,
        )
        .where(and_(*base_filters))
        .distinct()
    )
    participation = (await session.execute(participation_stmt)).all()
    if not participation:
        return []

    # Group by (teacher, subject) → set of batches.
    by_key: dict[tuple[uuid.UUID, uuid.UUID], set[uuid.UUID]] = {}
    for row in participation:
        key = (row.effective_teacher_id, row.subject_id)
        by_key.setdefault(key, set()).add(row.batch_id)

    # Step 2 + 3: for each (teacher, subject), join through tests for
    # their batches and average the non-absent percentages.
    results: list[dict] = []
    for (teacher_id, subject_id), batch_ids in by_key.items():
        tests_filters = [
            Test.branch_id == branch_id,
            Test.is_deleted == False,
            Test.subject_id == subject_id,
            Test.batch_id.in_(batch_ids),
        ]
        if from_dt is not None:
            tests_filters.append(Test.scheduled_at >= from_dt)
        if to_dt is not None:
            tests_filters.append(Test.scheduled_at <= to_dt)

        # First confirm there are tests in scope.
        test_ids_stmt = select(Test.id).where(and_(*tests_filters))
        test_ids = [r[0] for r in (await session.execute(test_ids_stmt)).all()]
        if not test_ids:
            continue

        marks_stmt = select(
            func.avg(StudentMark.percentage),
            func.count(func.distinct(StudentMark.student_id)),
        ).where(
            StudentMark.test_id.in_(test_ids),
            StudentMark.is_deleted == False,
            StudentMark.is_absent == False,
        )
        row = (await session.execute(marks_stmt)).one()
        avg_pct, students = row[0], int(row[1] or 0)
        if avg_pct is None or students == 0:
            continue

        results.append(
            {
                "teacher_id": teacher_id,
                "subject_id": subject_id,
                "tests_count": len(test_ids),
                "students_count": students,
                "avg_score_pct": round(float(avg_pct), 1),
            }
        )

    return results


async def attendance_outcome_pairs(
    session: AsyncSession,
    branch_id: uuid.UUID,
    from_dt: datetime | None,
    to_dt: datetime | None,
) -> list[dict]:
    """Per-student (attendance_pct, avg_test_pct) pairs across the branch.

    Attendance is computed across ALL lectures (any subject) in the
    window — gives the headline "does showing up correlate with
    scoring" answer, even if not subject-matched. Subject-matched
    correlation is a possible follow-up.
    """
    # Attendance per student.
    att_filters = [
        Lecture.branch_id == branch_id,
        Lecture.is_deleted == False,
        Lecture.lecture_status == "completed",
    ]
    if from_dt is not None:
        att_filters.append(Lecture.scheduled_start >= from_dt)
    if to_dt is not None:
        att_filters.append(Lecture.scheduled_start <= to_dt)

    att_stmt = (
        select(
            LectureAttendanceMapping.student_id.label("sid"),
            func.count().label("total"),
            func.count()
            .filter(LectureAttendanceMapping.attendance_status == "PRESENT")
            .label("present"),
        )
        .join(Lecture, Lecture.id == LectureAttendanceMapping.lecture_id)
        .where(
            LectureAttendanceMapping.is_deleted == False,
            and_(*att_filters),
        )
        .group_by(LectureAttendanceMapping.student_id)
    )
    att_rows = (await session.execute(att_stmt)).all()

    # Avg score per student.
    score_filters = [
        StudentMark.branch_id == branch_id,
        StudentMark.is_deleted == False,
        StudentMark.is_absent == False,
    ]
    if from_dt is not None or to_dt is not None:
        score_filters_test = [
            Test.is_deleted == False,
            Test.branch_id == branch_id,
        ]
        if from_dt is not None:
            score_filters_test.append(Test.scheduled_at >= from_dt)
        if to_dt is not None:
            score_filters_test.append(Test.scheduled_at <= to_dt)
        score_stmt = (
            select(
                StudentMark.student_id.label("sid"),
                func.avg(StudentMark.percentage).label("avg_pct"),
            )
            .join(Test, Test.id == StudentMark.test_id)
            .where(and_(*score_filters), and_(*score_filters_test))
            .group_by(StudentMark.student_id)
        )
    else:
        score_stmt = (
            select(
                StudentMark.student_id.label("sid"),
                func.avg(StudentMark.percentage).label("avg_pct"),
            )
            .where(and_(*score_filters))
            .group_by(StudentMark.student_id)
        )

    score_rows = (await session.execute(score_stmt)).all()

    att_by_sid = {
        r.sid: round(100.0 * r.present / r.total, 1) if r.total > 0 else 0.0
        for r in att_rows
    }
    score_by_sid = {r.sid: round(float(r.avg_pct or 0.0), 1) for r in score_rows}

    # Inner join — students with both signals.
    pairs: list[dict] = []
    for sid, att_pct in att_by_sid.items():
        if sid not in score_by_sid:
            continue
        pairs.append(
            {
                "student_id": sid,
                "attendance_pct": att_pct,
                "avg_test_pct": score_by_sid[sid],
            }
        )
    return pairs


async def branch_test_summary(
    session: AsyncSession,
    branch_id: uuid.UUID,
    from_dt: datetime | None,
    to_dt: datetime | None,
) -> dict:
    """Branch-wide test summary in window."""
    test_filters = [Test.branch_id == branch_id, Test.is_deleted == False]
    if from_dt is not None:
        test_filters.append(Test.scheduled_at >= from_dt)
    if to_dt is not None:
        test_filters.append(Test.scheduled_at <= to_dt)
    tests_count = (
        await session.execute(
            select(func.count(Test.id)).where(and_(*test_filters))
        )
    ).scalar_one()

    marks_stmt = select(
        func.count(func.distinct(StudentMark.student_id)),
        func.avg(StudentMark.percentage),
    ).where(
        StudentMark.branch_id == branch_id,
        StudentMark.is_deleted == False,
        StudentMark.is_absent == False,
    )
    if from_dt is not None or to_dt is not None:
        marks_stmt = marks_stmt.join(Test, Test.id == StudentMark.test_id).where(
            and_(*test_filters)
        )
    row = (await session.execute(marks_stmt)).one()
    return {
        "tests_evaluated": int(tests_count or 0),
        "students_with_marks": int(row[0] or 0),
        "branch_avg_score": round(float(row[1] or 0.0), 1),
    }
