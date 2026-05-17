import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.services import audit_service
from app.modules.batch.repositories import batch_repository
from app.modules.events.services import event_service
from app.modules.lectures.repositories import lecture_repository
from app.modules.lectures.schemas.lecture_schemas import (
    AttendanceMark,
    LectureCreate,
    LectureReschedule,
)

VALID_TRANSITIONS = {
    "scheduled": ["started", "cancelled", "rescheduled"],
    "started": ["paused", "completed", "cancelled"],
    "paused": ["started", "completed", "cancelled"],
    "completed": [],
    "cancelled": [],
    "rescheduled": ["scheduled"],
}

VALID_DELIVERY_MODES = {"offline", "online", "hybrid"}
VALID_ATTENDANCE_STATUSES = {"PRESENT", "ABSENT", "LATE", "PARTIAL", "EXCUSED", "MANUAL_OVERRIDE"}


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
        academic_year_id=batch.academic_year_id,
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
