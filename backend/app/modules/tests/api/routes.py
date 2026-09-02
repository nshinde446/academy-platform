import mimetypes
import uuid

from fastapi import APIRouter, Depends, File, Query, Request, Response, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config.settings import get_settings
from app.core.database.session import get_db
from app.core.storage import StorageBackend, get_storage_backend
from app.modules.auth.permissions.rbac import get_current_user, require_roles
from app.modules.tests.schemas.test_schemas import (
    AnswerKeyInfo,
    AutoPickRequest,
    MarkBatchSubmit,
    MarkResponse,
    QuestionBulkAction,
    QuestionBulkResult,
    QuestionCreate,
    QuestionResponse,
    QuestionUpdate,
    RankListResponse,
    ResolveReviewRequest,
    ResolveReviewResult,
    ResponseBulkResult,
    ResponseBulkSubmit,
    TestCreate,
    TestQuestionsAdd,
    TestReportResponse,
    TestResponse,
    UploadResultSummary,
)
from app.modules.tests.services import ranklist_export, test_service

router = APIRouter(prefix="/questions", tags=["questions"])
tests_router = APIRouter(prefix="/tests", tags=["tests"])
marks_router = APIRouter(prefix="/marks", tags=["marks"])


# ─── Question Endpoints ───────────────────────────────────────────────────────

@router.post("", response_model=QuestionResponse)
async def create_question(
    body: QuestionCreate,
    request: Request,
    branch_id: uuid.UUID = Query(...),
    academic_year_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(["super_admin", "academic_head"])),
    session: AsyncSession = Depends(get_db),
):
    return await test_service.create_question(
        session, body.model_dump(), branch_id, academic_year_id,
        current_user["user_id"],
        request.client.host if request.client else None,
    )


@router.get("", response_model=list[QuestionResponse])
async def list_questions(
    branch_id: uuid.UUID = Query(...),
    subject_id: uuid.UUID | None = Query(None),
    topic_id: uuid.UUID | None = Query(None),
    difficulty: str | None = Query(None),
    blooms_taxonomy: str | None = Query(None),
    review_status: str | None = Query(None),
    source_prefix: str | None = Query(
        None,
        description="Filter by Question.source prefix (e.g. 'studymat:')",
    ),
    search: str | None = Query(None, description="ILIKE on question content"),
    material_id: uuid.UUID | None = Query(None),
    class_label: str | None = Query(None, description="Via the source material"),
    topic: str | None = Query(None, description="Via the source material"),
    exam_type: str | None = Query(None, description="e.g. neet, jee_main (Postgres)"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin", "academic_head", "teacher"])),
    session: AsyncSession = Depends(get_db),
):
    return await test_service.list_questions(
        session, branch_id,
        subject_id=subject_id,
        topic_id=topic_id,
        difficulty=difficulty,
        blooms_taxonomy=blooms_taxonomy,
        review_status=review_status,
        source_prefix=source_prefix,
        search=search,
        material_id=material_id,
        class_label=class_label,
        topic=topic,
        exam_type=exam_type,
        offset=offset,
        limit=limit,
    )


@router.get("/count")
async def count_questions(
    branch_id: uuid.UUID = Query(...),
    subject_id: uuid.UUID | None = Query(None),
    topic_id: uuid.UUID | None = Query(None),
    difficulty: str | None = Query(None),
    blooms_taxonomy: str | None = Query(None),
    review_status: str | None = Query(None),
    source_prefix: str | None = Query(None),
    search: str | None = Query(None),
    material_id: uuid.UUID | None = Query(None),
    class_label: str | None = Query(None),
    topic: str | None = Query(None),
    exam_type: str | None = Query(None),
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin", "academic_head", "teacher"])),
    session: AsyncSession = Depends(get_db),
):
    """Total matching questions — drives the tab counts on /question-bank."""
    n = await test_service.count_questions(
        session, branch_id,
        subject_id=subject_id,
        topic_id=topic_id,
        difficulty=difficulty,
        blooms_taxonomy=blooms_taxonomy,
        review_status=review_status,
        source_prefix=source_prefix,
        search=search,
        material_id=material_id,
        class_label=class_label,
        topic=topic,
        exam_type=exam_type,
    )
    return {"count": n}


@router.post("/bulk-approve", response_model=QuestionBulkResult)
async def bulk_approve_questions(
    body: QuestionBulkAction,
    request: Request,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(
        require_roles(["super_admin", "branch_admin", "academic_head"])
    ),
    session: AsyncSession = Depends(get_db),
):
    return await test_service.bulk_set_review_status(
        session, branch_id, body.question_ids, "approved",
        current_user["user_id"],
        request.client.host if request.client else None,
    )


@router.post("/bulk-reject", response_model=QuestionBulkResult)
async def bulk_reject_questions(
    body: QuestionBulkAction,
    request: Request,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(
        require_roles(["super_admin", "branch_admin", "academic_head"])
    ),
    session: AsyncSession = Depends(get_db),
):
    return await test_service.bulk_set_review_status(
        session, branch_id, body.question_ids, "rejected",
        current_user["user_id"],
        request.client.host if request.client else None,
    )


@router.get("/{question_id}", response_model=QuestionResponse)
async def get_question(
    question_id: uuid.UUID,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin", "academic_head", "teacher"])),
    session: AsyncSession = Depends(get_db),
):
    return await test_service.get_question(session, question_id, branch_id)


@router.patch("/{question_id}", response_model=QuestionResponse)
async def update_question(
    question_id: uuid.UUID,
    body: QuestionUpdate,
    request: Request,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(["super_admin", "academic_head"])),
    session: AsyncSession = Depends(get_db),
):
    return await test_service.update_question(
        session, question_id, body.model_dump(exclude_unset=True), branch_id,
        current_user["user_id"],
        request.client.host if request.client else None,
    )


@router.delete("/{question_id}", status_code=204)
async def delete_question(
    question_id: uuid.UUID,
    request: Request,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(["super_admin", "academic_head"])),
    session: AsyncSession = Depends(get_db),
):
    await test_service.delete_question(
        session, question_id, branch_id, current_user["user_id"],
        request.client.host if request.client else None,
    )


# ─── Test Endpoints ───────────────────────────────────────────────────────────

@tests_router.post("", response_model=TestResponse)
async def create_test(
    body: TestCreate,
    request: Request,
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin", "academic_head"])),
    session: AsyncSession = Depends(get_db),
):
    return await test_service.create_test(
        session, body.model_dump(), current_user["user_id"],
        request.client.host if request.client else None,
    )


@tests_router.post("/auto-pick", response_model=list[QuestionResponse])
async def auto_pick_questions(
    body: AutoPickRequest,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin", "academic_head", "teacher"])),
    session: AsyncSession = Depends(get_db),
):
    """Composer auto-pick — draw N questions from the bank by facets (M4).

    Preview-only: returns questions but creates nothing. The composer
    holds them client-side, lets the admin review/swap/remove, then saves
    via POST /tests + POST /tests/{id}/questions.
    """
    return await test_service.auto_pick_questions(session, branch_id, body)


@tests_router.get("", response_model=list[TestResponse])
async def list_tests(
    branch_id: uuid.UUID = Query(...),
    batch_id: uuid.UUID | None = Query(None),
    subject_id: uuid.UUID | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin", "academic_head", "teacher"])),
    session: AsyncSession = Depends(get_db),
):
    return await test_service.list_tests(session, branch_id, batch_id, subject_id, offset, limit)


@tests_router.get("/{test_id}", response_model=TestResponse)
async def get_test(
    test_id: uuid.UUID,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin", "academic_head", "teacher"])),
    session: AsyncSession = Depends(get_db),
):
    return await test_service.get_test(session, test_id, branch_id)


@tests_router.get("/{test_id}/questions", response_model=list[QuestionResponse])
async def get_test_questions(
    test_id: uuid.UUID,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin", "academic_head", "teacher"])),
    session: AsyncSession = Depends(get_db),
):
    """Full question payloads on a test (ordered) — composer draft review."""
    return await test_service.get_test_question_details(session, test_id, branch_id)


def _pdf_response(filename: str, data: bytes) -> Response:
    return Response(
        content=data,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


@tests_router.get("/{test_id}/paper.pdf")
async def download_paper_pdf(
    test_id: uuid.UUID,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin", "academic_head", "teacher"])),
    session: AsyncSession = Depends(get_db),
):
    """Branded student question paper as a PDF (Tier 14)."""
    filename, data = await test_service.generate_paper_pdf(session, test_id, branch_id)
    return _pdf_response(filename, data)


@tests_router.get("/{test_id}/answer-key.pdf")
async def download_answer_key_pdf(
    test_id: uuid.UUID,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin", "academic_head"])),
    session: AsyncSession = Depends(get_db),
):
    """Internal answer key PDF — narrower roles than the question paper."""
    filename, data = await test_service.generate_answer_key_pdf(session, test_id, branch_id)
    return _pdf_response(filename, data)


@tests_router.post("/{test_id}/questions")
async def add_questions_to_test(
    test_id: uuid.UUID,
    body: TestQuestionsAdd,
    request: Request,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin", "academic_head"])),
    session: AsyncSession = Depends(get_db),
):
    questions = [q.model_dump() for q in body.questions]
    await test_service.add_questions_to_test(
        session, test_id, questions, branch_id, current_user["user_id"],
        request.client.host if request.client else None,
    )
    return {"detail": "Questions added successfully"}


@tests_router.patch("/{test_id}/publish", response_model=TestResponse)
async def publish_test(
    test_id: uuid.UUID,
    request: Request,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin", "academic_head"])),
    session: AsyncSession = Depends(get_db),
):
    return await test_service.publish_test(
        session, test_id, branch_id, current_user["user_id"],
        request.client.host if request.client else None,
    )


@tests_router.delete("/{test_id}", status_code=204)
async def delete_test(
    test_id: uuid.UUID,
    request: Request,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(["super_admin", "academic_head"])),
    session: AsyncSession = Depends(get_db),
):
    """Soft-delete a paper/test draft from /papers."""
    await test_service.delete_test(
        session, test_id, branch_id, current_user["user_id"],
        request.client.host if request.client else None,
    )


@tests_router.get("/{test_id}/marks", response_model=list[MarkResponse])
async def get_test_marks(
    test_id: uuid.UUID,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin", "academic_head", "teacher"])),
    session: AsyncSession = Depends(get_db),
):
    return await test_service.get_test_marks(session, test_id, branch_id)


@tests_router.get("/{test_id}/report", response_model=TestReportResponse)
async def get_test_report(
    test_id: uuid.UUID,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin", "academic_head"])),
    session: AsyncSession = Depends(get_db),
):
    return await test_service.generate_report(session, test_id, branch_id)


@tests_router.post("/{test_id}/responses", response_model=ResponseBulkResult)
async def submit_responses(
    test_id: uuid.UUID,
    body: ResponseBulkSubmit,
    request: Request,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(
        require_roles(["super_admin", "branch_admin", "academic_head", "teacher"])
    ),
    session: AsyncSession = Depends(get_db),
):
    """Bulk-submit per-question student responses for a test (Tier 11).

    Auto-marks each response against the question's correct_answer and
    rolls up totals into the existing StudentMark aggregate. Idempotent
    on (student, test, question) — re-submissions overwrite.
    """
    return await test_service.submit_responses(
        session,
        test_id,
        body,
        branch_id,
        current_user["user_id"],
        request.client.host if request.client else None,
    )


# ─── Test Portal: ZipGrade CSV upload + rank list ─────────────────────────────

_PORTAL_ROLES = ["super_admin", "branch_admin", "academic_head"]


@tests_router.post("/{test_id}/upload-result", response_model=UploadResultSummary)
async def upload_result(
    test_id: uuid.UUID,
    request: Request,
    branch_id: uuid.UUID = Query(...),
    file: UploadFile = File(...),
    current_user: dict = Depends(require_roles(_PORTAL_ROLES)),
    session: AsyncSession = Depends(get_db),
):
    """Upload a ZipGrade results CSV → match PRNs, save marks, flag unmatched
    rows, mark absentees, and (re)build the rank list."""
    content = await file.read()
    return await test_service.upload_result(
        session, test_id, branch_id, content, current_user["user_id"],
        request.client.host if request.client else None,
    )


@tests_router.get("/{test_id}/ranklist", response_model=RankListResponse)
async def get_ranklist(
    test_id: uuid.UUID,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(_PORTAL_ROLES + ["teacher"])),
    session: AsyncSession = Depends(get_db),
):
    return await test_service.get_ranklist(session, test_id, branch_id)


@tests_router.get("/{test_id}/ranklist/download")
async def download_ranklist(
    test_id: uuid.UUID,
    branch_id: uuid.UUID = Query(...),
    format: str = Query("pdf", pattern="^(pdf|xlsx)$"),
    current_user: dict = Depends(require_roles(_PORTAL_ROLES + ["teacher"])),
    session: AsyncSession = Depends(get_db),
):
    ranklist = await test_service.get_ranklist(session, test_id, branch_id)
    brand = get_settings().ACADEMY_BRAND_NAME
    slug = "".join(c if c.isalnum() else "-" for c in ranklist["test_name"]).strip("-").lower() or "rank-list"
    if format == "xlsx":
        data = ranklist_export.ranklist_xlsx(brand=brand, ranklist=ranklist)
        return Response(
            content=data, media_type=ranklist_export.XLSX_MIME,
            headers={"Content-Disposition": f'attachment; filename="{slug}.xlsx"'},
        )
    data = await ranklist_export.ranklist_pdf(brand=brand, ranklist=ranklist)
    return Response(
        content=data, media_type=ranklist_export.PDF_MIME,
        headers={"Content-Disposition": f'attachment; filename="{slug}.pdf"'},
    )


@tests_router.post("/{test_id}/review/{review_id}/resolve", response_model=ResolveReviewResult)
async def resolve_review(
    test_id: uuid.UUID,
    review_id: uuid.UUID,
    body: ResolveReviewRequest,
    request: Request,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(_PORTAL_ROLES)),
    session: AsyncSession = Depends(get_db),
):
    """Assign an unmatched ZipGrade row to a student → write their mark and mark
    the row resolved. The rank list recomputes on the next read."""
    return await test_service.resolve_review(
        session, test_id, review_id, body.student_id, branch_id,
        current_user["user_id"],
        request.client.host if request.client else None,
    )


@tests_router.post("/{test_id}/answer-key", response_model=AnswerKeyInfo)
async def upload_answer_key(
    test_id: uuid.UUID,
    request: Request,
    branch_id: uuid.UUID = Query(...),
    file: UploadFile = File(...),
    current_user: dict = Depends(require_roles(_PORTAL_ROLES)),
    session: AsyncSession = Depends(get_db),
    storage: StorageBackend = Depends(get_storage_backend),
):
    """Store an answer-key file for reference (kept, not scored against)."""
    content = await file.read()
    return await test_service.set_answer_key(
        session, test_id, branch_id, file.filename or "answer-key", content, storage,
        current_user["user_id"],
        request.client.host if request.client else None,
    )


@tests_router.get("/{test_id}/answer-key")
async def download_answer_key(
    test_id: uuid.UUID,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(_PORTAL_ROLES + ["teacher"])),
    session: AsyncSession = Depends(get_db),
    storage: StorageBackend = Depends(get_storage_backend),
):
    """Download the stored answer-key file (404 if none set)."""
    filename, data = await test_service.get_answer_key(session, test_id, branch_id, storage)
    media_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    return Response(
        content=data, media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ─── Marks Endpoints ──────────────────────────────────────────────────────────

@marks_router.post("", response_model=list[MarkResponse])
async def submit_marks(
    body: MarkBatchSubmit,
    request: Request,
    test_id: uuid.UUID = Query(...),
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin", "academic_head", "teacher"])),
    session: AsyncSession = Depends(get_db),
):
    marks_list = [m.model_dump() for m in body.marks]
    return await test_service.submit_marks(
        session, test_id, marks_list, branch_id, current_user["user_id"],
        request.client.host if request.client else None,
    )


@marks_router.get("/student/{student_id}", response_model=list[MarkResponse])
async def get_student_marks(
    student_id: uuid.UUID,
    branch_id: uuid.UUID = Query(...),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    return await test_service.get_student_marks(session, student_id, branch_id, offset, limit)
