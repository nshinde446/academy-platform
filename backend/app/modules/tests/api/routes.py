import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.modules.auth.permissions.rbac import get_current_user, require_roles
from app.modules.tests.schemas.test_schemas import (
    MarkBatchSubmit,
    MarkResponse,
    QuestionBulkAction,
    QuestionBulkResult,
    QuestionCreate,
    QuestionResponse,
    QuestionUpdate,
    ResponseBulkResult,
    ResponseBulkSubmit,
    TestCreate,
    TestQuestionsAdd,
    TestReportResponse,
    TestResponse,
)
from app.modules.tests.services import test_service

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
