import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.modules.auth.permissions.rbac import require_roles
from app.modules.reports.schemas.report_schemas import (
    JobCreate,
    JobResponse,
    TemplateCreate,
    TemplateResponse,
    TemplateUpdate,
)
from app.modules.reports.services import report_service

router = APIRouter(prefix="/reports", tags=["reports"])


@router.post("/templates", response_model=TemplateResponse, status_code=201)
async def create_template(
    body: TemplateCreate,
    request: Request,
    current_user: dict = Depends(require_roles(["super_admin"])),
    session: AsyncSession = Depends(get_db),
):
    return await report_service.create_template(
        session,
        data=body.model_dump(),
        current_user_id=current_user["user_id"],
        ip_address=request.client.host if request.client else None,
    )


@router.get("/templates", response_model=list[TemplateResponse])
async def list_templates(
    branch_id: uuid.UUID | None = Query(None),
    report_type: str | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin", "academic_head"])),
    session: AsyncSession = Depends(get_db),
):
    return await report_service.list_templates(
        session, branch_id=branch_id, report_type=report_type,
        offset=offset, limit=limit,
    )


@router.post("/generate", response_model=JobResponse, status_code=201)
async def generate_report(
    body: JobCreate,
    request: Request,
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin", "academic_head", "teacher"])),
    session: AsyncSession = Depends(get_db),
):
    job = await report_service.create_job(
        session,
        data=body.model_dump(),
        current_user_id=current_user["user_id"],
        ip_address=request.client.host if request.client else None,
    )
    await report_service.generate_report(session, job["id"])
    return await report_service.get_job_status(session, job["id"])


@router.get("/jobs", response_model=list[JobResponse])
async def list_jobs(
    job_status: str | None = Query(None),
    branch_id: uuid.UUID | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin", "academic_head", "teacher"])),
    session: AsyncSession = Depends(get_db),
):
    if "super_admin" in current_user.get("roles", []):
        return await report_service.list_jobs(
            session, branch_id=branch_id, job_status=job_status,
            offset=offset, limit=limit,
        )
    return await report_service.list_jobs(
        session, requested_by=current_user["user_id"],
        branch_id=branch_id, job_status=job_status,
        offset=offset, limit=limit,
    )


@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: uuid.UUID,
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin", "academic_head", "teacher"])),
    session: AsyncSession = Depends(get_db),
):
    return await report_service.get_job_status(session, job_id)


@router.get("/jobs/{job_id}/download")
async def download_report(
    job_id: uuid.UUID,
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin", "academic_head", "teacher"])),
    session: AsyncSession = Depends(get_db),
):
    return await report_service.get_download_url(session, job_id)
