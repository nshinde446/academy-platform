import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.academic.repositories import academic_repository
from app.modules.audit.services import audit_service
from app.modules.teacher.repositories import teacher_repository
from app.modules.teacher.schemas.teacher_schemas import TeacherCreate, TeacherUpdate


async def _resolve_subject_ids(
    session: AsyncSession, branch_id: uuid.UUID, names: list[str]
) -> list[uuid.UUID]:
    """Subject names → every matching subject row's id (a name can repeat across
    courses, e.g. JEE Physics and NEET Physics)."""
    subjects = await academic_repository.find_subjects_by_names(
        session, branch_id, names
    )
    return [s.id for s in subjects]


async def create_teacher(
    session: AsyncSession,
    data: TeacherCreate,
    current_user_id: uuid.UUID,
    ip_address: str | None = None,
):
    payload = data.model_dump(exclude={"subjects"})
    teacher = await teacher_repository.create(session, **payload)
    # Assign subjects up front so the teacher is schedulable immediately
    # (Subject→Teacher lock). Unknown names are simply ignored here; the
    # /subjects editor surfaces the available options.
    if data.subjects:
        subject_ids = await _resolve_subject_ids(
            session, data.branch_id, data.subjects
        )
        if subject_ids:
            await teacher_repository.set_subject_mappings(
                session, teacher.id, data.branch_id, subject_ids
            )
    await audit_service.log_action(
        session,
        user_id=current_user_id,
        action="CREATE",
        table_name="teachers",
        record_id=teacher.id,
        new_values=data.model_dump(),
        ip_address=ip_address,
        branch_id=data.branch_id,
    )
    return teacher


async def list_subject_options(
    session: AsyncSession, branch_id: uuid.UUID
) -> list[str]:
    """Distinct subject names in the branch — the assignable-subjects picker."""
    subjects = await academic_repository.list_subjects(session, branch_id)
    return sorted({s.name for s in subjects}, key=str.lower)


async def get_teacher_subjects(
    session: AsyncSession, teacher_id: uuid.UUID, branch_id: uuid.UUID
) -> list[str]:
    teacher = await teacher_repository.get_by_id(session, teacher_id)
    if not teacher:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Teacher not found")
    if teacher.branch_id != branch_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this branch")
    ids = await teacher_repository.list_subject_ids_for_teacher(session, teacher_id)
    if not ids:
        return []
    subjects = await academic_repository.list_subjects(session, branch_id)
    by_id = {s.id: s.name for s in subjects}
    return sorted({by_id[i] for i in ids if i in by_id}, key=str.lower)


async def set_teacher_subjects(
    session: AsyncSession,
    teacher_id: uuid.UUID,
    branch_id: uuid.UUID,
    subject_names: list[str],
    current_user_id: uuid.UUID,
    ip_address: str | None = None,
) -> list[str]:
    """Replace a teacher's subject assignments (by name). Returns the resolved
    distinct names actually applied."""
    teacher = await teacher_repository.get_by_id(session, teacher_id)
    if not teacher:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Teacher not found")
    if teacher.branch_id != branch_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this branch")

    subject_ids = await _resolve_subject_ids(session, branch_id, subject_names)
    await teacher_repository.set_subject_mappings(
        session, teacher_id, branch_id, subject_ids
    )
    await audit_service.log_action(
        session,
        user_id=current_user_id,
        action="UPDATE",
        table_name="teacher_subject_mappings",
        record_id=teacher_id,
        new_values={"subjects": subject_names},
        ip_address=ip_address,
        branch_id=branch_id,
    )
    return await get_teacher_subjects(session, teacher_id, branch_id)


async def get_teacher(session: AsyncSession, teacher_id: uuid.UUID, branch_id: uuid.UUID):
    teacher = await teacher_repository.get_by_id(session, teacher_id)
    if not teacher:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Teacher not found")
    if teacher.branch_id != branch_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this branch")
    return teacher


async def list_teachers(session: AsyncSession, branch_id: uuid.UUID, offset: int = 0, limit: int = 50):
    return await teacher_repository.list_by_branch(session, branch_id, offset, limit)


async def list_teachers_with_stats(session: AsyncSession, branch_id: uuid.UUID):
    return await teacher_repository.list_with_stats(session, branch_id)


async def list_teachers_for_subject(
    session: AsyncSession, branch_id: uuid.UUID, subject_id: uuid.UUID
):
    """Teachers assigned to a subject — the schedule form's filtered dropdown."""
    return await teacher_repository.list_for_subject(session, branch_id, subject_id)


async def update_teacher(
    session: AsyncSession,
    teacher_id: uuid.UUID,
    data: TeacherUpdate,
    branch_id: uuid.UUID,
    current_user_id: uuid.UUID,
    ip_address: str | None = None,
):
    teacher = await teacher_repository.get_by_id(session, teacher_id)
    if not teacher:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Teacher not found")
    if teacher.branch_id != branch_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this branch")

    old_values = {"first_name": teacher.first_name, "last_name": teacher.last_name, "email": teacher.email}
    update_data = data.model_dump(exclude_unset=True)
    teacher = await teacher_repository.update(session, teacher, **update_data)

    await audit_service.log_action(
        session,
        user_id=current_user_id,
        action="UPDATE",
        table_name="teachers",
        record_id=teacher.id,
        old_values=old_values,
        new_values=update_data,
        ip_address=ip_address,
        branch_id=branch_id,
    )
    return teacher


async def delete_teacher(
    session: AsyncSession,
    teacher_id: uuid.UUID,
    branch_id: uuid.UUID,
    current_user_id: uuid.UUID,
    ip_address: str | None = None,
):
    teacher = await teacher_repository.get_by_id(session, teacher_id)
    if not teacher:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Teacher not found")
    if teacher.branch_id != branch_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this branch")

    await teacher_repository.soft_delete(session, teacher)
    await audit_service.log_action(
        session,
        user_id=current_user_id,
        action="DELETE",
        table_name="teachers",
        record_id=teacher.id,
        old_values={"first_name": teacher.first_name, "last_name": teacher.last_name},
        ip_address=ip_address,
        branch_id=branch_id,
    )
