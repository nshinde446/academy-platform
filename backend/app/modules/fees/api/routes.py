import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.modules.auth.permissions.rbac import require_roles
from app.modules.fees.schemas.fee_schemas import (
    CourseFeeConfigResponse,
    CourseFeeConfigUpsert,
    StudentFeeProfileCreate,
    StudentFeeProfileResponse,
)
from app.modules.fees.services import fee_service

router = APIRouter(prefix="/fees", tags=["fees"])

# Manager = super_admin / branch_admin; Accounts Staff = the existing `accounts`
# role. Config changes are manager-only (spec §12); profile create/read is both.
_MANAGER = ["super_admin", "branch_admin"]
_MANAGER_OR_ACCOUNTS = ["super_admin", "branch_admin", "accounts"]


@router.get("/config", response_model=list[CourseFeeConfigResponse])
async def list_course_fees(
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(_MANAGER_OR_ACCOUNTS)),
    session: AsyncSession = Depends(get_db),
):
    """Standard course fees for the branch (auto-fills a new profile's actual fee)."""
    return await fee_service.list_course_fees(session, branch_id)


@router.post("/config", response_model=CourseFeeConfigResponse)
async def set_course_fee(
    body: CourseFeeConfigUpsert,
    request: Request,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(_MANAGER)),
    session: AsyncSession = Depends(get_db),
):
    """Set/update a course's standard fee (manager only). Affects only new
    admissions — existing profiles are unchanged (spec §1)."""
    return await fee_service.upsert_course_fee(
        session, branch_id=branch_id, course_name=body.course_name,
        standard_fee=body.standard_fee, user_id=current_user["user_id"],
        ip_address=request.client.host if request.client else None,
    )


@router.post("/student", response_model=StudentFeeProfileResponse)
async def create_fee_profile(
    body: StudentFeeProfileCreate,
    request: Request,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(_MANAGER_OR_ACCOUNTS)),
    session: AsyncSession = Depends(get_db),
):
    """Create a student's fee profile + installment schedule at admission
    (spec §2). ONE_TIME → one PAID row; INSTALLMENT → an explicit plan or the
    auto-generated 2.5-month schedule. Installments must sum to the agreed fee."""
    return await fee_service.create_fee_profile(
        session, body.model_dump(), branch_id, current_user["user_id"],
        request.client.host if request.client else None,
    )


@router.get("/student/{student_id}", response_model=StudentFeeProfileResponse)
async def get_fee_profile(
    student_id: uuid.UUID,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(_MANAGER_OR_ACCOUNTS)),
    session: AsyncSession = Depends(get_db),
):
    """A student's full fee profile with its installment schedule (spec §7)."""
    return await fee_service.get_fee_profile(session, student_id, branch_id)
