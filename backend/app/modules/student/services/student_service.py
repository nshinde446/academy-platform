import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.services import audit_service
from app.modules.student.repositories import student_repository
from app.modules.student.schemas.student_schemas import StudentCreate, StudentUpdate

# Enrolment validations. Drives the /students/[id] cohort segmentation
# and the future at-risk / topic-mastery analytics.
VALID_STANDARDS = {"9", "10", "11", "12", "Dropper"}
VALID_TARGET_EXAMS = {
    "NEET",
    "JEE-Main",
    "JEE-Advanced",
    "MHT-CET",    # Maharashtra state engineering / pharmacy entrance
    "Both",       # NEET + JEE dual-prep
    "Foundation", # Class 9/10 foundation programs
    "Other",
}


def _validate_enrolment_fields(standard: str | None, target_exam: str | None):
    if standard is not None and standard not in VALID_STANDARDS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Invalid standard '{standard}'. "
                f"Allowed: {sorted(VALID_STANDARDS)}"
            ),
        )
    if target_exam is not None and target_exam not in VALID_TARGET_EXAMS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Invalid target_exam '{target_exam}'. "
                f"Allowed: {sorted(VALID_TARGET_EXAMS)}"
            ),
        )


async def create_student(
    session: AsyncSession,
    data: StudentCreate,
    current_user_id: uuid.UUID,
    ip_address: str | None = None,
):
    _validate_enrolment_fields(data.standard, data.target_exam)
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


async def list_students_with_stats(session: AsyncSession, branch_id: uuid.UUID):
    return await student_repository.list_with_stats(session, branch_id)


async def get_test_history(
    session: AsyncSession, student_id: uuid.UUID, branch_id: uuid.UUID
):
    # Ownership check — surfaces 404 the same way get_student does.
    await get_student(session, student_id, branch_id)
    return await student_repository.get_test_history(session, student_id, branch_id)


async def get_topic_mastery(
    session: AsyncSession, student_id: uuid.UUID, branch_id: uuid.UUID
):
    # Ownership check — surfaces 404 the same way get_student does.
    await get_student(session, student_id, branch_id)
    return await student_repository.get_topic_mastery(session, student_id, branch_id)


async def get_upcoming_tests(
    session: AsyncSession, student_id: uuid.UUID, branch_id: uuid.UUID
):
    # Ownership check — surfaces 404 the same way get_student does.
    await get_student(session, student_id, branch_id)
    return await student_repository.get_upcoming_tests(session, student_id, branch_id)


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
    _validate_enrolment_fields(
        update_data.get("standard"), update_data.get("target_exam")
    )
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
