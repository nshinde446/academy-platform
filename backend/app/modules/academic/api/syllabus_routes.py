import uuid

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.modules.academic.schemas.academic_schemas import (
    CurriculumBackfillSummary,
)
from app.modules.academic.services import syllabus_import_service
from app.modules.auth.permissions.rbac import require_roles

router = APIRouter(prefix="/syllabus", tags=["syllabus"])


@router.post("/import")
async def import_syllabus(
    request: Request,
    course_id: uuid.UUID = Query(...),
    file: UploadFile = File(...),
    current_user: dict = Depends(
        require_roles(["super_admin", "branch_admin", "academic_head"])
    ),
    session: AsyncSession = Depends(get_db),
):
    return await syllabus_import_service.import_syllabus(
        session,
        file,
        course_id,
        current_user["user_id"],
        request.client.host if request.client else None,
    )


@router.post("/backfill", response_model=CurriculumBackfillSummary)
async def backfill_curriculum(
    request: Request,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(
        require_roles(["super_admin", "branch_admin", "academic_head"])
    ),
    session: AsyncSession = Depends(get_db),
):
    """Load the bundled master curriculum (chapters/topics) onto this branch's
    existing course subjects that have none yet, keyed to each course's Target.
    Additive + idempotent — subjects that already have a curriculum are left
    untouched. Use this to map the master syllabus onto students imported
    before the curriculum auto-population existed."""
    return await syllabus_import_service.backfill_curriculum(
        session,
        branch_id,
        current_user["user_id"],
        request.client.host if request.client else None,
    )
