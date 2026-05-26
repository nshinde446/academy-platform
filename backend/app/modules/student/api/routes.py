import uuid

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.modules.auth.permissions.rbac import get_current_user, require_roles
from app.modules.student.schemas.student_schemas import (
    ImportSummary,
    StudentCreate,
    StudentResponse,
    StudentUpdate,
    StudentWithStats,
)
from app.modules.student.services import import_service, student_service

router = APIRouter(prefix="/students", tags=["students"])


@router.post("", response_model=StudentResponse)
async def create_student(
    body: StudentCreate,
    request: Request,
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin"])),
    session: AsyncSession = Depends(get_db),
):
    return await student_service.create_student(
        session, body, current_user["user_id"],
        request.client.host if request.client else None,
    )


@router.get("", response_model=list[StudentResponse])
async def list_students(
    branch_id: uuid.UUID = Query(...),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    return await student_service.list_students(session, branch_id, offset, limit)


@router.get("/with-stats", response_model=list[StudentWithStats])
async def list_students_with_stats(
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Roster with per-student analytics (avg score, attendance %, DPP
    completion %, batch rank) — powers the MSA_Design students table."""
    return await student_service.list_students_with_stats(session, branch_id)


@router.get("/{student_id}", response_model=StudentResponse)
async def get_student(
    student_id: uuid.UUID,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    return await student_service.get_student(session, student_id, branch_id)


@router.patch("/{student_id}", response_model=StudentResponse)
async def update_student(
    student_id: uuid.UUID,
    body: StudentUpdate,
    request: Request,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin"])),
    session: AsyncSession = Depends(get_db),
):
    return await student_service.update_student(
        session, student_id, body, branch_id, current_user["user_id"],
        request.client.host if request.client else None,
    )


@router.post("/import", response_model=ImportSummary)
async def import_students(
    request: Request,
    file: UploadFile = File(...),
    branch_id: uuid.UUID = Query(...),
    standard: str = Query(..., description="Class/standard applied to all imported rows"),
    target_exam: str = Query(..., description="Exam track applied to all imported rows"),
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin"])),
    session: AsyncSession = Depends(get_db),
):
    """Bulk import students. Standard + target_exam are picked once in
    the dialog and applied to every row in the file, so the CSV/Excel
    only needs name and contact columns."""
    return await import_service.import_students(
        session,
        file,
        branch_id,
        current_user["user_id"],
        request.client.host if request.client else None,
        standard=standard,
        target_exam=target_exam,
    )


@router.delete("/{student_id}", status_code=204)
async def delete_student(
    student_id: uuid.UUID,
    request: Request,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin"])),
    session: AsyncSession = Depends(get_db),
):
    await student_service.delete_student(
        session, student_id, branch_id, current_user["user_id"],
        request.client.host if request.client else None,
    )
