import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.attendance.repositories import attendance_repository
from app.modules.attendance.services import daily_service
from app.modules.attendance.time_utils import local_date_of
from app.modules.audit.services import audit_service
from app.modules.events.services import event_service
from app.modules.lectures.repositories import lecture_repository

VALID_ATTENDANCE_STATUSES = {"PRESENT", "ABSENT", "LATE", "PARTIAL", "EXCUSED", "MANUAL_OVERRIDE"}
VALID_SOURCES = {"BIOMETRIC", "MANUAL", "IMPORT", "SYSTEM"}


async def receive_raw_punches(
    session: AsyncSession,
    punches: list[dict],
    current_user_id: uuid.UUID,
    ip_address: str | None = None,
):
    created = []
    for punch in punches:
        log = await attendance_repository.create_raw_punch_log(
            session,
            device_id=punch["device_id"],
            student_id=punch["student_id"],
            punch_timestamp=punch["punch_timestamp"],
            sync_batch_id=punch.get("sync_batch_id"),
            synced_at=datetime.now(timezone.utc),
            branch_id=punch["branch_id"],
        )
        created.append(log)

    await audit_service.log_action(
        session,
        user_id=current_user_id,
        action="CREATE",
        table_name="raw_punch_logs",
        record_id=created[0].id if created else None,
        new_values={"count": len(created)},
        ip_address=ip_address,
        branch_id=punches[0]["branch_id"] if punches else None,
    )
    return created


async def process_raw_punches(
    session: AsyncSession,
    lecture_id: uuid.UUID,
    branch_id: uuid.UUID,
    current_user_id: uuid.UUID,
    ip_address: str | None = None,
):
    """Aggregate punches into per-lecture attendance via the day layer.

    Rebuilds each batch student's Layer 1 day row from punches, then projects
    those day facts onto this lecture's window — writing one attendance_records
    row per student (present & absent), manual marks preserved. Route and
    response are unchanged; the engine underneath is now the day model.
    """
    lecture = await lecture_repository.get_by_id(session, lecture_id)
    if not lecture:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lecture not found")
    if lecture.branch_id != branch_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this branch")

    from sqlalchemy import select
    from app.modules.student.models.student_models import StudentBatchMapping

    tz_name = await daily_service.branch_timezone(session, branch_id)
    day = local_date_of(lecture.scheduled_start, tz_name)

    student_ids = [row[0] for row in (await session.execute(
        select(StudentBatchMapping.student_id).where(
            StudentBatchMapping.batch_id == lecture.batch_id,
            StudentBatchMapping.is_deleted == False,
        )
    )).all()]
    if not student_ids:
        return []

    for sid in student_ids:
        await daily_service.rebuild_daily(
            session, student_id=sid, branch_id=branch_id, day=day, tz_name=tz_name
        )

    results = await daily_service.project_day_onto_lecture(
        session,
        lecture_id=lecture_id,
        branch_id=branch_id,
        current_user_id=current_user_id,
        tz_name=tz_name,
    )

    await audit_service.log_action(
        session,
        user_id=current_user_id,
        action="CREATE",
        table_name="attendance_records",
        record_id=lecture_id,
        new_values={"processed_count": len(results), "lecture_id": str(lecture_id)},
        ip_address=ip_address,
        branch_id=branch_id,
    )
    return results


async def mark_attendance(
    session: AsyncSession,
    lecture_id: uuid.UUID,
    student_id: uuid.UUID,
    attendance_status: str,
    source: str,
    branch_id: uuid.UUID,
    current_user_id: uuid.UUID,
    ip_address: str | None = None,
):
    if attendance_status not in VALID_ATTENDANCE_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid attendance status: {attendance_status}",
        )
    if source not in VALID_SOURCES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid source: {source}",
        )

    lecture = await lecture_repository.get_by_id(session, lecture_id)
    if not lecture:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lecture not found")
    if lecture.branch_id != branch_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this branch")

    now = datetime.now(timezone.utc)
    existing = await attendance_repository.get_existing_attendance(session, student_id, lecture_id)

    if existing:
        old_status = existing.attendance_status
        record = await attendance_repository.update_attendance_record(
            session, existing,
            attendance_status=attendance_status,
            marked_at=now,
            marked_by=current_user_id,
            source=source,
        )
        await audit_service.log_action(
            session,
            user_id=current_user_id,
            action="UPDATE",
            table_name="attendance_records",
            record_id=record.id,
            old_values={"attendance_status": old_status},
            new_values={"attendance_status": attendance_status, "source": source},
            ip_address=ip_address,
            branch_id=branch_id,
        )
    else:
        record = await attendance_repository.create_attendance_record(
            session,
            student_id=student_id,
            lecture_id=lecture_id,
            attendance_status=attendance_status,
            marked_at=now,
            marked_by=current_user_id,
            source=source,
            branch_id=branch_id,
        )
        await audit_service.log_action(
            session,
            user_id=current_user_id,
            action="CREATE",
            table_name="attendance_records",
            record_id=record.id,
            new_values={"student_id": str(student_id), "attendance_status": attendance_status},
            ip_address=ip_address,
            branch_id=branch_id,
        )

    await event_service.emit_event(
        session,
        event_type="ATTENDANCE_MARKED",
        student_id=student_id,
        lecture_id=lecture_id,
        branch_id=branch_id,
        metadata={"attendance_status": attendance_status, "source": source},
    )
    return record


async def get_lecture_attendance(
    session: AsyncSession,
    lecture_id: uuid.UUID,
    branch_id: uuid.UUID,
):
    lecture = await lecture_repository.get_by_id(session, lecture_id)
    if not lecture:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lecture not found")
    if lecture.branch_id != branch_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this branch")

    return await attendance_repository.get_attendance_by_lecture(session, lecture_id)


async def get_student_attendance(
    session: AsyncSession,
    student_id: uuid.UUID,
    branch_id: uuid.UUID,
    offset: int = 0,
    limit: int = 50,
):
    return await attendance_repository.get_attendance_by_student(
        session, student_id, branch_id, offset, limit
    )


async def create_exception(
    session: AsyncSession,
    student_id: uuid.UUID,
    lecture_id: uuid.UUID,
    reason: str,
    branch_id: uuid.UUID,
    current_user_id: uuid.UUID,
    ip_address: str | None = None,
):
    lecture = await lecture_repository.get_by_id(session, lecture_id)
    if not lecture:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lecture not found")
    if lecture.branch_id != branch_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this branch")

    exc = await attendance_repository.create_exception(
        session,
        student_id=student_id,
        lecture_id=lecture_id,
        reason=reason,
        branch_id=branch_id,
    )

    await audit_service.log_action(
        session,
        user_id=current_user_id,
        action="CREATE",
        table_name="attendance_exceptions",
        record_id=exc.id,
        new_values={"student_id": str(student_id), "reason": reason},
        ip_address=ip_address,
        branch_id=branch_id,
    )
    return exc


async def resolve_exception(
    session: AsyncSession,
    exception_id: uuid.UUID,
    branch_id: uuid.UUID,
    current_user_id: uuid.UUID,
    resolution_notes: str | None = None,
    ip_address: str | None = None,
):
    exc = await attendance_repository.get_exception_by_id(session, exception_id)
    if not exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exception not found")
    if exc.branch_id != branch_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this branch")
    if exc.resolved:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Exception already resolved",
        )

    now = datetime.now(timezone.utc)
    exc = await attendance_repository.resolve_exception(
        session, exc,
        resolved=True,
        resolved_at=now,
        resolved_by=current_user_id,
        resolution_notes=resolution_notes,
    )

    await audit_service.log_action(
        session,
        user_id=current_user_id,
        action="UPDATE",
        table_name="attendance_exceptions",
        record_id=exc.id,
        old_values={"resolved": False},
        new_values={"resolved": True, "resolution_notes": resolution_notes},
        ip_address=ip_address,
        branch_id=branch_id,
    )
    return exc


async def generate_attendance_report(
    session: AsyncSession,
    lecture_id: uuid.UUID,
    branch_id: uuid.UUID,
):
    lecture = await lecture_repository.get_by_id(session, lecture_id)
    if not lecture:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lecture not found")
    if lecture.branch_id != branch_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this branch")

    counts = await attendance_repository.get_attendance_summary(session, lecture_id)
    total = sum(counts.values())

    return {
        "lecture_id": lecture_id,
        "total_students": total,
        "present": counts.get("PRESENT", 0),
        "absent": counts.get("ABSENT", 0),
        "late": counts.get("LATE", 0),
        "partial": counts.get("PARTIAL", 0),
        "excused": counts.get("EXCUSED", 0),
    }
