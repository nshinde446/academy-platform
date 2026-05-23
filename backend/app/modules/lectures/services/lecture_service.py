import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.services import audit_service
from app.modules.batch.repositories import batch_repository
from app.modules.events.services import event_service
from app.modules.lectures.repositories import lecture_repository
from app.modules.teacher.models.teacher_models import Teacher
from app.modules.lectures.schemas.lecture_schemas import (
    AttendanceMark,
    LectureCreate,
    LectureNoShow,
    LectureReschedule,
    LectureSessionCreate,
    LectureSubstitute,
)

VALID_TRANSITIONS = {
    "scheduled": ["started", "cancelled", "no_show", "rescheduled"],
    "started": ["paused", "completed", "cancelled"],
    "paused": ["started", "completed", "cancelled"],
    "completed": [],
    "cancelled": [],
    "no_show": [],
    "rescheduled": ["scheduled"],
}
VALID_NO_SHOW_REASONS = {
    "TEACHER_NO_SHOW",
    "STUDENT_NO_SHOW",
    "EXTERNAL",
    "OTHER",
}

VALID_DELIVERY_MODES = {"offline", "online", "hybrid"}
VALID_SESSION_ORIGINS = {"planned", "makeup", "ad_hoc"}
VALID_SESSION_STATUSES = {"in_progress", "completed", "aborted"}
VALID_ATTENDANCE_STATUSES = {"PRESENT", "ABSENT", "LATE", "PARTIAL", "EXCUSED", "MANUAL_OVERRIDE"}
VALID_CHANGE_REASONS = {
    "SUBSTITUTE",
    "SUBJECT_SWAP",
    "TOPIC_CHANGE",
    "COMBINED_BATCH",
    "OTHER",
}


def _validate_transition(current: str, target: str):
    allowed = VALID_TRANSITIONS.get(current, [])
    if target not in allowed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Cannot transition from '{current}' to '{target}'",
        )


async def _check_conflicts(
    session: AsyncSession,
    teacher_id: uuid.UUID,
    batch_id: uuid.UUID,
    classroom_id: uuid.UUID | None,
    scheduled_start: datetime,
    scheduled_end: datetime,
    exclude_lecture_id: uuid.UUID | None = None,
):
    if await lecture_repository.check_teacher_conflict(
        session, teacher_id, scheduled_start, scheduled_end, exclude_lecture_id
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Teacher has a scheduling conflict",
        )

    if await lecture_repository.check_batch_conflict(
        session, batch_id, scheduled_start, scheduled_end, exclude_lecture_id
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Batch has a scheduling conflict",
        )

    if classroom_id and await lecture_repository.check_classroom_conflict(
        session, classroom_id, scheduled_start, scheduled_end, exclude_lecture_id
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Classroom has a scheduling conflict",
        )


async def schedule_lecture(
    session: AsyncSession,
    data: LectureCreate,
    current_user_id: uuid.UUID,
    ip_address: str | None = None,
):
    if data.delivery_mode not in VALID_DELIVERY_MODES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid delivery mode: {data.delivery_mode}",
        )

    if data.delivery_mode == "offline" and not data.classroom_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Offline lectures require a classroom_id",
        )

    batch = await batch_repository.get_by_id(session, data.batch_id)
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")

    await _check_conflicts(
        session, data.teacher_id, data.batch_id, data.classroom_id,
        data.scheduled_start, data.scheduled_end,
    )

    lecture = await lecture_repository.create(
        session,
        teacher_id=data.teacher_id,
        batch_id=data.batch_id,
        classroom_id=data.classroom_id,
        subject_id=data.subject_id,
        topic_id=data.topic_id,
        scheduled_start=data.scheduled_start,
        scheduled_end=data.scheduled_end,
        delivery_mode=data.delivery_mode,
        lecture_status="scheduled",
        notes=data.notes,
        branch_id=batch.branch_id,
        academic_year_id=batch.start_academic_year_id,
    )

    await audit_service.log_action(
        session,
        user_id=current_user_id,
        action="CREATE",
        table_name="lectures",
        record_id=lecture.id,
        new_values=data.model_dump(),
        ip_address=ip_address,
        branch_id=batch.branch_id,
    )
    return lecture


async def get_lecture(session: AsyncSession, lecture_id: uuid.UUID, branch_id: uuid.UUID):
    lecture = await lecture_repository.get_by_id(session, lecture_id)
    if not lecture:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lecture not found")
    if lecture.branch_id != branch_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this branch")
    return lecture


async def list_lectures(session: AsyncSession, branch_id: uuid.UUID, offset: int = 0, limit: int = 50):
    return await lecture_repository.list_by_branch(session, branch_id, offset, limit)


async def start_lecture(
    session: AsyncSession,
    lecture_id: uuid.UUID,
    branch_id: uuid.UUID,
    current_user_id: uuid.UUID,
    ip_address: str | None = None,
):
    lecture = await lecture_repository.get_by_id(session, lecture_id)
    if not lecture:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lecture not found")
    if lecture.branch_id != branch_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this branch")

    _validate_transition(lecture.lecture_status, "started")

    now = datetime.now(timezone.utc)
    lecture = await lecture_repository.update(
        session, lecture, lecture_status="started", actual_start=now
    )

    await audit_service.log_action(
        session,
        user_id=current_user_id,
        action="UPDATE",
        table_name="lectures",
        record_id=lecture.id,
        old_values={"lecture_status": "scheduled"},
        new_values={"lecture_status": "started", "actual_start": str(now)},
        ip_address=ip_address,
        branch_id=lecture.branch_id,
    )

    await event_service.emit_event(
        session,
        event_type="LECTURE_STARTED",
        lecture_id=lecture.id,
        teacher_id=lecture.teacher_id,
        batch_id=lecture.batch_id,
        subject_id=lecture.subject_id,
        branch_id=lecture.branch_id,
        metadata={"actual_start": str(now)},
    )
    return lecture


async def complete_lecture(
    session: AsyncSession,
    lecture_id: uuid.UUID,
    branch_id: uuid.UUID,
    current_user_id: uuid.UUID,
    ip_address: str | None = None,
):
    lecture = await lecture_repository.get_by_id(session, lecture_id)
    if not lecture:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lecture not found")
    if lecture.branch_id != branch_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this branch")

    _validate_transition(lecture.lecture_status, "completed")

    now = datetime.now(timezone.utc)
    old_status = lecture.lecture_status
    lecture = await lecture_repository.update(
        session, lecture, lecture_status="completed", actual_end=now
    )

    await audit_service.log_action(
        session,
        user_id=current_user_id,
        action="UPDATE",
        table_name="lectures",
        record_id=lecture.id,
        old_values={"lecture_status": old_status},
        new_values={"lecture_status": "completed", "actual_end": str(now)},
        ip_address=ip_address,
        branch_id=lecture.branch_id,
    )

    await event_service.emit_event(
        session,
        event_type="LECTURE_COMPLETED",
        lecture_id=lecture.id,
        teacher_id=lecture.teacher_id,
        batch_id=lecture.batch_id,
        subject_id=lecture.subject_id,
        branch_id=lecture.branch_id,
        metadata={"actual_end": str(now)},
    )
    return lecture


async def cancel_lecture(
    session: AsyncSession,
    lecture_id: uuid.UUID,
    branch_id: uuid.UUID,
    current_user_id: uuid.UUID,
    ip_address: str | None = None,
):
    lecture = await lecture_repository.get_by_id(session, lecture_id)
    if not lecture:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lecture not found")
    if lecture.branch_id != branch_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this branch")

    _validate_transition(lecture.lecture_status, "cancelled")

    old_status = lecture.lecture_status
    lecture = await lecture_repository.update(session, lecture, lecture_status="cancelled")

    await audit_service.log_action(
        session,
        user_id=current_user_id,
        action="UPDATE",
        table_name="lectures",
        record_id=lecture.id,
        old_values={"lecture_status": old_status},
        new_values={"lecture_status": "cancelled"},
        ip_address=ip_address,
        branch_id=lecture.branch_id,
    )
    return lecture


async def reschedule_lecture(
    session: AsyncSession,
    lecture_id: uuid.UUID,
    data: LectureReschedule,
    branch_id: uuid.UUID,
    current_user_id: uuid.UUID,
    ip_address: str | None = None,
):
    lecture = await lecture_repository.get_by_id(session, lecture_id)
    if not lecture:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lecture not found")
    if lecture.branch_id != branch_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this branch")

    _validate_transition(lecture.lecture_status, "rescheduled")

    classroom_id = data.classroom_id if data.classroom_id else lecture.classroom_id
    await _check_conflicts(
        session, lecture.teacher_id, lecture.batch_id, classroom_id,
        data.scheduled_start, data.scheduled_end, exclude_lecture_id=lecture.id,
    )

    old_values = {
        "scheduled_start": str(lecture.scheduled_start),
        "scheduled_end": str(lecture.scheduled_end),
        "lecture_status": lecture.lecture_status,
    }

    lecture = await lecture_repository.update(
        session, lecture,
        scheduled_start=data.scheduled_start,
        scheduled_end=data.scheduled_end,
        classroom_id=classroom_id,
        lecture_status="rescheduled",
    )

    await audit_service.log_action(
        session,
        user_id=current_user_id,
        action="UPDATE",
        table_name="lectures",
        record_id=lecture.id,
        old_values=old_values,
        new_values={"scheduled_start": str(data.scheduled_start), "scheduled_end": str(data.scheduled_end), "lecture_status": "rescheduled"},
        ip_address=ip_address,
        branch_id=lecture.branch_id,
    )
    return lecture


async def mark_attendance(
    session: AsyncSession,
    lecture_id: uuid.UUID,
    data: AttendanceMark,
    branch_id: uuid.UUID,
    current_user_id: uuid.UUID,
    ip_address: str | None = None,
):
    lecture = await lecture_repository.get_by_id(session, lecture_id)
    if not lecture:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lecture not found")
    if lecture.branch_id != branch_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this branch")

    if data.attendance_status not in VALID_ATTENDANCE_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid attendance status: {data.attendance_status}",
        )

    now = datetime.now(timezone.utc)
    att = await lecture_repository.create_attendance(
        session,
        lecture_id=lecture_id,
        student_id=data.student_id,
        attendance_status=data.attendance_status,
        marked_at=now,
        branch_id=lecture.branch_id,
    )

    await audit_service.log_action(
        session,
        user_id=current_user_id,
        action="CREATE",
        table_name="lecture_attendance_mappings",
        record_id=att.id,
        new_values={"lecture_id": str(lecture_id), "student_id": str(data.student_id), "attendance_status": data.attendance_status},
        ip_address=ip_address,
        branch_id=lecture.branch_id,
    )
    return att


async def get_attendance(
    session: AsyncSession,
    lecture_id: uuid.UUID,
    branch_id: uuid.UUID,
):
    lecture = await lecture_repository.get_by_id(session, lecture_id)
    if not lecture:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lecture not found")
    if lecture.branch_id != branch_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this branch")

    return await lecture_repository.get_attendance(session, lecture_id)


async def mark_substitute(
    session: AsyncSession,
    lecture_id: uuid.UUID,
    data: LectureSubstitute,
    branch_id: uuid.UUID,
    current_user_id: uuid.UUID,
    ip_address: str | None = None,
):
    lecture = await lecture_repository.get_by_id(session, lecture_id)
    if not lecture:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lecture not found")
    if lecture.branch_id != branch_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this branch")

    if data.actual_teacher_id is not None and data.actual_teacher_id == lecture.teacher_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Substitute teacher must differ from the scheduled teacher",
        )

    reason = data.change_reason
    if data.actual_teacher_id is None:
        reason = None
    elif reason is not None and reason not in VALID_CHANGE_REASONS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid change_reason: {reason}",
        )

    old_values = {
        "actual_teacher_id": str(lecture.actual_teacher_id) if lecture.actual_teacher_id else None,
        "change_reason": lecture.change_reason,
        "change_notes": lecture.change_notes,
    }

    lecture = await lecture_repository.update(
        session,
        lecture,
        actual_teacher_id=data.actual_teacher_id,
        change_reason=reason,
        change_notes=data.change_notes if data.actual_teacher_id else None,
    )

    await audit_service.log_action(
        session,
        user_id=current_user_id,
        action="UPDATE",
        table_name="lectures",
        record_id=lecture.id,
        old_values=old_values,
        new_values={
            "actual_teacher_id": str(data.actual_teacher_id) if data.actual_teacher_id else None,
            "change_reason": reason,
            "change_notes": data.change_notes,
        },
        ip_address=ip_address,
        branch_id=lecture.branch_id,
    )

    if data.actual_teacher_id:
        await event_service.emit_event(
            session,
            event_type="LECTURE_SUBSTITUTED",
            lecture_id=lecture.id,
            teacher_id=lecture.teacher_id,
            batch_id=lecture.batch_id,
            subject_id=lecture.subject_id,
            branch_id=lecture.branch_id,
            metadata={
                "scheduled_teacher_id": str(lecture.teacher_id),
                "actual_teacher_id": str(data.actual_teacher_id),
                "reason": reason or "",
            },
        )
    return lecture


async def mark_no_show(
    session: AsyncSession,
    lecture_id: uuid.UUID,
    data: LectureNoShow,
    branch_id: uuid.UUID,
    current_user_id: uuid.UUID,
    ip_address: str | None = None,
):
    lecture = await lecture_repository.get_by_id(session, lecture_id)
    if not lecture:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lecture not found")
    if lecture.branch_id != branch_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this branch")

    if data.no_show_reason not in VALID_NO_SHOW_REASONS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid no_show_reason: {data.no_show_reason}",
        )

    _validate_transition(lecture.lecture_status, "no_show")

    old_status = lecture.lecture_status
    lecture = await lecture_repository.update(
        session,
        lecture,
        lecture_status="no_show",
        no_show_reason=data.no_show_reason,
        notes=(data.notes if data.notes is not None else lecture.notes),
    )

    await audit_service.log_action(
        session,
        user_id=current_user_id,
        action="UPDATE",
        table_name="lectures",
        record_id=lecture.id,
        old_values={"lecture_status": old_status, "no_show_reason": None},
        new_values={
            "lecture_status": "no_show",
            "no_show_reason": data.no_show_reason,
        },
        ip_address=ip_address,
        branch_id=lecture.branch_id,
    )

    await event_service.emit_event(
        session,
        event_type="LECTURE_NO_SHOW",
        lecture_id=lecture.id,
        teacher_id=lecture.teacher_id,
        batch_id=lecture.batch_id,
        subject_id=lecture.subject_id,
        branch_id=lecture.branch_id,
        metadata={"no_show_reason": data.no_show_reason},
    )
    return lecture


async def _build_session_response(session: AsyncSession, sess) -> dict:
    """Hydrate a LectureSession row with its batch_ids and lecture_ids joins."""
    batches = await lecture_repository.list_session_batches(session, sess.id)
    plans = await lecture_repository.list_session_plans(session, sess.id)
    return {
        "id": sess.id,
        "teacher_id": sess.teacher_id,
        "subject_id": sess.subject_id,
        "topic_id": sess.topic_id,
        "classroom_id": sess.classroom_id,
        "actual_start": sess.actual_start,
        "actual_end": sess.actual_end,
        "delivery_mode": sess.delivery_mode,
        "session_status": sess.session_status,
        "origin": sess.origin,
        "notes": sess.notes,
        "branch_id": sess.branch_id,
        "academic_year_id": sess.academic_year_id,
        "batch_ids": [b.batch_id for b in batches],
        "lecture_ids": [p.lecture_id for p in plans],
        "status": sess.status,
    }


async def create_lecture_session(
    session: AsyncSession,
    data: LectureSessionCreate,
    branch_id: uuid.UUID,
    current_user_id: uuid.UUID,
    ip_address: str | None = None,
) -> dict:
    if data.delivery_mode not in VALID_DELIVERY_MODES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid delivery mode: {data.delivery_mode}",
        )
    if data.origin not in VALID_SESSION_ORIGINS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid origin: {data.origin}",
        )
    if not data.batch_ids:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one batch must be linked to the session",
        )
    if data.delivery_mode == "offline" and not data.classroom_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Offline sessions require a classroom_id",
        )
    if data.actual_end is not None and data.actual_end <= data.actual_start:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="actual_end must be after actual_start",
        )

    # Validate every batch belongs to this branch and pick an academic year.
    academic_year_id: uuid.UUID | None = None
    for bid in data.batch_ids:
        batch = await batch_repository.get_by_id(session, bid)
        if not batch:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Batch {bid} not found",
            )
        if batch.branch_id != branch_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Batch {bid} is not in this branch",
            )
        if academic_year_id is None:
            academic_year_id = batch.start_academic_year_id

    # Validate every linked plan belongs to this branch.
    for lid in data.lecture_ids:
        plan = await lecture_repository.get_by_id(session, lid)
        if not plan:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Lecture plan {lid} not found",
            )
        if plan.branch_id != branch_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Lecture plan {lid} is not in this branch",
            )

    session_status_val = "in_progress" if data.actual_end is None else "completed"

    sess = await lecture_repository.create_session(
        session,
        teacher_id=data.teacher_id,
        subject_id=data.subject_id,
        topic_id=data.topic_id,
        classroom_id=data.classroom_id,
        actual_start=data.actual_start,
        actual_end=data.actual_end,
        delivery_mode=data.delivery_mode,
        session_status=session_status_val,
        origin=data.origin,
        notes=data.notes,
        branch_id=branch_id,
        academic_year_id=academic_year_id,
    )

    for bid in data.batch_ids:
        await lecture_repository.link_session_batch(session, sess.id, bid, branch_id)
    for lid in data.lecture_ids:
        await lecture_repository.link_session_plan(session, sess.id, lid, branch_id)

    await audit_service.log_action(
        session,
        user_id=current_user_id,
        action="CREATE",
        table_name="lecture_sessions",
        record_id=sess.id,
        new_values={
            **data.model_dump(mode="json"),
            "session_status": session_status_val,
        },
        ip_address=ip_address,
        branch_id=branch_id,
    )

    await event_service.emit_event(
        session,
        event_type="LECTURE_SESSION_RECORDED",
        teacher_id=sess.teacher_id,
        batch_id=data.batch_ids[0],
        subject_id=sess.subject_id,
        branch_id=branch_id,
        metadata={
            "session_id": str(sess.id),
            "origin": sess.origin,
            "batch_count": len(data.batch_ids),
            "linked_plan_count": len(data.lecture_ids),
        },
    )

    return await _build_session_response(session, sess)


async def list_lecture_sessions(
    session: AsyncSession,
    branch_id: uuid.UUID,
    offset: int = 0,
    limit: int = 50,
) -> list[dict]:
    sessions = await lecture_repository.list_sessions_by_branch(
        session, branch_id, offset, limit
    )
    if not sessions:
        return []
    session_ids = [s.id for s in sessions]
    batches = await lecture_repository.list_session_batches_for_sessions(
        session, session_ids
    )
    plans = await lecture_repository.list_session_plans_for_sessions(
        session, session_ids
    )
    batches_by_session: dict[uuid.UUID, list[uuid.UUID]] = {}
    for b in batches:
        batches_by_session.setdefault(b.session_id, []).append(b.batch_id)
    plans_by_session: dict[uuid.UUID, list[uuid.UUID]] = {}
    for p in plans:
        plans_by_session.setdefault(p.session_id, []).append(p.lecture_id)

    return [
        {
            "id": s.id,
            "teacher_id": s.teacher_id,
            "subject_id": s.subject_id,
            "topic_id": s.topic_id,
            "classroom_id": s.classroom_id,
            "actual_start": s.actual_start,
            "actual_end": s.actual_end,
            "delivery_mode": s.delivery_mode,
            "session_status": s.session_status,
            "origin": s.origin,
            "notes": s.notes,
            "branch_id": s.branch_id,
            "academic_year_id": s.academic_year_id,
            "batch_ids": batches_by_session.get(s.id, []),
            "lecture_ids": plans_by_session.get(s.id, []),
            "status": s.status,
        }
        for s in sessions
    ]


def _safe_pct(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round((numerator * 100) / denominator, 1)


async def get_adherence_insights(
    session: AsyncSession,
    branch_id: uuid.UUID,
    from_dt: datetime | None,
    to_dt: datetime | None,
) -> dict:
    """Build the adherence dashboard payload in a single round-trip.

    Aggregations run in parallel-friendly sequence (each is one SQL query).
    Rates derive from totals so the frontend doesn't need to recompute.
    """
    totals = await lecture_repository.lecture_totals_in_range(
        session, branch_id, from_dt, to_dt
    )
    sessions = await lecture_repository.session_origin_totals_in_range(
        session, branch_id, from_dt, to_dt
    )
    per_teacher = await lecture_repository.per_teacher_adherence_in_range(
        session, branch_id, from_dt, to_dt
    )

    rates = {
        "adherence_pct": _safe_pct(totals["completed_as_planned"], totals["planned"]),
        "substitute_pct": _safe_pct(totals["substituted"], totals["planned"]),
        "cancellation_pct": _safe_pct(totals["cancelled"], totals["planned"]),
        "no_show_pct": _safe_pct(totals["no_show"], totals["planned"]),
    }

    # Enrich per-teacher rows with names and substitute rate.
    teacher_ids = [row["teacher_id"] for row in per_teacher]
    teacher_rows: list[dict] = []
    if teacher_ids:
        result = await session.execute(
            select(Teacher).where(
                Teacher.id.in_(teacher_ids),
                Teacher.branch_id == branch_id,
                Teacher.is_deleted == False,
            )
        )
        teachers_by_id = {t.id: t for t in result.scalars().all()}
        for row in per_teacher:
            t = teachers_by_id.get(row["teacher_id"])
            if t is None:
                continue
            teacher_rows.append(
                {
                    "teacher_id": row["teacher_id"],
                    "first_name": t.first_name,
                    "last_name": t.last_name,
                    "planned": row["planned"],
                    "substituted_out": row["substituted_out"],
                    "substituted_in": row["substituted_in"],
                    "cancelled": row["cancelled"],
                    "substitute_rate_pct": _safe_pct(
                        row["substituted_out"], row["planned"]
                    ),
                }
            )
    teacher_rows.sort(key=lambda r: r["substitute_rate_pct"], reverse=True)

    syllabus_rows = await lecture_repository.batch_syllabus_coverage(
        session, branch_id
    )

    return {
        "from_date": from_dt,
        "to_date": to_dt,
        "totals": totals,
        "sessions": sessions,
        "rates": rates,
        "by_teacher": teacher_rows,
        "by_batch_syllabus": syllabus_rows,
    }


async def delete_lecture(
    session: AsyncSession,
    lecture_id: uuid.UUID,
    branch_id: uuid.UUID,
    current_user_id: uuid.UUID,
    ip_address: str | None = None,
):
    lecture = await lecture_repository.get_by_id(session, lecture_id)
    if not lecture:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lecture not found")
    if lecture.branch_id != branch_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this branch")

    await lecture_repository.soft_delete(session, lecture)

    await audit_service.log_action(
        session,
        user_id=current_user_id,
        action="DELETE",
        table_name="lectures",
        record_id=lecture.id,
        old_values={"lecture_status": lecture.lecture_status},
        ip_address=ip_address,
        branch_id=lecture.branch_id,
    )
