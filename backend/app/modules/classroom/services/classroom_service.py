import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.services import audit_service
from app.modules.classroom.repositories import classroom_repository
from app.modules.classroom.schemas.classroom_schemas import ClassroomCreate, ClassroomUpdate


async def create_classroom(
    session: AsyncSession,
    data: ClassroomCreate,
    current_user_id: uuid.UUID,
    ip_address: str | None = None,
):
    classroom = await classroom_repository.create(session, **data.model_dump())
    await audit_service.log_action(
        session,
        user_id=current_user_id,
        action="CREATE",
        table_name="classrooms",
        record_id=classroom.id,
        new_values=data.model_dump(),
        ip_address=ip_address,
        branch_id=data.branch_id,
    )
    return classroom


async def get_classroom(session: AsyncSession, classroom_id: uuid.UUID, branch_id: uuid.UUID):
    classroom = await classroom_repository.get_by_id(session, classroom_id)
    if not classroom:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Classroom not found")
    if classroom.branch_id != branch_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this branch")
    return classroom


async def list_classrooms(session: AsyncSession, branch_id: uuid.UUID, offset: int = 0, limit: int = 50):
    return await classroom_repository.list_by_branch(session, branch_id, offset, limit)


async def update_classroom(
    session: AsyncSession,
    classroom_id: uuid.UUID,
    data: ClassroomUpdate,
    branch_id: uuid.UUID,
    current_user_id: uuid.UUID,
    ip_address: str | None = None,
):
    classroom = await classroom_repository.get_by_id(session, classroom_id)
    if not classroom:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Classroom not found")
    if classroom.branch_id != branch_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this branch")

    old_values = {"name": classroom.name, "code": classroom.code, "capacity": classroom.capacity}
    update_data = data.model_dump(exclude_unset=True)
    classroom = await classroom_repository.update(session, classroom, **update_data)

    await audit_service.log_action(
        session,
        user_id=current_user_id,
        action="UPDATE",
        table_name="classrooms",
        record_id=classroom.id,
        old_values=old_values,
        new_values=update_data,
        ip_address=ip_address,
        branch_id=branch_id,
    )
    return classroom


async def delete_classroom(
    session: AsyncSession,
    classroom_id: uuid.UUID,
    branch_id: uuid.UUID,
    current_user_id: uuid.UUID,
    ip_address: str | None = None,
):
    classroom = await classroom_repository.get_by_id(session, classroom_id)
    if not classroom:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Classroom not found")
    if classroom.branch_id != branch_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this branch")

    await classroom_repository.soft_delete(session, classroom)
    await audit_service.log_action(
        session,
        user_id=current_user_id,
        action="DELETE",
        table_name="classrooms",
        record_id=classroom.id,
        old_values={"name": classroom.name, "code": classroom.code},
        ip_address=ip_address,
        branch_id=branch_id,
    )
