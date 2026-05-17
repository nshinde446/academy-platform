import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.services import audit_service
from app.modules.student.repositories import student_repository
from app.modules.student.schemas.student_schemas import StudentCreate, StudentUpdate


async def create_student(
    session: AsyncSession,
    data: StudentCreate,
    current_user_id: uuid.UUID,
    ip_address: str | None = None,
):
    student = await student_repository.create(session, **data.model_dump())

    await audit_service.log_action(
        session,
        user_id=current_user_id,
        action="CREATE",
        table_name="students",
        record_id=student.id,
        new_values=data.model_dump(),
        ip_address=ip_address,
        branch_id=data.branch_id,
    )
    return student


async def get_student(
    session: AsyncSession, student_id: uuid.UUID, branch_id: uuid.UUID
):
    student = await student_repository.get_by_id(session, student_id)
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")
    if student.branch_id != branch_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this branch")
    return student


async def list_students(session: AsyncSession, branch_id: uuid.UUID, offset: int = 0, limit: int = 50):
    return await student_repository.list_by_branch(session, branch_id, offset, limit)


async def update_student(
    session: AsyncSession,
    student_id: uuid.UUID,
    data: StudentUpdate,
    branch_id: uuid.UUID,
    current_user_id: uuid.UUID,
    ip_address: str | None = None,
):
    student = await student_repository.get_by_id(session, student_id)
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")
    if student.branch_id != branch_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this branch")

    old_values = {
        "first_name": student.first_name,
        "last_name": student.last_name,
        "email": student.email,
        "phone": student.phone,
    }

    update_data = data.model_dump(exclude_unset=True)
    student = await student_repository.update(session, student, **update_data)

    await audit_service.log_action(
        session,
        user_id=current_user_id,
        action="UPDATE",
        table_name="students",
        record_id=student.id,
        old_values=old_values,
        new_values=update_data,
        ip_address=ip_address,
        branch_id=branch_id,
    )
    return student


async def delete_student(
    session: AsyncSession,
    student_id: uuid.UUID,
    branch_id: uuid.UUID,
    current_user_id: uuid.UUID,
    ip_address: str | None = None,
):
    student = await student_repository.get_by_id(session, student_id)
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")
    if student.branch_id != branch_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this branch")

    await student_repository.soft_delete(session, student)

    await audit_service.log_action(
        session,
        user_id=current_user_id,
        action="DELETE",
        table_name="students",
        record_id=student.id,
        old_values={"first_name": student.first_name, "last_name": student.last_name},
        ip_address=ip_address,
        branch_id=branch_id,
    )
