import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.modules.auth.permissions.rbac import get_current_user, require_roles
from app.modules.lectures.schemas.lecture_schemas import (
    AttendanceMark,
    AttendanceResponse,
    LectureCreate,
    LectureReschedule,
    LectureResponse,
    LectureSubstitute,
)
from app.modules.lectures.services import lecture_service

router = APIRouter(prefix="/lectures", tags=["lectures"])


@router.post("", response_model=LectureResponse)
async def schedule_lecture(
    body: LectureCreate,
    request: Request,
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin", "academic_head"])),
    session: AsyncSession = Depends(get_db),
):
    return await lecture_service.schedule_lecture(
        session, body, current_user["user_id"],
        request.client.host if request.client else None,
    )


@router.get("", response_model=list[LectureResponse])
async def list_lectures(
    branch_id: uuid.UUID = Query(...),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    return await lecture_service.list_lectures(session, branch_id, offset, limit)


@router.get("/{lecture_id}", response_model=LectureResponse)
async def get_lecture(
    lecture_id: uuid.UUID,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    return await lecture_service.get_lecture(session, lecture_id, branch_id)


@router.patch("/{lecture_id}/start", response_model=LectureResponse)
async def start_lecture(
    lecture_id: uuid.UUID,
    request: Request,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(["super_admin", "teacher"])),
    session: AsyncSession = Depends(get_db),
):
    return await lecture_service.start_lecture(
        session, lecture_id, branch_id, current_user["user_id"],
        request.client.host if request.client else None,
    )


@router.patch("/{lecture_id}/complete", response_model=LectureResponse)
async def complete_lecture(
    lecture_id: uuid.UUID,
    request: Request,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(["super_admin", "teacher"])),
    session: AsyncSession = Depends(get_db),
):
    return await lecture_service.complete_lecture(
        session, lecture_id, branch_id, current_user["user_id"],
        request.client.host if request.client else None,
    )


@router.patch("/{lecture_id}/cancel", response_model=LectureResponse)
async def cancel_lecture(
    lecture_id: uuid.UUID,
    request: Request,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin"])),
    session: AsyncSession = Depends(get_db),
):
    return await lecture_service.cancel_lecture(
        session, lecture_id, branch_id, current_user["user_id"],
        request.client.host if request.client else None,
    )


@router.patch("/{lecture_id}/substitute", response_model=LectureResponse)
async def mark_substitute(
    lecture_id: uuid.UUID,
    body: LectureSubstitute,
    request: Request,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin", "academic_head"])),
    session: AsyncSession = Depends(get_db),
):
    return await lecture_service.mark_substitute(
        session, lecture_id, body, branch_id, current_user["user_id"],
        request.client.host if request.client else None,
    )


@router.patch("/{lecture_id}/reschedule", response_model=LectureResponse)
async def reschedule_lecture(
    lecture_id: uuid.UUID,
    body: LectureReschedule,
    request: Request,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin", "academic_head"])),
    session: AsyncSession = Depends(get_db),
):
    return await lecture_service.reschedule_lecture(
        session, lecture_id, body, branch_id, current_user["user_id"],
        request.client.host if request.client else None,
    )


@router.post("/{lecture_id}/attendance", response_model=AttendanceResponse)
async def mark_attendance(
    lecture_id: uuid.UUID,
    body: AttendanceMark,
    request: Request,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(["super_admin", "teacher"])),
    session: AsyncSession = Depends(get_db),
):
    return await lecture_service.mark_attendance(
        session, lecture_id, body, branch_id, current_user["user_id"],
        request.client.host if request.client else None,
    )


@router.get("/{lecture_id}/attendance", response_model=list[AttendanceResponse])
async def get_attendance(
    lecture_id: uuid.UUID,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin", "academic_head", "teacher"])),
    session: AsyncSession = Depends(get_db),
):
    return await lecture_service.get_attendance(session, lecture_id, branch_id)


@router.delete("/{lecture_id}", status_code=204)
async def delete_lecture(
    lecture_id: uuid.UUID,
    request: Request,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin"])),
    session: AsyncSession = Depends(get_db),
):
    await lecture_service.delete_lecture(
        session, lecture_id, branch_id, current_user["user_id"],
        request.client.host if request.client else None,
    )
