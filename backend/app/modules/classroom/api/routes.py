import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.modules.auth.permissions.rbac import get_current_user, require_roles
from app.modules.classroom.schemas.classroom_schemas import (
    ClassroomCreate,
    ClassroomResponse,
    ClassroomUpdate,
)
from app.modules.classroom.services import classroom_service

router = APIRouter(prefix="/classrooms", tags=["classrooms"])


@router.post("", response_model=ClassroomResponse)
async def create_classroom(
    body: ClassroomCreate,
    request: Request,
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin"])),
    session: AsyncSession = Depends(get_db),
):
    return await classroom_service.create_classroom(
        session, body, current_user["user_id"],
        request.client.host if request.client else None,
    )


@router.get("", response_model=list[ClassroomResponse])
async def list_classrooms(
    branch_id: uuid.UUID = Query(...),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    return await classroom_service.list_classrooms(session, branch_id, offset, limit)


@router.get("/{classroom_id}", response_model=ClassroomResponse)
async def get_classroom(
    classroom_id: uuid.UUID,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    return await classroom_service.get_classroom(session, classroom_id, branch_id)


@router.patch("/{classroom_id}", response_model=ClassroomResponse)
async def update_classroom(
    classroom_id: uuid.UUID,
    body: ClassroomUpdate,
    request: Request,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin"])),
    session: AsyncSession = Depends(get_db),
):
    return await classroom_service.update_classroom(
        session, classroom_id, body, branch_id, current_user["user_id"],
        request.client.host if request.client else None,
    )


@router.delete("/{classroom_id}", status_code=204)
async def delete_classroom(
    classroom_id: uuid.UUID,
    request: Request,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin"])),
    session: AsyncSession = Depends(get_db),
):
    await classroom_service.delete_classroom(
        session, classroom_id, branch_id, current_user["user_id"],
        request.client.host if request.client else None,
    )
