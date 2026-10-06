import uuid

from fastapi import APIRouter, Depends, File, Query, Request, Response, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.modules.auth.permissions.rbac import (
    get_current_user,
    require_manager_or_audit,
    require_roles,
)
from app.modules.teacher.schemas.teacher_schemas import (
    BulkDeleteSummary,
    BulkTeacherDelete,
    ImportSummary,
    SecondarySubjectAssign,
    SecondarySubjectRow,
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
    # Floor Coordinators may add teachers too (only Delete is Manager-only).
    current_user: dict = Depends(
        require_roles(["super_admin", "branch_admin", "floor_coordinator"])
    ),
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
    batch_id: uuid.UUID | None = Query(None),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Teachers who may teach the given subject (Subject→Teacher lock).

    Registered before ``/{teacher_id}`` so the literal path wins over the
    UUID path param. Drives the schedule form's teacher dropdown. When
    ``batch_id`` is given, teachers with a secondary per-batch assignment for
    that (subject, batch) are included too.
    """
    return await teacher_service.list_teachers_for_subject(
        session, branch_id, subject_id, batch_id
    )


@router.get("/secondary-subjects", response_model=list[SecondarySubjectRow])
async def list_secondary_subjects(
    branch_id: uuid.UUID = Query(...),
    teacher_id: uuid.UUID | None = Query(None),
    batch_id: uuid.UUID | None = Query(None),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Secondary (per-batch) subject assignments, scoped by teacher or by batch.
    Literal path — before ``/{teacher_id}``."""
    if teacher_id is not None:
        return await teacher_service.list_secondary_for_teacher(
            session, branch_id, teacher_id
        )
    if batch_id is not None:
        return await teacher_service.list_secondary_for_batch(
            session, branch_id, batch_id
        )
    return []


@router.post("/{teacher_id}/secondary-subjects", response_model=list[SecondarySubjectRow])
async def assign_secondary_subjects(
    teacher_id: uuid.UUID,
    body: SecondarySubjectAssign,
    request: Request,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin"])),
    session: AsyncSession = Depends(get_db),
):
    """Assign a secondary subject to this teacher for the given batches. The
    teacher's core subject is untouched; the subject is auto-added to each
    batch's course if missing."""
    return await teacher_service.assign_secondary_subjects(
        session, branch_id, teacher_id, body.subject_name, body.batch_ids,
        current_user["user_id"], request.client.host if request.client else None,
    )


@router.delete("/secondary-subjects/{mapping_id}", status_code=204)
async def remove_secondary_subject(
    mapping_id: uuid.UUID,
    request: Request,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin"])),
    session: AsyncSession = Depends(get_db),
):
    """Remove one secondary assignment (teacher stops teaching that subject for
    that batch). Literal path — before ``/{teacher_id}``."""
    await teacher_service.remove_secondary_subject(
        session, branch_id, mapping_id, current_user["user_id"],
        request.client.host if request.client else None,
    )


@router.post("/bulk-delete", response_model=BulkDeleteSummary)
async def bulk_delete_teachers(
    body: BulkTeacherDelete,
    request: Request,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_manager_or_audit("Delete", "teachers")),
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


@router.get("/{teacher_id}/photo")
async def get_teacher_photo(
    teacher_id: uuid.UUID,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """The teacher's enrolled face photo (JPEG), resolved through the linked staff
    row's emp_code (the biometric device userId). Any signed-in user may view it
    (cookie auth, so an ``<img>`` works). 404 when the teacher has no linked staff
    or no enrolled face."""
    from fastapi import HTTPException, status

    from app.modules.attendance.services import provisioning_service
    from app.modules.staff.repositories import staff_repository

    emp_map = await staff_repository.emp_code_by_linked_teacher(
        session, branch_id, [teacher_id]
    )
    emp_code = emp_map.get(teacher_id)
    jpeg = (
        await provisioning_service.face_photo_by_uid(session, branch_id, emp_code)
        if emp_code
        else None
    )
    if jpeg is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No face photo.")
    return Response(
        content=jpeg,
        media_type="image/jpeg",
        headers={"Cache-Control": "private, max-age=300"},
    )


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
    current_user: dict = Depends(require_manager_or_audit("Delete", "teachers")),
    session: AsyncSession = Depends(get_db),
):
    await teacher_service.delete_teacher(
        session, teacher_id, branch_id, current_user["user_id"],
        request.client.host if request.client else None,
    )
