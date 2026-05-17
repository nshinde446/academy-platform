import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.modules.auth.permissions.rbac import get_current_user, require_roles
from app.modules.teacher.schemas.teacher_schemas import (
    TeacherCreate,
    TeacherResponse,
    TeacherUpdate,
)
from app.modules.teacher.services import teacher_service

router = APIRouter(prefix="/teachers", tags=["teachers"])


@router.post("", response_model=TeacherResponse)
async def create_teacher(
    body: TeacherCreate,
    request: Request,
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin"])),
    session: AsyncSession = Depends(get_db),
):
    return await teacher_service.create_teacher(
        session, body, current_user["user_id"],
        request.client.host if request.client else None,
    )


@router.get("", response_model=list[TeacherResponse])
async def list_teachers(
    branch_id: uuid.UUID = Query(...),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    return await teacher_service.list_teachers(session, branch_id, offset, limit)


@router.get("/{teacher_id}", response_model=TeacherResponse)
async def get_teacher(
    teacher_id: uuid.UUID,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    return await teacher_service.get_teacher(session, teacher_id, branch_id)


@router.patch("/{teacher_id}", response_model=TeacherResponse)
async def update_teacher(
    teacher_id: uuid.UUID,
    body: TeacherUpdate,
    request: Request,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin"])),
    session: AsyncSession = Depends(get_db),
):
    return await teacher_service.update_teacher(
        session, teacher_id, body, branch_id, current_user["user_id"],
        request.client.host if request.client else None,
    )


@router.delete("/{teacher_id}", status_code=204)
async def delete_teacher(
    teacher_id: uuid.UUID,
    request: Request,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin"])),
    session: AsyncSession = Depends(get_db),
):
    await teacher_service.delete_teacher(
        session, teacher_id, branch_id, current_user["user_id"],
        request.client.host if request.client else None,
    )
