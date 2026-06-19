import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.modules.auth.permissions.rbac import get_current_user, require_roles
from app.modules.student.schemas.student_schemas import (
    BulkDeleteSummary,
    ImportPreview,
    ImportSummary,
    ImportUndoSummary,
    StudentCreate,
    StudentResponse,
    StudentSyllabus,
    StudentTestHistoryRow,
    StudentTopicMastery,
    StudentUpcomingTest,
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


@router.get(
    "/{student_id}/test-history",
    response_model=list[StudentTestHistoryRow],
)
async def get_student_test_history(
    student_id: uuid.UUID,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Per-student dashboard data: one row per test taken, with subject,
    topics, marks, batch rank, and institute rank."""
    return await student_service.get_test_history(session, student_id, branch_id)


@router.get(
    "/{student_id}/topic-mastery",
    response_model=list[StudentTopicMastery],
)
async def get_student_topic_mastery(
    student_id: uuid.UUID,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Per-topic accuracy (weakest first) from the student's per-question
    responses — the Tier 13 weakness map."""
    return await student_service.get_topic_mastery(session, student_id, branch_id)


@router.get(
    "/{student_id}/upcoming-tests",
    response_model=list[StudentUpcomingTest],
)
async def get_student_upcoming_tests(
    student_id: uuid.UUID,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Future-scheduled tests for the student's batch they haven't taken yet
    (soonest first) — the Tier 13 'upcoming tests' section."""
    return await student_service.get_upcoming_tests(session, student_id, branch_id)


@router.post("/delete-all", response_model=BulkDeleteSummary)
async def delete_all_students(
    request: Request,
    branch_id: uuid.UUID = Query(...),
    confirm: bool = Query(False),
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin"])),
    session: AsyncSession = Depends(get_db),
):
    """Soft-delete every student in the branch (keeps batches/courses/curriculum)
    so a stream-enhanced file can be re-imported cleanly. Requires confirm=true."""
    if not confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Pass confirm=true to delete all students.",
        )
    return await student_service.delete_all_students(
        session,
        branch_id,
        current_user["user_id"],
        request.client.host if request.client else None,
    )


@router.get("/{student_id}/syllabus", response_model=StudentSyllabus)
async def get_student_syllabus(
    student_id: uuid.UUID,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """The subjects this student is accountable for — their course's subjects
    filtered to their stream (Physics/Chemistry always; Maths for PCM; Biology
    for PCB) — with how much curriculum is loaded for each."""
    return await student_service.get_student_syllabus(session, student_id, branch_id)


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


@router.post("/import/preview", response_model=ImportPreview)
async def preview_import_students(
    file: UploadFile = File(...),
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin"])),
    session: AsyncSession = Depends(get_db),
):
    """Dry-run a student upload — report row issues and which Batch codes
    exist vs. are missing, so the admin can choose to create the missing
    ones before committing the import."""
    return await import_service.preview_import(session, file, branch_id)


@router.post("/import", response_model=ImportSummary)
async def import_students(
    request: Request,
    file: UploadFile = File(...),
    branch_id: uuid.UUID = Query(...),
    create_missing_batches: bool = Query(False),
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin"])),
    session: AsyncSession = Depends(get_db),
):
    """Bulk import students. Class, Target Exam, and Batch are read
    per-row from the file so one CSV/Excel can mix cohorts. When
    ``create_missing_batches`` is set, batch codes that don't exist yet are
    created (course/exam-date derived from the Target column)."""
    return await import_service.import_students(
        session,
        file,
        branch_id,
        current_user["user_id"],
        create_missing_batches=create_missing_batches,
        ip_address=request.client.host if request.client else None,
    )


@router.post("/import/{import_id}/undo", response_model=ImportUndoSummary)
async def undo_import_students(
    import_id: uuid.UUID,
    request: Request,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin"])),
    session: AsyncSession = Depends(get_db),
):
    """Reverse a bulk import as a unit: soft-delete the students it created
    (and their batch mappings) and reclaim any batches it auto-created that
    have no other students. Idempotent."""
    return await import_service.undo_import(
        session,
        import_id,
        branch_id,
        current_user["user_id"],
        ip_address=request.client.host if request.client else None,
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
