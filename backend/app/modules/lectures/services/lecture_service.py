import uuid
from datetime import date, datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.services import audit_service
from app.modules.batch.repositories import batch_repository
from app.modules.events.services import event_service
from app.modules.lectures.repositories import lecture_repository
from app.modules.academic.models.academic_models import Subject
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
    # no_show → completed is reachable only via mark_substitute (admin
    # corrects "nobody came" → "actually someone covered it").
    "no_show": ["completed"],
    # rescheduled is a legacy/transient status — new reschedules now write
    # back to "scheduled" with the new times (see reschedule_lecture). Kept
    # here so any pre-existing rescheduled rows still have a lifecycle.
    "rescheduled": ["started", "cancelled", "no_show", "scheduled"],
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

    # Reschedule writes the new times back as a regular "scheduled" lecture
    # so the lifecycle continues — Start / Cancel / No-Show all remain
    # available. The audit log records the reschedule action separately.
    lecture = await lecture_repository.update(
        session, lecture,
        scheduled_start=data.scheduled_start,
        scheduled_end=data.scheduled_end,
        classroom_id=classroom_id,
        lecture_status="scheduled",
    )

    await audit_service.log_action(
        session,
        user_id=current_user_id,
        action="UPDATE",
        table_name="lectures",
        record_id=lecture.id,
        old_values=old_values,
        new_values={"scheduled_start": str(data.scheduled_start), "scheduled_end": str(data.scheduled_end), "lecture_status": "scheduled"},
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
        "lecture_status": lecture.lecture_status,
        "no_show_reason": lecture.no_show_reason,
    }

    # Mutual exclusion: recording a substitute on a no-show lecture means
    # "actually someone DID cover it" — transition status to completed and
    # clear the no_show_reason so the lecture's state is internally consistent.
    transition_from_no_show = (
        data.actual_teacher_id is not None
        and lecture.lecture_status == "no_show"
    )
    if transition_from_no_show:
        lecture.no_show_reason = None
        lecture.lecture_status = "completed"

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
            "lecture_status": lecture.lecture_status,
            "no_show_reason": lecture.no_show_reason,
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
    old_actual_teacher = lecture.actual_teacher_id
    old_change_reason = lecture.change_reason

    # No-show means nobody actually taught the class. Clear any substitute
    # info that may have been left over from earlier admin edits — the two
    # states are mutually exclusive (someone taught vs nobody taught).
    # The repo update() guard skips None values, so we use the model
    # attribute directly to force-clear.
    lecture.actual_teacher_id = None
    lecture.change_reason = None
    lecture.change_notes = None

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
        old_values={
            "lecture_status": old_status,
            "no_show_reason": None,
            "actual_teacher_id": str(old_actual_teacher) if old_actual_teacher else None,
            "change_reason": old_change_reason,
        },
        new_values={
            "lecture_status": "no_show",
            "no_show_reason": data.no_show_reason,
            "actual_teacher_id": None,
            "change_reason": None,
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


def _compute_pace(
    coverage_pct: float,
    target_exam_date: date | None,
    start_year: int | None,
    end_year: int | None,
    today: date | None = None,
) -> dict:
    """Time-weighted pace.

    Linear interpolation between the academic year start and the target
    exam date. When target_exam_date is missing we fall back to the
    Indian coaching default of mid-May of the end academic year.
    Pacing start is fixed at June 1 of the start academic year — that's
    when new sessions typically begin for NEET/JEE prep.

    Returns expected_coverage_pct + pace_delta_pct + pace_status:
        ahead (delta ≥ +10)
        on_pace ( -5 ≤ delta < +10 )
        behind ( -15 ≤ delta < -5 )
        critically_behind ( delta < -15 )
        no_data (when dates can't be derived)
    """
    today = today or date.today()
    exam = target_exam_date
    if exam is None and end_year is not None:
        exam = date(end_year, 5, 15)
    start = date(start_year, 6, 1) if start_year is not None else None

    if start is None or exam is None or exam <= start:
        return {
            "expected_coverage_pct": 0.0,
            "pace_delta_pct": 0.0,
            "pace_status": "no_data",
        }

    total_days = (exam - start).days
    if today <= start:
        expected = 0.0
    elif today >= exam:
        expected = 100.0
    else:
        elapsed = (today - start).days
        expected = round((elapsed * 100) / total_days, 1)

    delta = round(coverage_pct - expected, 1)
    if expected == 100.0 and coverage_pct >= 100.0:
        status = "on_pace"
    elif delta >= 10:
        status = "ahead"
    elif delta >= -5:
        status = "on_pace"
    elif delta >= -15:
        status = "behind"
    else:
        status = "critically_behind"

    return {
        "expected_coverage_pct": expected,
        "pace_delta_pct": delta,
        "pace_status": status,
    }


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
    no_show_breakdown = await lecture_repository.no_show_breakdown_in_range(
        session, branch_id, from_dt, to_dt
    )

    rates = {
        "adherence_pct": _safe_pct(totals["completed_as_planned"], totals["planned"]),
        "substitute_pct": _safe_pct(totals["substituted"], totals["planned"]),
        "cancellation_pct": _safe_pct(totals["cancelled"], totals["planned"]),
        "no_show_pct": _safe_pct(totals["no_show"], totals["planned"]),
        # Reliability signal — only teacher-attributable no-shows.
        "teacher_no_show_pct": _safe_pct(
            no_show_breakdown["teacher"], totals["planned"]
        ),
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
    # Decorate each row with time-weighted pace fields. Pure derivation,
    # no DB hit, so we do it inline.
    for row in syllabus_rows:
        row.update(
            _compute_pace(
                coverage_pct=row["coverage_pct"],
                target_exam_date=row.get("target_exam_date"),
                start_year=row.get("start_year"),
                end_year=row.get("end_year"),
            )
        )

    return {
        "from_date": from_dt,
        "to_date": to_dt,
        "totals": totals,
        "sessions": sessions,
        "rates": rates,
        "no_show_breakdown": no_show_breakdown,
        "by_teacher": teacher_rows,
        "by_batch_syllabus": syllabus_rows,
    }


_NO_SHOW_REASON_LABEL = {
    "TEACHER_NO_SHOW": "teacher",
    "STUDENT_NO_SHOW": "students",
    "EXTERNAL": "external",
    "OTHER": "other",
}


def _derive_lecture_status(lecture, is_covered: bool) -> dict:
    """Mirror of frontend deriveStatus(). Keep in sync."""
    has_sub = lecture.actual_teacher_id is not None
    status = lecture.lecture_status

    if is_covered and status in ("cancelled", "no_show"):
        return {
            "status_label": "Made up",
            "status_tone": "success",
            "status_sub": "was cancelled" if status == "cancelled" else "was no-show",
        }
    if status == "no_show":
        reason = (lecture.no_show_reason or "OTHER").upper()
        return {
            "status_label": f"No-show · {_NO_SHOW_REASON_LABEL.get(reason, 'other')}",
            "status_tone": "destructive" if reason == "TEACHER_NO_SHOW" else "secondary",
            "status_sub": None,
        }
    if status == "cancelled":
        return {"status_label": "Cancelled", "status_tone": "secondary", "status_sub": None}
    if status == "started":
        return {
            "status_label": "In progress",
            "status_tone": "default",
            "status_sub": "with substitute" if has_sub else None,
        }
    if status == "paused":
        return {"status_label": "Paused", "status_tone": "secondary", "status_sub": None}
    if status == "completed":
        if has_sub:
            return {"status_label": "Completed", "status_tone": "default", "status_sub": "by substitute"}
        return {"status_label": "Completed", "status_tone": "success", "status_sub": None}
    if status == "rescheduled":
        return {"status_label": "Rescheduled", "status_tone": "secondary", "status_sub": None}
    return {"status_label": "Scheduled", "status_tone": "default", "status_sub": None}


def _teacher_sort_key(t: dict, now: datetime) -> tuple:
    """Lower tuple = earlier in the list.

    Order: (problems → live → upcoming → done → no-activity)
    """
    s = t["summary"]
    has_red = s["no_show"] > 0
    has_live = s["in_progress"] > 0

    def _is_upcoming(ev: dict) -> bool:
        if ev["kind"] != "lecture":
            return False
        if not ev["status_label"].startswith("Scheduled"):
            return False
        start = ev["start"]
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        return start > now

    has_upcoming = any(_is_upcoming(ev) for ev in t["events"])
    has_done = s["completed"] > 0
    total = len(t["events"])
    return (
        0 if has_red else 1,
        0 if has_live else 1,
        0 if has_upcoming else 1,
        0 if has_done else 1,
        -total,
    )


async def get_outcome_insights(
    db: AsyncSession,
    branch_id: uuid.UUID,
    from_dt: datetime | None,
    to_dt: datetime | None,
) -> dict:
    """Tier 9 outcome correlation.

    Returns:
      summary           — tests evaluated, students with marks, branch avg
      by_teacher        — per (teacher × subject) avg score vs branch avg
      attendance_buckets — branch-wide attendance % vs avg test score
    """
    summary = await lecture_repository.branch_test_summary(
        db, branch_id, from_dt, to_dt
    )
    teacher_rows = await lecture_repository.teacher_outcome_rows(
        db, branch_id, from_dt, to_dt
    )
    pairs = await lecture_repository.attendance_outcome_pairs(
        db, branch_id, from_dt, to_dt
    )

    # Enrich teacher rows with names and subject names.
    teacher_ids = list({r["teacher_id"] for r in teacher_rows})
    subject_ids = list({r["subject_id"] for r in teacher_rows})

    teachers_by_id: dict[uuid.UUID, Teacher] = {}
    subjects_by_id: dict[uuid.UUID, Subject] = {}
    if teacher_ids:
        result = await db.execute(
            select(Teacher).where(
                Teacher.id.in_(teacher_ids),
                Teacher.is_deleted == False,
            )
        )
        teachers_by_id = {t.id: t for t in result.scalars().all()}
    if subject_ids:
        result = await db.execute(
            select(Subject).where(
                Subject.id.in_(subject_ids),
                Subject.is_deleted == False,
            )
        )
        subjects_by_id = {s.id: s for s in result.scalars().all()}

    branch_avg = summary["branch_avg_score"]
    enriched: list[dict] = []
    for r in teacher_rows:
        t = teachers_by_id.get(r["teacher_id"])
        s = subjects_by_id.get(r["subject_id"])
        if t is None or s is None:
            continue
        enriched.append(
            {
                "teacher_id": r["teacher_id"],
                "first_name": t.first_name,
                "last_name": t.last_name,
                "subject_id": r["subject_id"],
                "subject_name": s.name,
                "tests_count": r["tests_count"],
                "students_count": r["students_count"],
                "avg_score_pct": r["avg_score_pct"],
                "delta_vs_branch_pct": round(r["avg_score_pct"] - branch_avg, 1),
            }
        )
    enriched.sort(key=lambda r: r["delta_vs_branch_pct"], reverse=True)

    # Attendance × score buckets.
    buckets_def = [(">=80%", 80.0, 101.0), ("50-80%", 50.0, 80.0), ("<50%", 0.0, 50.0)]
    buckets: list[dict] = []
    for label, lo, hi in buckets_def:
        bucket_pairs = [
            p for p in pairs if lo <= p["attendance_pct"] < hi
        ]
        if not bucket_pairs:
            buckets.append({"bucket": label, "students": 0, "avg_score": 0.0})
            continue
        avg = sum(p["avg_test_pct"] for p in bucket_pairs) / len(bucket_pairs)
        buckets.append(
            {
                "bucket": label,
                "students": len(bucket_pairs),
                "avg_score": round(avg, 1),
            }
        )

    return {
        "from_date": from_dt,
        "to_date": to_dt,
        "summary": summary,
        "by_teacher": enriched,
        "attendance_buckets": buckets,
    }


async def get_roster(
    db: AsyncSession,
    branch_id: uuid.UUID,
    day: datetime,
) -> dict:
    """Today's Roster: per-teacher timeline of every lecture + off-plan
    session on a given date, plus snapshot KPIs and a Live Now strip.

    `day` is a UTC datetime; the window is its [00:00, 23:59:59].
    """
    day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day.replace(hour=23, minute=59, second=59, microsecond=999999)
    now = datetime.now(timezone.utc)

    def _aware(dt: datetime | None) -> datetime | None:
        # SQLite (test DB) returns naive datetimes even for timezone=True
        # columns. Coerce to UTC so comparisons with `now` don't blow up.
        if dt is None:
            return None
        return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)

    lectures = await lecture_repository.list_lectures_for_day(
        db, branch_id, day_start, day_end
    )
    sessions = await lecture_repository.list_sessions_for_day(
        db, branch_id, day_start, day_end
    )

    # Lookup tables (batched fetches).
    teacher_ids = {l.teacher_id for l in lectures} | {s.teacher_id for s in sessions}
    teacher_ids |= {l.actual_teacher_id for l in lectures if l.actual_teacher_id}

    teachers_by_id: dict[uuid.UUID, Teacher] = {}
    if teacher_ids:
        result = await db.execute(
            select(Teacher).where(
                Teacher.id.in_(teacher_ids), Teacher.is_deleted == False
            )
        )
        teachers_by_id = {t.id: t for t in result.scalars().all()}

    # Also fetch ALL branch teachers for the idle list (those with nothing today).
    result = await db.execute(
        select(Teacher).where(
            Teacher.branch_id == branch_id, Teacher.is_deleted == False
        )
    )
    all_branch_teachers = list(result.scalars().all())

    # Batches, subjects, topics, classrooms — names only.
    from app.modules.batch.models.batch_models import Batch
    from app.modules.academic.models.academic_models import Subject, Topic
    from app.modules.classroom.models.classroom_models import Classroom

    batch_ids = {l.batch_id for l in lectures}
    subject_ids = {l.subject_id for l in lectures} | {s.subject_id for s in sessions}
    topic_ids = {l.topic_id for l in lectures if l.topic_id} | {
        s.topic_id for s in sessions if s.topic_id
    }
    classroom_ids = {l.classroom_id for l in lectures if l.classroom_id} | {
        s.classroom_id for s in sessions if s.classroom_id
    }

    async def _by_id(model, ids):
        if not ids:
            return {}
        r = await db.execute(select(model).where(model.id.in_(ids)))
        return {x.id: x for x in r.scalars().all()}

    batches_by_id = await _by_id(Batch, batch_ids)
    subjects_by_id = await _by_id(Subject, subject_ids)
    topics_by_id = await _by_id(Topic, topic_ids)
    classrooms_by_id = await _by_id(Classroom, classroom_ids)

    # Session → batch_ids and session → covered lecture_ids.
    session_ids = [s.id for s in sessions]
    session_batches = await lecture_repository.list_session_batches_for_sessions(
        db, session_ids
    )
    session_plans = await lecture_repository.list_session_plans_for_sessions(
        db, session_ids
    )
    batches_by_session: dict[uuid.UUID, list[uuid.UUID]] = {}
    for sb in session_batches:
        batches_by_session.setdefault(sb.session_id, []).append(sb.batch_id)
    plans_by_session: dict[uuid.UUID, int] = {}
    for sp in session_plans:
        plans_by_session[sp.session_id] = plans_by_session.get(sp.session_id, 0) + 1

    # Which of today's lectures are covered by ANY session (today or otherwise)?
    lecture_ids = [l.id for l in lectures]
    coverage_links = await lecture_repository.list_session_plans_by_lecture_ids(
        db, lecture_ids
    )
    covered_lecture_ids: set[uuid.UUID] = {sp.lecture_id for sp in coverage_links}

    # Snapshot.
    no_show_teacher = sum(
        1 for l in lectures
        if l.lecture_status == "no_show" and (l.no_show_reason or "").upper() == "TEACHER_NO_SHOW"
    )
    snapshot = {
        "planned": len(lectures),
        "completed": sum(1 for l in lectures if l.lecture_status == "completed"),
        "in_progress": sum(
            1 for l in lectures if l.lecture_status in ("started", "paused")
        ),
        "pending": sum(
            1 for l in lectures if l.lecture_status in ("scheduled", "rescheduled")
        ),
        "no_show_teacher": no_show_teacher,
        "no_show_other": sum(1 for l in lectures if l.lecture_status == "no_show") - no_show_teacher,
        "cancelled": sum(1 for l in lectures if l.lecture_status == "cancelled"),
        "off_plan_makeup": sum(1 for s in sessions if s.origin == "makeup"),
        "off_plan_ad_hoc": sum(1 for s in sessions if s.origin == "ad_hoc"),
        "off_plan_merged": sum(
            1 for s in sessions if plans_by_session.get(s.id, 0) >= 2
        ),
    }

    # Live now — live + overdue.
    live_now: list[dict] = []
    for l in lectures:
        teacher = teachers_by_id.get(l.teacher_id)
        if not teacher:
            continue
        base = {
            "lecture_id": l.id,
            "teacher_id": l.teacher_id,
            "teacher_name": f"{teacher.first_name} {teacher.last_name}",
            "batch_name": batches_by_id.get(l.batch_id).name if l.batch_id in batches_by_id else None,
            "subject_name": subjects_by_id.get(l.subject_id).name if l.subject_id in subjects_by_id else None,
            "topic_name": topics_by_id.get(l.topic_id).name if l.topic_id in topics_by_id else None,
            "classroom_name": classrooms_by_id.get(l.classroom_id).name if l.classroom_id in classrooms_by_id else None,
            "scheduled_start": l.scheduled_start,
            "scheduled_end": l.scheduled_end,
        }
        if l.lecture_status == "started":
            live_now.append({"kind": "live", **base})
        elif l.lecture_status in ("scheduled", "rescheduled"):
            ss = _aware(l.scheduled_start)
            if ss is not None and ss < now:
                minutes_overdue = int((now - ss).total_seconds() // 60)
                live_now.append(
                    {"kind": "overdue", "minutes_overdue": minutes_overdue, **base}
                )

    # Per-teacher events.
    by_teacher: dict[uuid.UUID, dict] = {}
    for l in lectures:
        teacher = teachers_by_id.get(l.teacher_id)
        if teacher is None:
            continue
        bucket = by_teacher.setdefault(
            l.teacher_id,
            {
                "teacher_id": l.teacher_id,
                "first_name": teacher.first_name,
                "last_name": teacher.last_name,
                "events": [],
                "summary": {
                    "planned": 0,
                    "completed": 0,
                    "in_progress": 0,
                    "no_show": 0,
                    "cancelled": 0,
                    "sub_in": 0,
                    "sub_out": 0,
                    "off_plan": 0,
                },
            },
        )
        is_covered = l.id in covered_lecture_ids
        derived = _derive_lecture_status(l, is_covered)
        bucket["events"].append(
            {
                "kind": "lecture",
                "id": l.id,
                "start": l.scheduled_start,
                "end": l.scheduled_end,
                **derived,
                "batch_name": batches_by_id.get(l.batch_id).name if l.batch_id in batches_by_id else None,
                "batch_names": [],
                "subject_name": subjects_by_id.get(l.subject_id).name if l.subject_id in subjects_by_id else None,
                "topic_name": topics_by_id.get(l.topic_id).name if l.topic_id in topics_by_id else None,
                "classroom_name": classrooms_by_id.get(l.classroom_id).name if l.classroom_id in classrooms_by_id else None,
                "actual_teacher_id": l.actual_teacher_id,
                "actual_teacher_name": (
                    f"{teachers_by_id[l.actual_teacher_id].first_name} {teachers_by_id[l.actual_teacher_id].last_name}"
                    if l.actual_teacher_id and l.actual_teacher_id in teachers_by_id
                    else None
                ),
                "no_show_reason": l.no_show_reason,
                "is_covered": is_covered,
                "origin": None,
            }
        )
        # Roll up counts.
        bucket["summary"]["planned"] += 1
        if l.lecture_status == "completed":
            bucket["summary"]["completed"] += 1
        if l.lecture_status in ("started", "paused"):
            bucket["summary"]["in_progress"] += 1
        if l.lecture_status == "no_show":
            bucket["summary"]["no_show"] += 1
        if l.lecture_status == "cancelled":
            bucket["summary"]["cancelled"] += 1
        if l.actual_teacher_id is not None:
            bucket["summary"]["sub_out"] += 1
            # Also bump the actual_teacher's sub_in.
            sub_in_bucket = by_teacher.get(l.actual_teacher_id)
            if sub_in_bucket:
                sub_in_bucket["summary"]["sub_in"] += 1

    # Add sessions (off-plan) onto the responsible teacher's timeline.
    for s in sessions:
        teacher = teachers_by_id.get(s.teacher_id)
        if teacher is None:
            continue
        bucket = by_teacher.setdefault(
            s.teacher_id,
            {
                "teacher_id": s.teacher_id,
                "first_name": teacher.first_name,
                "last_name": teacher.last_name,
                "events": [],
                "summary": {
                    "planned": 0,
                    "completed": 0,
                    "in_progress": 0,
                    "no_show": 0,
                    "cancelled": 0,
                    "sub_in": 0,
                    "sub_out": 0,
                    "off_plan": 0,
                },
            },
        )
        # Session status pill — coloured by origin.
        if s.origin == "makeup":
            session_label, session_tone = "Makeup", "success"
        elif s.origin == "ad_hoc":
            session_label, session_tone = "Ad-hoc", "default"
        else:
            session_label, session_tone = (s.origin or "session").capitalize(), "default"

        batch_ids_for_session = batches_by_session.get(s.id, [])
        batch_names_for_session = [
            batches_by_id[bid].name for bid in batch_ids_for_session if bid in batches_by_id
        ]

        bucket["events"].append(
            {
                "kind": "session",
                "id": s.id,
                "start": s.actual_start,
                "end": s.actual_end,
                "status_label": session_label,
                "status_tone": session_tone,
                "status_sub": None,
                "batch_name": batch_names_for_session[0] if batch_names_for_session else None,
                "batch_names": batch_names_for_session,
                "subject_name": subjects_by_id.get(s.subject_id).name if s.subject_id in subjects_by_id else None,
                "topic_name": topics_by_id.get(s.topic_id).name if s.topic_id in topics_by_id else None,
                "classroom_name": classrooms_by_id.get(s.classroom_id).name if s.classroom_id in classrooms_by_id else None,
                "actual_teacher_id": None,
                "actual_teacher_name": None,
                "no_show_reason": None,
                "is_covered": False,
                "origin": s.origin,
            }
        )
        bucket["summary"]["off_plan"] += 1

    # Sort events within each teacher row by time.
    for t in by_teacher.values():
        t["events"].sort(key=lambda e: e["start"])

    teachers_sorted = sorted(
        by_teacher.values(), key=lambda t: _teacher_sort_key(t, now)
    )

    idle_teachers = [
        {"teacher_id": t.id, "first_name": t.first_name, "last_name": t.last_name}
        for t in all_branch_teachers
        if t.id not in by_teacher
    ]
    # Stable: alphabetical for idle.
    idle_teachers.sort(key=lambda t: (t["first_name"], t["last_name"]))

    return {
        "date": day.strftime("%Y-%m-%d"),
        "now": now,
        "snapshot": snapshot,
        "live_now": live_now,
        "teachers": teachers_sorted,
        "idle_teachers": idle_teachers,
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
