import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.modules.auth.permissions.rbac import require_roles
from app.modules.analytics.schemas.analytics_schemas import (
    BatchAnalyticsResponse,
    RiskStudentResponse,
    StudentAnalyticsResponse,
    TeacherAnalyticsResponse,
)
from app.modules.analytics.services import analytics_service

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/students/{student_id}", response_model=StudentAnalyticsResponse)
async def get_student_analytics(
    student_id: uuid.UUID,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin", "academic_head", "teacher"])),
    session: AsyncSession = Depends(get_db),
):
    return await analytics_service.get_student_analytics(session, student_id, branch_id)


@router.get("/teachers/{teacher_id}", response_model=TeacherAnalyticsResponse)
async def get_teacher_analytics(
    teacher_id: uuid.UUID,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin", "academic_head"])),
    session: AsyncSession = Depends(get_db),
):
    return await analytics_service.get_teacher_analytics(session, teacher_id, branch_id)


@router.get("/batches/{batch_id}", response_model=BatchAnalyticsResponse)
async def get_batch_analytics(
    batch_id: uuid.UUID,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin", "academic_head", "teacher"])),
    session: AsyncSession = Depends(get_db),
):
    return await analytics_service.get_batch_analytics(session, batch_id, branch_id)


@router.get("/batches/{batch_id}/risk-students", response_model=list[RiskStudentResponse])
async def get_risk_students(
    batch_id: uuid.UUID,
    branch_id: uuid.UUID = Query(...),
    threshold: float = Query(50.0, ge=0, le=100),
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin", "academic_head", "teacher"])),
    session: AsyncSession = Depends(get_db),
):
    return await analytics_service.get_risk_students(session, branch_id, threshold)


@router.post("/refresh", status_code=200)
async def refresh_analytics(
    request: Request,
    branch_id: uuid.UUID = Query(...),
    academic_year_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(["super_admin"])),
    session: AsyncSession = Depends(get_db),
):
    await analytics_service.refresh_all(
        session, branch_id, academic_year_id,
        current_user_id=current_user["user_id"],
        ip_address=request.client.host if request.client else None,
    )
    return {"message": "Analytics refreshed successfully"}
