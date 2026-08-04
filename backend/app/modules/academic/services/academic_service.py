import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.academic import subject_seeding
from app.modules.academic.repositories import academic_repository
from app.modules.audit.services import audit_service


async def create_institute(session: AsyncSession, data: dict, current_user_id: uuid.UUID, ip_address: str | None = None):
    inst = await academic_repository.create_institute(session, **data)
    await audit_service.log_action(
        session, user_id=current_user_id, action="CREATE",
        table_name="institutes", record_id=inst.id, new_values=data, ip_address=ip_address,
    )
    return inst


async def create_academic_year(session: AsyncSession, data: dict, current_user_id: uuid.UUID, ip_address: str | None = None):
    ay = await academic_repository.create_academic_year(session, **data)
    await audit_service.log_action(
        session, user_id=current_user_id, action="CREATE",
        table_name="academic_years", record_id=ay.id, new_values=data,
        ip_address=ip_address, branch_id=data.get("branch_id"),
    )
    return ay


async def delete_academic_year(
    session: AsyncSession,
    ay_id: uuid.UUID,
    branch_id: uuid.UUID,
    current_user_id: uuid.UUID,
    ip_address: str | None = None,
):
    ay = await academic_repository.get_academic_year(session, ay_id)
    if not ay:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Academic year not found")
    if ay.branch_id != branch_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this branch")

    in_use = await academic_repository.count_active_batches_using_academic_year(session, ay_id)
    if in_use:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot delete: {in_use} batch(es) reference this academic year.",
        )

    await academic_repository.soft_delete_academic_year(session, ay)
    await audit_service.log_action(
        session, user_id=current_user_id, action="DELETE",
        table_name="academic_years", record_id=ay.id,
        old_values={"name": ay.name, "start_year": ay.start_year, "end_year": ay.end_year},
        ip_address=ip_address, branch_id=branch_id,
    )


async def create_course(session: AsyncSession, data: dict, current_user_id: uuid.UUID, ip_address: str | None = None):
    course = await academic_repository.create_course(session, **data)
    await audit_service.log_action(
        session, user_id=current_user_id, action="CREATE",
        table_name="courses", record_id=course.id, new_values=data,
        ip_address=ip_address, branch_id=data.get("branch_id"),
    )
    return course


async def update_course(
    session: AsyncSession,
    course_id: uuid.UUID,
    data: dict,
    branch_id: uuid.UUID,
    current_user_id: uuid.UUID,
    ip_address: str | None = None,
):
    course = await academic_repository.get_course(session, course_id)
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
    if course.branch_id != branch_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this branch")

    old_values = {
        "name": course.name,
        "code": course.code,
        "description": course.description,
        "duration_years": course.duration_years,
    }
    course = await academic_repository.update_course(session, course, **data)
    await audit_service.log_action(
        session, user_id=current_user_id, action="UPDATE",
        table_name="courses", record_id=course.id,
        old_values=old_values, new_values=data,
        ip_address=ip_address, branch_id=branch_id,
    )
    return course


async def delete_course(
    session: AsyncSession,
    course_id: uuid.UUID,
    branch_id: uuid.UUID,
    current_user_id: uuid.UUID,
    ip_address: str | None = None,
):
    course = await academic_repository.get_course(session, course_id)
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
    if course.branch_id != branch_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this branch")

    in_use = await academic_repository.count_active_batches_using_course(session, course_id)
    if in_use:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot delete: {in_use} batch(es) use this course.",
        )

    await academic_repository.soft_delete_course(session, course)
    await audit_service.log_action(
        session, user_id=current_user_id, action="DELETE",
        table_name="courses", record_id=course.id,
        old_values={"name": course.name, "code": course.code},
        ip_address=ip_address, branch_id=branch_id,
    )


async def create_subject(session: AsyncSession, data: dict, current_user_id: uuid.UUID, ip_address: str | None = None):
    subj = await academic_repository.create_subject(session, **data)
    await audit_service.log_action(
        session, user_id=current_user_id, action="CREATE",
        table_name="subjects", record_id=subj.id, new_values=data,
        ip_address=ip_address, branch_id=data.get("branch_id"),
    )
    return subj


async def seed_course_subjects(
    session: AsyncSession,
    branch_id: uuid.UUID,
    course_id: uuid.UUID,
    syllabus_key: str,
    current_user_id: uuid.UUID,
    ip_address: str | None = None,
):
    """Populate a course's subjects (and their curriculum skeleton) from a known
    syllabus. Idempotent: a course that already has subjects is left untouched.
    Returns ``(created_count, subjects)`` — subjects is always the course's full
    current set so the UI can render the result either way."""
    course = await academic_repository.get_course(session, course_id)
    if not course or course.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
    if course.branch_id != branch_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this branch")
    if syllabus_key not in subject_seeding.SUBJECT_SETS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown syllabus '{syllabus_key}'",
        )

    years = await academic_repository.list_academic_years(session, branch_id)
    if not years:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Create an academic year for this branch before adding subjects.",
        )
    # Newest academic year (highest start year) carries new subjects.
    academic_year = max(years, key=lambda y: getattr(y, "start_year", 0) or 0)

    created = await subject_seeding.build_subject_skeleton(
        session, branch_id, course, academic_year, syllabus_key, import_id=None
    )
    if created:
        await audit_service.log_action(
            session, user_id=current_user_id, action="CREATE",
            table_name="subjects", record_id=course.id,
            new_values={"course_id": str(course_id), "syllabus_key": syllabus_key, "created": created},
            ip_address=ip_address, branch_id=branch_id,
        )
    subjects = await academic_repository.list_subjects(session, branch_id, course_id)
    return created, subjects


async def delete_subject(
    session: AsyncSession,
    subject_id: uuid.UUID,
    branch_id: uuid.UUID,
    current_user_id: uuid.UUID,
    ip_address: str | None = None,
):
    subject = await academic_repository.get_subject(session, subject_id)
    if not subject:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found")
    if subject.branch_id != branch_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this branch")

    in_use = await academic_repository.count_lectures_using_subject(session, subject_id)
    if in_use:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot delete: {in_use} lecture(s) use this subject.",
        )

    await academic_repository.soft_delete_subject(session, subject)
    await audit_service.log_action(
        session, user_id=current_user_id, action="DELETE",
        table_name="subjects", record_id=subject.id,
        old_values={"name": subject.name, "code": subject.code, "course_id": str(subject.course_id)},
        ip_address=ip_address, branch_id=branch_id,
    )


async def create_chapter(session: AsyncSession, data: dict, current_user_id: uuid.UUID, ip_address: str | None = None):
    ch = await academic_repository.create_chapter(session, **data)
    await audit_service.log_action(
        session, user_id=current_user_id, action="CREATE",
        table_name="chapters", record_id=ch.id, new_values=data,
        ip_address=ip_address, branch_id=data.get("branch_id"),
    )
    return ch


async def create_topic(session: AsyncSession, data: dict, current_user_id: uuid.UUID, ip_address: str | None = None):
    t = await academic_repository.create_topic(session, **data)
    await audit_service.log_action(
        session, user_id=current_user_id, action="CREATE",
        table_name="topics", record_id=t.id, new_values=data,
        ip_address=ip_address, branch_id=data.get("branch_id"),
    )
    return t


async def create_subtopic(session: AsyncSession, data: dict, current_user_id: uuid.UUID, ip_address: str | None = None):
    st = await academic_repository.create_subtopic(session, **data)
    await audit_service.log_action(
        session, user_id=current_user_id, action="CREATE",
        table_name="subtopics", record_id=st.id, new_values=data,
        ip_address=ip_address, branch_id=data.get("branch_id"),
    )
    return st
