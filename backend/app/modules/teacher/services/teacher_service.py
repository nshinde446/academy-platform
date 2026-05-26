import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.services import audit_service
from app.modules.teacher.repositories import teacher_repository
from app.modules.teacher.schemas.teacher_schemas import TeacherCreate, TeacherUpdate


async def create_teacher(
    session: AsyncSession,
    data: TeacherCreate,
    current_user_id: uuid.UUID,
    ip_address: str | None = None,
):
    teacher = await teacher_repository.create(session, **data.model_dump())
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
