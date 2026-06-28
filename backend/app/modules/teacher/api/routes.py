import uuid

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.modules.auth.permissions.rbac import get_current_user, require_roles
from app.modules.teacher.schemas.teacher_schemas import (
    BulkDeleteSummary,
    BulkTeacherDelete,
    ImportSummary,
    TeacherCreate,
    TeacherResponse,
    TeacherSubjectsResponse,
    TeacherSubjectsUpdate,
    TeacherUpdate,
    TeacherWithStats,
)
from app.modules.teacher.services import import_service, teacher_service

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


@router.get("/with-stats", response_model=list[TeacherWithStats])
async def list_teachers_with_stats(
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Roster with last-30-day adherence + outcome metrics — powers the
    MSA_Design teachers table (Lectures, Sub rate, Avg outcome)."""
    return await teacher_service.list_teachers_with_stats(session, branch_id)


@router.get("/subject-options", response_model=list[str])
async def list_subject_options(
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Distinct subject names in the branch — the assignable-subjects picker for
    the teacher create/edit dialogs. Before ``/{teacher_id}`` so the literal
    path wins."""
    return await teacher_service.list_subject_options(session, branch_id)


@router.get("/by-subject", response_model=list[TeacherResponse])
async def list_teachers_by_subject(
    branch_id: uuid.UUID = Query(...),
    subject_id: uuid.UUID = Query(...),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Teachers assigned to the given subject (Subject→Teacher lock).

    Registered before ``/{teacher_id}`` so the literal path wins over the
    UUID path param. Drives the schedule form's teacher dropdown.
    """
    return await teacher_service.list_teachers_for_subject(
        session, branch_id, subject_id
    )


@router.post("/bulk-delete", response_model=BulkDeleteSummary)
async def bulk_delete_teachers(
    body: BulkTeacherDelete,
    request: Request,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin"])),
    session: AsyncSession = Depends(get_db),
):
    """Soft-delete a selected set of teachers from the roster. Literal path —
    registered before ``/{teacher_id}`` so it isn't captured as a UUID param."""
    return await teacher_service.bulk_delete_teachers(
        session,
        branch_id,
        body.teacher_ids,
        current_user["user_id"],
        request.client.host if request.client else None,
    )


@router.get("/{teacher_id}", response_model=TeacherResponse)
async def get_teacher(
    teacher_id: uuid.UUID,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    return await teacher_service.get_teacher(session, teacher_id, branch_id)


@router.get("/{teacher_id}/subjects", response_model=TeacherSubjectsResponse)
async def get_teacher_subjects(
    teacher_id: uuid.UUID,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Subject names a teacher is assigned to teach."""
    subjects = await teacher_service.get_teacher_subjects(
        session, teacher_id, branch_id
    )
    return {"subjects": subjects}


@router.put("/{teacher_id}/subjects", response_model=TeacherSubjectsResponse)
async def set_teacher_subjects(
    teacher_id: uuid.UUID,
    body: TeacherSubjectsUpdate,
    request: Request,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin"])),
    session: AsyncSession = Depends(get_db),
):
    """Replace a teacher's subject assignments (by name). Powers the
    Subject→Teacher lock so the teacher becomes schedulable for those subjects.
    """
    subjects = await teacher_service.set_teacher_subjects(
        session, teacher_id, branch_id, body.subjects, current_user["user_id"],
        request.client.host if request.client else None,
    )
    return {"subjects": subjects}


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


@router.post("/import", response_model=ImportSummary)
async def import_teachers(
    request: Request,
    file: UploadFile = File(...),
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin"])),
    session: AsyncSession = Depends(get_db),
):
    return await import_service.import_teachers(
        session,
        file,
        branch_id,
        current_user["user_id"],
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
