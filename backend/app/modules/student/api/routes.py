import uuid

import json

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.modules.auth.permissions.rbac import get_current_user, require_roles
from app.modules.student.models.student_models import StudentImportJob
from app.modules.student.schemas.student_schemas import (
    BulkActionSummary,
    BulkDeleteSummary,
    BulkStudentDelete,
    BulkStudentUpdate,
    ImportJobResponse,
    ImportRowsValidateRequest,
    ImportPreview,
    ImportSummary,
    ImportUndoSummary,
    StudentCreate,
    StudentResponse,
    StudentStatsPage,
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
    """Full branch roster with per-student analytics — used where the whole set
    is needed (attendance batch roster, a student's batch-rank context)."""
    return await student_service.list_students_with_stats(session, branch_id)


@router.get("/roster", response_model=StudentStatsPage)
async def list_students_roster(
    branch_id: uuid.UUID = Query(...),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    search: str = Query(""),
    sort_by: str = Query("name"),
    order: str = Query("asc", pattern="^(asc|desc)$"),
    standard: str | None = Query(None),
    target_exam: str | None = Query(None),
    fees_status: str | None = Query(None),
    batch_id: uuid.UUID | None = Query(None),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """One page of the roster — server-side paginated/searched/filtered/sorted so
    large branches stay fast. Powers the MSA_Design students table."""
    return await student_service.list_students_roster(
        session,
        branch_id,
        offset,
        limit,
        search,
        sort_by,
        order,
        standard=standard,
        target_exam=target_exam,
        fees_status=fees_status,
        batch_id=batch_id,
    )


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


@router.post("/bulk-update", response_model=BulkActionSummary)
async def bulk_update_students(
    body: BulkStudentUpdate,
    request: Request,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin"])),
    session: AsyncSession = Depends(get_db),
):
    """Apply one field change (fees/class/stream or batch reassignment) to a set
    of selected students from the roster."""
    return await student_service.bulk_update_students(
        session,
        branch_id,
        body.student_ids,
        fees_status=body.fees_status,
        standard=body.standard,
        stream=body.stream,
        batch_id=body.batch_id,
        current_user_id=current_user["user_id"],
        ip_address=request.client.host if request.client else None,
    )


@router.post("/bulk-delete", response_model=BulkDeleteSummary)
async def bulk_delete_students(
    body: BulkStudentDelete,
    request: Request,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin"])),
    session: AsyncSession = Depends(get_db),
):
    """Soft-delete a selected set of students from the roster."""
    return await student_service.bulk_delete_students(
        session,
        branch_id,
        body.student_ids,
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


def _parse_column_map(raw: str | None) -> dict[str, str] | None:
    """Parse the optional column-map form field (JSON: file-header → field-key).
    A bad payload is a client error, not a 500."""
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="column_map must be valid JSON",
        )
    if not isinstance(data, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="column_map must be a JSON object",
        )
    return {str(k): str(v) for k, v in data.items()}


@router.post("/import/columns")
async def detect_import_columns(
    file: UploadFile = File(...),
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin"])),
):
    """The upload's header columns, a suggested file-header → field mapping, and
    the catalog of fields they can be mapped to — drives the mapping step."""
    return await import_service.detect_columns(file)


@router.post("/import/parse")
async def parse_import_students(
    file: UploadFile = File(...),
    branch_id: uuid.UUID = Query(...),
    create_missing_batches: bool = Query(False),
    column_map: str | None = Form(None),
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin"])),
    session: AsyncSession = Depends(get_db),
):
    """Parse an upload into the editable validation grid (T4): the canonical
    fields present, one row per record (keyed by field), and per-row
    errors/warnings so the admin can fix cells inline before committing."""
    content = await file.read()
    fields, rows = import_service.parse_import_rows(
        file.filename, content, _parse_column_map(column_map)
    )
    validation = await import_service.validate_import_rows(
        session,
        branch_id,
        [r["values"] for r in rows],
        create_missing_batches,
    )
    return {
        "fields": fields,
        "import_fields": import_service.IMPORT_FIELDS,
        "rows": rows,
        "validation": validation,
    }


@router.post("/import/validate")
async def validate_import_students(
    body: ImportRowsValidateRequest,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin"])),
    session: AsyncSession = Depends(get_db),
):
    """Re-validate edited grid rows (no writes) — powers live cell validation."""
    validation = await import_service.validate_import_rows(
        session, branch_id, body.rows, body.create_missing_batches
    )
    return {"validation": validation}


@router.post("/import/preview", response_model=ImportPreview)
async def preview_import_students(
    file: UploadFile = File(...),
    branch_id: uuid.UUID = Query(...),
    column_map: str | None = Form(None),
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin"])),
    session: AsyncSession = Depends(get_db),
):
    """Dry-run a student upload — report row issues and which Batch codes
    exist vs. are missing, so the admin can choose to create the missing
    ones before committing the import."""
    return await import_service.preview_import(
        session, file, branch_id, _parse_column_map(column_map)
    )


@router.post("/import", response_model=ImportSummary)
async def import_students(
    request: Request,
    file: UploadFile = File(...),
    branch_id: uuid.UUID = Query(...),
    create_missing_batches: bool = Query(False),
    column_map: str | None = Form(None),
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin"])),
    session: AsyncSession = Depends(get_db),
):
    """Bulk import students. Class, Target Exam, and Batch are read
    per-row from the file so one CSV/Excel can mix cohorts. When
    ``create_missing_batches`` is set, batch codes that don't exist yet are
    created (course/exam-date derived from the Target column).

    Synchronous engine — fine for small files / API use. The portal uses
    ``/import/start`` (background job + progress) for large uploads."""
    content = await file.read()
    return await import_service.import_students(
        session,
        content,
        file.filename,
        branch_id,
        current_user["user_id"],
        create_missing_batches=create_missing_batches,
        ip_address=request.client.host if request.client else None,
        column_map=_parse_column_map(column_map),
    )


def _job_to_response(job: StudentImportJob) -> ImportJobResponse:
    resp = ImportJobResponse.model_validate(job)
    # The job id is the import_id; only hand back an undo handle once it has
    # finished and actually persisted students.
    resp.import_id = (
        job.id if job.job_status == "completed" and job.imported > 0 else None
    )
    return resp


@router.post("/import/start", response_model=ImportJobResponse)
async def start_import_students(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    branch_id: uuid.UUID = Query(...),
    create_missing_batches: bool = Query(False),
    column_map: str | None = Form(None),
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin"])),
    session: AsyncSession = Depends(get_db),
):
    """Start a background import: record a job (with row count) and return it
    immediately, then process the file after the response. The UI polls
    ``/import/jobs/{id}`` for progress and the final result — no request
    timeout regardless of file size."""
    content = await file.read()
    ip = request.client.host if request.client else None
    parsed_map = _parse_column_map(column_map)
    job = await import_service.start_import_job(
        session,
        content,
        file.filename,
        branch_id,
        current_user["user_id"],
        create_missing_batches,
    )
    background_tasks.add_task(
        import_service.run_import_job,
        job.id,
        content,
        file.filename,
        branch_id,
        current_user["user_id"],
        create_missing_batches,
        ip,
        parsed_map,
    )
    return _job_to_response(job)


@router.get("/import/jobs/{job_id}", response_model=ImportJobResponse)
async def get_import_job(
    job_id: uuid.UUID,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin"])),
    session: AsyncSession = Depends(get_db),
):
    """Poll a background import job's progress + result."""
    job = await session.get(StudentImportJob, job_id)
    if job is None or job.branch_id != branch_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Import job not found"
        )
    return _job_to_response(job)


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
