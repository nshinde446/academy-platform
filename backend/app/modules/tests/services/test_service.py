import json
import uuid
from collections import defaultdict
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.storage import StorageBackend, safe_filename
from app.modules.audit.services import audit_service
from app.modules.batch.repositories import batch_repository
from app.modules.events.services import event_service
from app.modules.student.models.student_models import Student, StudentBatchMapping
from app.modules.academic.models.academic_models import Course, Subject
from app.modules.tests.models.test_models import (
    StudentMark,
    TestBatch,
    TestImportReview,
    TestSubject,
    TestSubjectMark,
)
from app.modules.tests.repositories import test_repository
from app.modules.tests.services import zipgrade_csv

VALID_DIFFICULTIES = {"EASY", "MEDIUM", "HARD"}
VALID_BLOOMS = {"REMEMBER", "UNDERSTAND", "APPLY", "ANALYZE", "EVALUATE", "CREATE"}
VALID_TEST_STATUSES = {"DRAFT", "SCHEDULED", "ACTIVE", "COMPLETED", "CANCELLED"}
VALID_PAPER_TYPES = {"DPP", "CPP", "TEST"}
VALID_QUESTION_TYPES = {"MCQ_ONLY", "MCQ_NUMERICAL", "NA"}
# Bound a single auto-pick so a runaway request can't scan the whole bank.
MAX_AUTO_PICK = 200
PASS_PERCENTAGE = 33.0


def _calculate_grade(percentage: float) -> str:
    if percentage >= 90:
        return "A+"
    elif percentage >= 80:
        return "A"
    elif percentage >= 70:
        return "B"
    elif percentage >= 60:
        return "C"
    elif percentage >= 50:
        return "D"
    elif percentage >= PASS_PERCENTAGE:
        return "E"
    return "F"


# ─── Question Service ─────────────────────────────────────────────────────────

async def create_question(
    session: AsyncSession,
    data: dict,
    branch_id: uuid.UUID,
    academic_year_id: uuid.UUID,
    current_user_id: uuid.UUID,
    ip_address: str | None = None,
):
    if data.get("difficulty") and data["difficulty"] not in VALID_DIFFICULTIES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid difficulty: {data['difficulty']}",
        )
    if data.get("blooms_taxonomy") and data["blooms_taxonomy"] not in VALID_BLOOMS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid blooms_taxonomy: {data['blooms_taxonomy']}",
        )

    options_str = json.dumps(data["options"]) if data.get("options") else None
    tags_str = json.dumps(data["concept_tags"]) if data.get("concept_tags") else None

    question = await test_repository.create_question(
        session,
        content=data["content"],
        options=options_str,
        correct_answer=data["correct_answer"],
        explanation=data.get("explanation"),
        subject_id=data["subject_id"],
        topic_id=data.get("topic_id"),
        difficulty=data.get("difficulty", "MEDIUM"),
        blooms_taxonomy=data.get("blooms_taxonomy", "REMEMBER"),
        concept_tags=tags_str,
        branch_id=branch_id,
        academic_year_id=academic_year_id,
    )

    await audit_service.log_action(
        session,
        user_id=current_user_id,
        action="CREATE",
        table_name="questions",
        record_id=question.id,
        new_values={"content": data["content"][:100]},
        ip_address=ip_address,
        branch_id=branch_id,
    )
    return _format_question(question)


async def get_question(session: AsyncSession, question_id: uuid.UUID, branch_id: uuid.UUID):
    question = await test_repository.get_question_by_id(session, question_id)
    if not question:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")
    if question.branch_id != branch_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this branch")
    return _format_question(question)


VALID_REVIEW_STATUSES = {"pending_review", "approved", "rejected"}


async def list_questions(
    session: AsyncSession,
    branch_id: uuid.UUID,
    subject_id: uuid.UUID | None = None,
    topic_id: uuid.UUID | None = None,
    difficulty: str | None = None,
    blooms_taxonomy: str | None = None,
    review_status: str | None = None,
    source_prefix: str | None = None,
    search: str | None = None,
    material_id: uuid.UUID | None = None,
    class_label: str | None = None,
    topic: str | None = None,
    exam_type: str | None = None,
    offset: int = 0,
    limit: int = 50,
):
    questions = await test_repository.list_questions(
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
    return [_format_question(q) for q in questions]


async def count_questions(
    session: AsyncSession,
    branch_id: uuid.UUID,
    **filters,
) -> int:
    return await test_repository.count_questions(session, branch_id, **filters)


async def bulk_set_review_status(
    session: AsyncSession,
    branch_id: uuid.UUID,
    question_ids: list[uuid.UUID],
    new_status: str,
    current_user_id: uuid.UUID,
    ip_address: str | None = None,
) -> dict:
    if new_status not in VALID_REVIEW_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid review_status '{new_status}'. Allowed: {sorted(VALID_REVIEW_STATUSES)}",
        )
    updated, skipped = await test_repository.bulk_update_review_status(
        session, branch_id, question_ids, new_status
    )
    await audit_service.log_action(
        session,
        user_id=current_user_id,
        action="BULK_UPDATE",
        table_name="questions",
        record_id=uuid.uuid4(),
        new_values={
            "review_status": new_status,
            "updated_count": updated,
            "skipped_count": len(skipped),
        },
        ip_address=ip_address,
        branch_id=branch_id,
    )
    return {"updated": updated, "skipped": skipped}


async def update_question(
    session: AsyncSession,
    question_id: uuid.UUID,
    data: dict,
    branch_id: uuid.UUID,
    current_user_id: uuid.UUID,
    ip_address: str | None = None,
):
    question = await test_repository.get_question_by_id(session, question_id)
    if not question:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")
    if question.branch_id != branch_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this branch")

    update_kwargs = {}
    if "content" in data and data["content"] is not None:
        update_kwargs["content"] = data["content"]
    if "correct_answer" in data and data["correct_answer"] is not None:
        update_kwargs["correct_answer"] = data["correct_answer"]
    if "explanation" in data:
        update_kwargs["explanation"] = data["explanation"]
    if "topic_id" in data:
        update_kwargs["topic_id"] = data["topic_id"]
    if "difficulty" in data and data["difficulty"] is not None:
        if data["difficulty"] not in VALID_DIFFICULTIES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid difficulty: {data['difficulty']}",
            )
        update_kwargs["difficulty"] = data["difficulty"]
    if "blooms_taxonomy" in data and data["blooms_taxonomy"] is not None:
        if data["blooms_taxonomy"] not in VALID_BLOOMS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid blooms_taxonomy: {data['blooms_taxonomy']}",
            )
        update_kwargs["blooms_taxonomy"] = data["blooms_taxonomy"]
    if "options" in data:
        update_kwargs["options"] = json.dumps(data["options"]) if data["options"] else None
    if "concept_tags" in data:
        update_kwargs["concept_tags"] = json.dumps(data["concept_tags"]) if data["concept_tags"] else None
    if "subject_id" in data and data["subject_id"] is not None:
        update_kwargs["subject_id"] = data["subject_id"]
    if "review_status" in data and data["review_status"] is not None:
        if data["review_status"] not in VALID_REVIEW_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid review_status: {data['review_status']}",
            )
        update_kwargs["review_status"] = data["review_status"]

    question = await test_repository.update_question(session, question, **update_kwargs)

    await audit_service.log_action(
        session,
        user_id=current_user_id,
        action="UPDATE",
        table_name="questions",
        record_id=question.id,
        new_values=update_kwargs,
        ip_address=ip_address,
        branch_id=branch_id,
    )
    return _format_question(question)


async def delete_question(
    session: AsyncSession,
    question_id: uuid.UUID,
    branch_id: uuid.UUID,
    current_user_id: uuid.UUID,
    ip_address: str | None = None,
):
    question = await test_repository.get_question_by_id(session, question_id)
    if not question:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")
    if question.branch_id != branch_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this branch")

    await test_repository.soft_delete_question(session, question)

    await audit_service.log_action(
        session,
        user_id=current_user_id,
        action="DELETE",
        table_name="questions",
        record_id=question.id,
        old_values={"content": question.content[:100]},
        ip_address=ip_address,
        branch_id=branch_id,
    )


def _format_question(question):
    # concept_tags is stored as JSON text. Tolerate both JSON-encoded
    # lists and plain comma-separated strings (older inserts). Drop any
    # null/empty entries — material ingest can write [null, "12"] when a
    # material has no topic, and QuestionResponse.concept_tags is
    # list[str], which would reject the null and 500 the whole list.
    tags = None
    if question.concept_tags:
        try:
            parsed = json.loads(question.concept_tags)
            if isinstance(parsed, list):
                tags = [str(t) for t in parsed if t]
            else:
                tags = None
        except (ValueError, TypeError):
            tags = [t.strip() for t in question.concept_tags.split(",") if t.strip()]
    return {
        "id": question.id,
        "content": question.content,
        "options": json.loads(question.options) if question.options else None,
        "correct_answer": question.correct_answer,
        "explanation": question.explanation,
        "subject_id": question.subject_id,
        "topic_id": question.topic_id,
        "difficulty": question.difficulty,
        "blooms_taxonomy": question.blooms_taxonomy,
        "concept_tags": tags,
        "source": question.source,
        "source_ref": question.source_ref,
        "diagram_ref": question.diagram_ref,
        "review_status": question.review_status,
        "quality_score": question.quality_score,
        "branch_id": question.branch_id,
        "academic_year_id": question.academic_year_id,
        "status": question.status,
    }


# ─── Test Service ─────────────────────────────────────────────────────────────

async def _resolve_batches(session: AsyncSession, data: dict) -> list:
    """The test's batches. Accepts `batch_ids` (multi, Test Portal) or the legacy
    single `batch_id` (composer / OMR); the first is the primary. 404 if any is
    unknown, 422 if none given."""
    batch_ids = data.get("batch_ids") or (
        [data["batch_id"]] if data.get("batch_id") else []
    )
    batch_ids = list(dict.fromkeys(batch_ids))  # de-dup, keep order
    if not batch_ids:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one batch is required",
        )
    batches = []
    for bid in batch_ids:
        batch = await batch_repository.get_by_id(session, bid)
        if not batch:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Batch not found: {bid}"
            )
        batches.append(batch)
    return batches


async def _any_jee_batch(session: AsyncSession, batches: list) -> bool:
    """Whether any selected batch is a JEE batch — identified from the batch name
    or its course code/name (there is no explicit exam-type field). Drives whether
    Question Type (MCQ / MCQ+Numerical) is allowed on the test."""
    course_ids = {b.course_id for b in batches}
    courses: dict = {}
    if course_ids:
        for c in (await session.execute(
            select(Course).where(Course.id.in_(course_ids))
        )).scalars():
            courses[c.id] = c
    for b in batches:
        c = courses.get(b.course_id)
        haystack = " ".join(
            x for x in (b.name, getattr(c, "name", None), getattr(c, "code", None)) if x
        ).lower()
        if "jee" in haystack:
            return True
    return False


async def create_test(
    session: AsyncSession,
    data: dict,
    current_user_id: uuid.UUID,
    ip_address: str | None = None,
):
    paper_type = data.get("paper_type", "TEST")
    if paper_type not in VALID_PAPER_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid paper_type '{paper_type}'. Allowed: {sorted(VALID_PAPER_TYPES)}",
        )

    batches = await _resolve_batches(session, data)
    primary = batches[0]

    # Question Type (JEE only). A non-NA value is rejected unless a JEE batch is
    # selected, mirroring the form hiding the control for CET/NEET batches.
    question_type = (data.get("question_type") or "NA").upper()
    if question_type not in VALID_QUESTION_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid question_type '{question_type}'. Allowed: {sorted(VALID_QUESTION_TYPES)}",
        )
    if question_type != "NA" and not await _any_jee_batch(session, batches):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Question Type applies only to JEE batches.",
        )

    # Subjects: `subjects` ({subject_id, total_marks} — per-subject flow),
    # `subject_ids` (multi, no per-subject marks), or legacy single `subject_id`.
    # The primary subject_id is the first, kept for the composer / ranking / history.
    if data.get("subjects"):
        subject_pairs = [(s["subject_id"], s.get("total_marks")) for s in data["subjects"]]
    else:
        subject_ids = data.get("subject_ids") or (
            [data["subject_id"]] if data.get("subject_id") else []
        )
        subject_pairs = [(sid, None) for sid in subject_ids]
    # De-duplicate by subject_id while preserving order (first marks value wins).
    seen: set = set()
    subject_pairs = [
        (sid, marks) for sid, marks in subject_pairs
        if not (sid in seen or seen.add(sid))
    ]
    if not subject_pairs:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one subject is required",
        )

    test = await test_repository.create_test(
        session,
        name=data["name"],
        description=data.get("description"),
        paper_type=paper_type,
        batch_id=primary.id,
        subject_id=subject_pairs[0][0],
        scheduled_at=data.get("scheduled_at"),
        duration_minutes=data.get("duration_minutes", 60),
        total_marks=data.get("total_marks", 100.0),
        question_type=question_type,
        omr_type=data.get("omr_type"),
        test_status="DRAFT",
        branch_id=primary.branch_id,
        academic_year_id=primary.start_academic_year_id,
        source_lecture_id=data.get("source_lecture_id"),
    )
    for sid, marks in subject_pairs:
        session.add(TestSubject(
            test_id=test.id, subject_id=sid, branch_id=primary.branch_id,
            total_marks=marks,
        ))
    for batch in batches:
        session.add(TestBatch(
            test_id=test.id, batch_id=batch.id, branch_id=primary.branch_id,
        ))
    await session.flush()

    # Transient attributes so the create response echoes what was scheduled.
    test.subject_ids = [sid for sid, _ in subject_pairs]
    test.batch_ids = [b.id for b in batches]

    await audit_service.log_action(
        session,
        user_id=current_user_id,
        action="CREATE",
        table_name="tests",
        record_id=test.id,
        new_values={"name": data["name"]},
        ip_address=ip_address,
        branch_id=primary.branch_id,
    )
    return test


async def get_test(session: AsyncSession, test_id: uuid.UUID, branch_id: uuid.UUID):
    test = await test_repository.get_test_by_id(session, test_id)
    if not test:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")
    if test.branch_id != branch_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this branch")
    return test


async def list_tests(
    session: AsyncSession,
    branch_id: uuid.UUID,
    batch_id: uuid.UUID | None = None,
    subject_id: uuid.UUID | None = None,
    offset: int = 0,
    limit: int = 50,
):
    return await test_repository.list_tests(
        session, branch_id, batch_id, subject_id, offset, limit
    )


async def add_questions_to_test(
    session: AsyncSession,
    test_id: uuid.UUID,
    questions: list[dict],
    branch_id: uuid.UUID,
    current_user_id: uuid.UUID,
    ip_address: str | None = None,
):
    test = await test_repository.get_test_by_id(session, test_id)
    if not test:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")
    if test.branch_id != branch_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this branch")

    result = await test_repository.add_questions_to_test(session, test_id, questions)

    await audit_service.log_action(
        session,
        user_id=current_user_id,
        action="UPDATE",
        table_name="test_questions",
        record_id=test_id,
        new_values={"questions_added": len(questions)},
        ip_address=ip_address,
        branch_id=branch_id,
    )
    return result


async def get_test_question_details(
    session: AsyncSession, test_id: uuid.UUID, branch_id: uuid.UUID
):
    """Full question payloads for a test, ordered — composer preview."""
    test = await test_repository.get_test_by_id(session, test_id)
    if not test:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")
    if test.branch_id != branch_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this branch")
    questions = await test_repository.get_test_question_details(session, test_id)
    return [_format_question(q) for q in questions]


async def _paper_pdf(session, test_id, branch_id, builder_name: str) -> tuple[str, bytes]:
    """Shared fetch+render for the two paper PDFs. Returns (filename, bytes).

    Layout runs in a headless Chromium via Playwright so output matches
    the Question Bank preview pane (same KaTeX render). The browser
    builders are async, so no asyncio.to_thread shim needed."""
    from types import SimpleNamespace

    from app.core.config.settings import get_settings
    from app.modules.tests.services import pdf_browser_service as svc

    test = await get_test(session, test_id, branch_id)  # validates branch
    questions = await get_test_question_details(session, test_id, branch_id)
    if not questions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This paper has no questions yet",
        )
    meta = SimpleNamespace(
        name=test.name,
        paper_type=test.paper_type,
        total_marks=test.total_marks,
    )
    brand = get_settings().ACADEMY_BRAND_NAME
    builder = getattr(svc, builder_name)
    data = await builder(meta, questions, brand)

    slug = "".join(c if c.isalnum() else "-" for c in test.name).strip("-") or "paper"
    suffix = "answer-key" if "answer" in builder_name else "paper"
    return f"{slug}-{suffix}.pdf", data


async def generate_paper_pdf(session, test_id: uuid.UUID, branch_id: uuid.UUID):
    return await _paper_pdf(session, test_id, branch_id, "build_question_paper_pdf")


async def generate_answer_key_pdf(session, test_id: uuid.UUID, branch_id: uuid.UUID):
    return await _paper_pdf(session, test_id, branch_id, "build_answer_key_pdf")


async def auto_pick_questions(
    session: AsyncSession,
    branch_id: uuid.UUID,
    payload,  # AutoPickRequest
) -> list[dict]:
    """Draw questions from the bank by facets for the composer (M4).

    Honours `difficulty_mix` (one randomized draw per difficulty) or a
    flat `count` (any difficulty). De-dupes across the per-difficulty
    draws and excludes `exclude_ids` so reshuffle / swap never re-surface
    a question already on the paper.
    """
    picked: list = []
    seen: set[uuid.UUID] = set(payload.exclude_ids or [])

    facets = dict(
        subject_id=payload.subject_id,
        class_label=payload.class_label,
        topic=payload.topic,
        exam_type=payload.exam_type,
        review_status=payload.review_status,
    )

    if payload.difficulty_mix:
        for diff, n in payload.difficulty_mix.items():
            if n <= 0:
                continue
            if diff not in VALID_DIFFICULTIES:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Invalid difficulty '{diff}' in difficulty_mix",
                )
            rows = await test_repository.pick_random_questions(
                session, branch_id,
                count=min(n, MAX_AUTO_PICK),
                difficulty=diff,
                exclude_ids=list(seen),
                **facets,
            )
            for q in rows:
                if q.id not in seen:
                    seen.add(q.id)
                    picked.append(q)
    else:
        count = payload.count if payload.count is not None else 10
        if count <= 0:
            return []
        rows = await test_repository.pick_random_questions(
            session, branch_id,
            count=min(count, MAX_AUTO_PICK),
            difficulty=None,
            exclude_ids=list(seen),
            **facets,
        )
        for q in rows:
            if q.id not in seen:
                seen.add(q.id)
                picked.append(q)

    return [_format_question(q) for q in picked]


async def delete_test(
    session: AsyncSession,
    test_id: uuid.UUID,
    branch_id: uuid.UUID,
    current_user_id: uuid.UUID,
    ip_address: str | None = None,
) -> None:
    """Soft-delete a paper/test (the draft disappears from /papers list).

    Row stays in the DB so an accidental delete can be reversed by
    flipping is_deleted; associated test_questions stay too so a
    restored test still has its questions."""
    test = await test_repository.get_test_by_id(session, test_id)
    if not test:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")
    if test.branch_id != branch_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this branch")

    old_name = test.name
    await test_repository.soft_delete_test(session, test)

    await audit_service.log_action(
        session,
        user_id=current_user_id,
        action="DELETE",
        table_name="tests",
        record_id=test.id,
        old_values={"name": old_name, "paper_type": test.paper_type},
        ip_address=ip_address,
        branch_id=branch_id,
    )


async def publish_test(
    session: AsyncSession,
    test_id: uuid.UUID,
    branch_id: uuid.UUID,
    current_user_id: uuid.UUID,
    ip_address: str | None = None,
):
    test = await test_repository.get_test_by_id(session, test_id)
    if not test:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")
    if test.branch_id != branch_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this branch")
    if test.test_status not in ("DRAFT", "SCHEDULED"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Cannot publish test in status '{test.test_status}'",
        )

    old_status = test.test_status
    test = await test_repository.update_test(session, test, test_status="ACTIVE")

    await audit_service.log_action(
        session,
        user_id=current_user_id,
        action="UPDATE",
        table_name="tests",
        record_id=test.id,
        old_values={"test_status": old_status},
        new_values={"test_status": "ACTIVE"},
        ip_address=ip_address,
        branch_id=branch_id,
    )

    await event_service.emit_event(
        session,
        event_type="TEST_UPLOADED",
        test_id=test.id,
        batch_id=test.batch_id,
        subject_id=test.subject_id,
        branch_id=branch_id,
        metadata={"test_name": test.name, "test_status": "ACTIVE"},
    )
    return test


# ─── Marks Service ────────────────────────────────────────────────────────────

async def submit_marks(
    session: AsyncSession,
    test_id: uuid.UUID,
    marks_list: list[dict],
    branch_id: uuid.UUID,
    current_user_id: uuid.UUID,
    ip_address: str | None = None,
):
    test = await test_repository.get_test_by_id(session, test_id)
    if not test:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")
    if test.branch_id != branch_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this branch")

    now = datetime.now(timezone.utc)
    results = []

    for entry in marks_list:
        student_id = entry["student_id"]
        marks_obtained = entry.get("marks_obtained", 0.0)
        is_absent = entry.get("is_absent", False)

        if is_absent:
            percentage = 0.0
            grade = None
        else:
            percentage = (marks_obtained / test.total_marks * 100) if test.total_marks > 0 else 0.0
            grade = _calculate_grade(percentage)

        existing = await test_repository.get_student_mark(session, student_id, test_id)
        if existing:
            old_marks = existing.marks_obtained
            mark = await test_repository.update_student_mark(
                session, existing,
                marks_obtained=marks_obtained,
                max_marks=test.total_marks,
                percentage=percentage,
                grade=grade,
                is_absent=is_absent,
                marked_at=now,
                marked_by=current_user_id,
            )
            await audit_service.log_action(
                session,
                user_id=current_user_id,
                action="UPDATE",
                table_name="student_marks",
                record_id=mark.id,
                old_values={"marks_obtained": old_marks},
                new_values={"marks_obtained": marks_obtained},
                ip_address=ip_address,
                branch_id=branch_id,
            )
        else:
            mark = await test_repository.create_student_mark(
                session,
                student_id=student_id,
                test_id=test_id,
                marks_obtained=marks_obtained,
                max_marks=test.total_marks,
                percentage=percentage,
                grade=grade,
                is_absent=is_absent,
                marked_at=now,
                marked_by=current_user_id,
                branch_id=branch_id,
                academic_year_id=test.academic_year_id,
            )
            await audit_service.log_action(
                session,
                user_id=current_user_id,
                action="CREATE",
                table_name="student_marks",
                record_id=mark.id,
                new_values={"student_id": str(student_id), "marks_obtained": marks_obtained},
                ip_address=ip_address,
                branch_id=branch_id,
            )
        results.append(mark)

    await event_service.emit_event(
        session,
        event_type="MARKS_UPDATED",
        test_id=test_id,
        batch_id=test.batch_id,
        subject_id=test.subject_id,
        branch_id=branch_id,
        metadata={"marks_count": len(results)},
    )
    return results


async def get_test_marks(session: AsyncSession, test_id: uuid.UUID, branch_id: uuid.UUID):
    test = await test_repository.get_test_by_id(session, test_id)
    if not test:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")
    if test.branch_id != branch_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this branch")
    return await test_repository.get_marks_by_test(session, test_id)


async def get_student_marks(
    session: AsyncSession, student_id: uuid.UUID, branch_id: uuid.UUID,
    offset: int = 0, limit: int = 50,
):
    return await test_repository.get_marks_by_student(session, student_id, branch_id, offset, limit)


async def generate_report(session: AsyncSession, test_id: uuid.UUID, branch_id: uuid.UUID):
    test = await test_repository.get_test_by_id(session, test_id)
    if not test:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")
    if test.branch_id != branch_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this branch")

    stats = await test_repository.get_test_statistics(session, test_id)
    absent_count = await test_repository.count_absent(session, test_id)

    all_marks = await test_repository.get_marks_by_test(session, test_id)
    pass_count = sum(1 for m in all_marks if not m.is_absent and m.percentage >= PASS_PERCENTAGE)
    fail_count = sum(1 for m in all_marks if not m.is_absent and m.percentage < PASS_PERCENTAGE)

    return {
        "test_id": test_id,
        "total_students": stats["appeared"] + absent_count,
        "appeared": stats["appeared"],
        "absent": absent_count,
        "average": round(stats["average"], 2),
        "highest": stats["highest"],
        "lowest": stats["lowest"],
        "pass_count": pass_count,
        "fail_count": fail_count,
    }


# ─── Test Portal: ZipGrade CSV upload + rank list ────────────────────────────


async def _batch_roster(session: AsyncSession, batch_id: uuid.UUID) -> list:
    """Active students enrolled in the batch: (id, first, last, enrollment)."""
    return list((await session.execute(
        select(
            Student.id, Student.first_name, Student.last_name,
            Student.enrollment_number,
        )
        .join(StudentBatchMapping, StudentBatchMapping.student_id == Student.id)
        .where(
            StudentBatchMapping.batch_id == batch_id,
            StudentBatchMapping.is_deleted == False,
            Student.is_deleted == False,
        )
        .distinct()
    )).all())


async def _upsert_mark(
    session: AsyncSession,
    *,
    test,
    branch_id: uuid.UUID,
    student_id: uuid.UUID,
    marks: float,
    is_absent: bool,
    raw: dict | None,
    current_user_id: uuid.UUID,
    now: datetime,
) -> None:
    """Create or overwrite a StudentMark for (student, test). Shared by the CSV
    import and the needs-review resolve path so both write marks identically."""
    total = test.total_marks or 0.0
    pct = (marks / total * 100) if (total > 0 and not is_absent) else 0.0
    grade = None if is_absent else _calculate_grade(pct)
    existing = await test_repository.get_student_mark(session, student_id, test.id)
    fields = dict(
        marks_obtained=marks, max_marks=total, percentage=pct, grade=grade,
        is_absent=is_absent, raw_csv_row=raw, marked_at=now,
        marked_by=current_user_id,
    )
    if existing:
        # is_absent False must overwrite a prior True → set it explicitly
        # (update_student_mark skips None/falsey-safe fields via its own guard).
        existing.is_absent = is_absent
        await test_repository.update_student_mark(session, existing, **fields)
    else:
        await test_repository.create_student_mark(
            session, student_id=student_id, test_id=test.id,
            branch_id=branch_id, academic_year_id=test.academic_year_id,
            **fields,
        )


async def upload_result(
    session: AsyncSession,
    test_id: uuid.UUID,
    branch_id: uuid.UUID,
    csv_bytes: bytes,
    current_user_id: uuid.UUID,
    ip_address: str | None = None,
) -> dict:
    """Import a ZipGrade results CSV: match each row's PRN to a batch student,
    save marks, flag unmatched rows for review, and mark missing students absent
    (§4.3–4.5). Idempotent — re-uploading replaces the prior import for this test.
    """
    test = await test_repository.get_test_by_id(session, test_id)
    if not test:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")
    if test.branch_id != branch_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this branch")

    try:
        rows = zipgrade_csv.parse_zipgrade_csv(csv_bytes)
    except zipgrade_csv.ZipGradeCsvError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    roster = await _batch_roster(session, test.batch_id)
    # PRN (enrollment_number) -> student_id, case-insensitive.
    prn_to_student = {
        (enr or "").strip().lower(): sid
        for sid, _f, _l, enr in roster
        if (enr or "").strip()
    }

    # Idempotency: clear prior unmatched-review rows for this test.
    prior_review = (await session.execute(
        select(TestImportReview).where(
            TestImportReview.test_id == test_id,
            TestImportReview.is_deleted == False,
        )
    )).scalars().all()
    for r in prior_review:
        r.is_deleted = True

    now = datetime.now(timezone.utc)
    matched_ids: set[uuid.UUID] = set()
    matched = 0
    needs_review = 0

    for row in rows:
        key = (row["prn"] or "").strip().lower()
        if key and key in prn_to_student:
            sid = prn_to_student[key]
            await _upsert_mark(
                session, test=test, branch_id=branch_id, student_id=sid,
                marks=row["score"] or 0.0, is_absent=False, raw=row["raw"],
                current_user_id=current_user_id, now=now,
            )
            matched_ids.add(sid)
            matched += 1
        else:
            session.add(TestImportReview(
                test_id=test_id, branch_id=branch_id,
                csv_prn=row["prn"] or None, csv_name=row["name"] or None,
                raw_row=row["raw"],
            ))
            needs_review += 1

    # Batch students with no matching row → Absent.
    absent = 0
    for sid, _f, _l, _enr in roster:
        if sid not in matched_ids:
            await _upsert_mark(
                session, test=test, branch_id=branch_id, student_id=sid,
                marks=0.0, is_absent=True, raw=None,
                current_user_id=current_user_id, now=now,
            )
            absent += 1

    await session.flush()
    await event_service.emit_event(
        session,
        event_type="MARKS_UPDATED",
        test_id=test_id,
        batch_id=test.batch_id,
        subject_id=test.subject_id,
        branch_id=branch_id,
        metadata={"matched": matched, "needs_review": needs_review, "absent": absent},
    )
    await audit_service.log_action(
        session,
        user_id=current_user_id,
        action="UPDATE",
        table_name="student_marks",
        record_id=test_id,
        new_values={"matched": matched, "needs_review": needs_review, "absent": absent},
        ip_address=ip_address,
        branch_id=branch_id,
    )
    return {
        "matched": matched, "needs_review": needs_review, "absent": absent,
        "total_rows": len(rows),
    }


# ─── Test Portal: per-subject manual-marks CSV (Section 2) ────────────────────


async def _test_batch_ids(session: AsyncSession, test) -> list[uuid.UUID]:
    """Every batch the test is scheduled for: the ``test_batches`` rows unioned
    with the primary ``tests.batch_id`` (so a legacy single-batch test still has
    a roster even without a ``test_batches`` row)."""
    rows = (await session.execute(
        select(TestBatch.batch_id).where(
            TestBatch.test_id == test.id, TestBatch.is_deleted == False,
        )
    )).scalars().all()
    return list(dict.fromkeys([test.batch_id, *rows]))


async def _recompute_aggregate_marks(
    session: AsyncSession, test, test_subjects: list,
    student_ids, current_user_id: uuid.UUID, now: datetime,
) -> None:
    """Rebuild each student's aggregate ``StudentMark`` for the test as the sum of
    their per-subject ``TestSubjectMark`` rows, so the existing rank list and
    history keep working off StudentMark. A student present in no subject is
    aggregate-absent; otherwise their total is the sum of the subjects they sat."""
    total_possible = sum((ts.total_marks or 0.0) for ts in test_subjects)
    sm_rows = (await session.execute(
        select(TestSubjectMark).where(
            TestSubjectMark.test_id == test.id, TestSubjectMark.is_deleted == False,
        )
    )).scalars().all()
    by_student: dict[uuid.UUID, list] = defaultdict(list)
    for m in sm_rows:
        by_student[m.student_id].append(m)

    for sid in student_ids:
        present = [m for m in by_student.get(sid, []) if not m.absent]
        is_absent = not present
        total = sum((m.marks_obtained or 0.0) for m in present)
        pct = (total / total_possible * 100) if (total_possible > 0 and not is_absent) else 0.0
        grade = None if is_absent else _calculate_grade(pct)
        existing = await test_repository.get_student_mark(session, sid, test.id)
        if existing:
            existing.marks_obtained = total
            existing.max_marks = total_possible
            existing.percentage = pct
            existing.grade = grade
            existing.is_absent = is_absent
            existing.marked_at = now
            existing.marked_by = current_user_id
        else:
            await test_repository.create_student_mark(
                session, student_id=sid, test_id=test.id,
                branch_id=test.branch_id, academic_year_id=test.academic_year_id,
                marks_obtained=total, max_marks=total_possible, percentage=pct,
                grade=grade, is_absent=is_absent, raw_csv_row=None,
                marked_at=now, marked_by=current_user_id,
            )
    await session.flush()


async def upload_subject_csv(
    session: AsyncSession,
    test_id: uuid.UUID,
    subject_id: uuid.UUID,
    branch_id: uuid.UUID,
    csv_bytes: bytes,
    current_user_id: uuid.UUID,
    ip_address: str | None = None,
) -> dict:
    """Import one subject's marks CSV (Name, PRN, Marks) for the per-subject flow
    (Section 2). Matches each PRN to a student in any of the test's batches →
    ``TestSubjectMark`` (present); students in a batch but not in the CSV → absent
    for this subject; unmatched PRNs → ``TestImportReview``. Marks above the
    subject total are reported as errors and skipped. The aggregate ``StudentMark``
    (sum across subjects) is rebuilt so the rank list stays in sync. Idempotent —
    re-uploading replaces this subject's prior marks + review rows."""
    test = await test_repository.get_test_by_id(session, test_id)
    if not test:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")
    if test.branch_id != branch_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this branch")

    test_subjects = (await session.execute(
        select(TestSubject).where(
            TestSubject.test_id == test_id, TestSubject.is_deleted == False,
        )
    )).scalars().all()
    ts = next((t for t in test_subjects if t.subject_id == subject_id), None)
    if ts is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Subject is not part of this test",
        )
    subject_total = ts.total_marks

    try:
        rows = zipgrade_csv.parse_subject_marks_csv(csv_bytes)
    except zipgrade_csv.ZipGradeCsvError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    # Roster across all the test's batches; PRN (enrollment_number) -> student.
    roster: dict[uuid.UUID, uuid.UUID] = {}  # student_id -> batch_id
    prn_to_student: dict[str, uuid.UUID] = {}
    for bid in await _test_batch_ids(session, test):
        for sid, _f, _l, enr in await _batch_roster(session, bid):
            roster.setdefault(sid, bid)
            key = (enr or "").strip().lower()
            if key:
                prn_to_student.setdefault(key, sid)

    now = datetime.now(timezone.utc)

    # Idempotency: soft-delete this subject's prior marks + its prior review rows.
    for m in (await session.execute(
        select(TestSubjectMark).where(
            TestSubjectMark.test_id == test_id,
            TestSubjectMark.subject_id == subject_id,
            TestSubjectMark.is_deleted == False,
        )
    )).scalars().all():
        m.is_deleted = True
    for r in (await session.execute(
        select(TestImportReview).where(
            TestImportReview.test_id == test_id, TestImportReview.is_deleted == False,
        )
    )).scalars().all():
        if str(r.raw_row.get("__subject_id__")) == str(subject_id):
            r.is_deleted = True

    matched_ids: set[uuid.UUID] = set()
    matched = unmatched = 0
    errors: list[str] = []

    for i, row in enumerate(rows, start=1):
        marks = row["marks"]
        if marks is not None and subject_total is not None and marks > subject_total:
            errors.append(
                f"Row {i} (PRN {row['prn'] or '—'}): marks {marks} exceed the "
                f"subject total {subject_total}"
            )
            continue
        key = (row["prn"] or "").strip().lower()
        if key and key in prn_to_student:
            sid = prn_to_student[key]
            session.add(TestSubjectMark(
                test_id=test_id, student_id=sid, batch_id=roster.get(sid),
                subject_id=subject_id, marks_obtained=marks, absent=False,
                branch_id=branch_id, academic_year_id=test.academic_year_id,
            ))
            matched_ids.add(sid)
            matched += 1
        else:
            session.add(TestImportReview(
                test_id=test_id, branch_id=branch_id,
                csv_prn=row["prn"] or None, csv_name=row["name"] or None,
                raw_row={**row["raw"], "__subject_id__": str(subject_id)},
            ))
            unmatched += 1

    # Roster students with no row for this subject → absent for this subject.
    absent = 0
    for sid, bid in roster.items():
        if sid not in matched_ids:
            session.add(TestSubjectMark(
                test_id=test_id, student_id=sid, batch_id=bid,
                subject_id=subject_id, marks_obtained=None, absent=True,
                branch_id=branch_id, academic_year_id=test.academic_year_id,
            ))
            absent += 1

    await session.flush()
    await _recompute_aggregate_marks(
        session, test, test_subjects, roster.keys(), current_user_id, now,
    )

    # A subject counts as uploaded once it has any mark row (present or absent).
    uploaded_subject_ids = set((await session.execute(
        select(TestSubjectMark.subject_id).where(
            TestSubjectMark.test_id == test_id, TestSubjectMark.is_deleted == False,
        ).distinct()
    )).scalars().all())
    all_uploaded = {t.subject_id for t in test_subjects} <= uploaded_subject_ids

    await event_service.emit_event(
        session,
        event_type="MARKS_UPDATED",
        test_id=test_id,
        batch_id=test.batch_id,
        subject_id=subject_id,
        branch_id=branch_id,
        metadata={"matched": matched, "unmatched": unmatched, "absent": absent},
    )
    await audit_service.log_action(
        session,
        user_id=current_user_id,
        action="UPDATE",
        table_name="test_subject_marks",
        record_id=test_id,
        new_values={
            "subject_id": str(subject_id), "matched": matched,
            "unmatched": unmatched, "absent": absent,
        },
        ip_address=ip_address,
        branch_id=branch_id,
    )
    return {
        "subject_id": subject_id, "matched": matched, "unmatched": unmatched,
        "absent": absent, "errors": errors, "all_subjects_uploaded": all_uploaded,
    }


async def _subject_columns(session: AsyncSession, test) -> tuple[list, dict]:
    """Ordered subject columns for the per-subject rank list, and the per-student
    per-subject marks. Returns (subjects, by_student) where ``subjects`` is a list
    of ``{subject_id, subject_name, total_marks}`` in creation order and
    ``by_student`` maps student_id -> {subject_name: marks | None(absent/missing)}.

    A test is per-subject when any of its ``TestSubject`` rows carries a
    per-subject ``total_marks`` (set at create time) — so the subject columns and
    the per-subject upload targets are known even before any CSV is uploaded. An
    OMR/single-total test (no per-subject totals) returns ([], {}), leaving its
    rank list unchanged."""
    ts_rows = (await session.execute(
        select(TestSubject).where(
            TestSubject.test_id == test.id, TestSubject.is_deleted == False,
        ).order_by(TestSubject.created_at)
    )).scalars().all()
    if not any(t.total_marks is not None for t in ts_rows):
        return [], {}

    subject_ids = [t.subject_id for t in ts_rows]
    names: dict[uuid.UUID, str] = {}
    if subject_ids:
        for sid, name in (await session.execute(
            select(Subject.id, Subject.name).where(Subject.id.in_(subject_ids))
        )).all():
            names[sid] = name
    subjects = [
        {
            "subject_id": t.subject_id,
            "subject_name": names.get(t.subject_id, "—"),
            "total_marks": t.total_marks,
        }
        for t in ts_rows
    ]

    tsm = (await session.execute(
        select(TestSubjectMark).where(
            TestSubjectMark.test_id == test.id, TestSubjectMark.is_deleted == False,
        )
    )).scalars().all()
    by_student: dict[uuid.UUID, dict] = defaultdict(dict)
    for m in tsm:
        nm = names.get(m.subject_id, "—")
        by_student[m.student_id][nm] = None if m.absent else m.marks_obtained
    return subjects, by_student


async def get_ranklist(session: AsyncSession, test_id: uuid.UUID, branch_id: uuid.UUID) -> dict:
    """The rank list (spec Section 3): appeared students highest→lowest with
    tie-aware ranks (same total → same rank, next rank skips the tied positions),
    absentees grouped at the bottom, unmatched rows returned separately. Per-subject
    columns are included for the per-subject flow. Computed on the fly from
    StudentMark (+ TestSubjectMark) so it's always in sync."""
    test = await test_repository.get_test_by_id(session, test_id)
    if not test:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")
    if test.branch_id != branch_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this branch")

    marks = await test_repository.get_marks_by_test(session, test_id)
    student_ids = [m.student_id for m in marks]
    students: dict[uuid.UUID, tuple[str, str | None]] = {}
    if student_ids:
        for sid, first, last, enr in (await session.execute(
            select(Student.id, Student.first_name, Student.last_name,
                   Student.enrollment_number)
            .where(Student.id.in_(student_ids))
        )).all():
            students[sid] = (f"{first} {last}".strip(), enr)

    subjects, subject_marks = await _subject_columns(session, test)
    # Per-subject totals sum to the rank list's total when the per-subject flow is
    # used; else the test's single total.
    total_marks = test.total_marks
    if subjects:
        ts_total = sum(
            (t.total_marks or 0.0) for t in (await session.execute(
                select(TestSubject).where(
                    TestSubject.test_id == test_id, TestSubject.is_deleted == False,
                )
            )).scalars().all()
        )
        total_marks = ts_total or test.total_marks

    def _row(m, rank):
        name, prn = students.get(m.student_id, ("Unknown", None))
        return {
            "rank": rank, "student_id": m.student_id, "prn": prn, "name": name,
            "marks_obtained": None if m.is_absent else m.marks_obtained,
            "percentage": None if m.is_absent else m.percentage,
            "absent": m.is_absent,
            "subject_marks": subject_marks.get(m.student_id, {}),
        }

    appeared = sorted(
        (m for m in marks if not m.is_absent),
        key=lambda m: m.marks_obtained, reverse=True,
    )
    # Tie-aware rank: 1 + (number of students with a strictly higher total), so
    # equal totals share a rank and the next rank skips the tied positions.
    totals = [m.marks_obtained for m in appeared]
    ranked = [
        _row(m, 1 + sum(1 for t in totals if t > m.marks_obtained))
        for m in appeared
    ]
    absentees = sorted(
        (_row(m, None) for m in marks if m.is_absent),
        key=lambda r: r["name"],
    )

    review = (await session.execute(
        select(TestImportReview).where(
            TestImportReview.test_id == test_id,
            TestImportReview.resolved == False,
            TestImportReview.is_deleted == False,
        )
    )).scalars().all()
    needs_review = [
        {"id": r.id, "csv_prn": r.csv_prn, "csv_name": r.csv_name, "resolved": r.resolved}
        for r in review
    ]

    return {
        "test_id": test_id,
        "test_name": test.name,
        "total_marks": total_marks,
        "subjects": subjects,
        "ranked": ranked,
        "absentees": absentees,
        "needs_review": needs_review,
    }


async def resolve_review(
    session: AsyncSession,
    test_id: uuid.UUID,
    review_id: uuid.UUID,
    student_id: uuid.UUID,
    branch_id: uuid.UUID,
    current_user_id: uuid.UUID,
    ip_address: str | None = None,
) -> dict:
    """Resolve an unmatched ZipGrade row by assigning it to a student (PR-B).

    The reviewer picks the right student (a PRN typo, or a student sat the test
    outside their batch). We re-derive the marks from the row we kept verbatim,
    write the StudentMark (overwriting any absent placeholder), and mark the
    review row resolved. The rank list recomputes from marks, so it updates on
    the next read.
    """
    test = await test_repository.get_test_by_id(session, test_id)
    if not test:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")
    if test.branch_id != branch_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this branch")

    review = (await session.execute(
        select(TestImportReview).where(
            TestImportReview.id == review_id,
            TestImportReview.test_id == test_id,
            TestImportReview.is_deleted == False,
        )
    )).scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review row not found")
    if review.resolved:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Row already resolved")

    student = (await session.execute(
        select(Student).where(
            Student.id == student_id,
            Student.is_deleted == False,
        )
    )).scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")
    if student.branch_id != branch_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Student is in another branch")

    score, _total, _pct = zipgrade_csv.score_from_raw(review.raw_row or {})
    marks = score or 0.0
    now = datetime.now(timezone.utc)
    await _upsert_mark(
        session, test=test, branch_id=branch_id, student_id=student_id,
        marks=marks, is_absent=False, raw=review.raw_row,
        current_user_id=current_user_id, now=now,
    )

    review.resolved = True
    review.resolved_student_id = student_id
    review.resolved_at = now
    await session.flush()

    await audit_service.log_action(
        session,
        user_id=current_user_id,
        action="UPDATE",
        table_name="test_import_review",
        record_id=review_id,
        new_values={"resolved_student_id": str(student_id), "marks_obtained": marks},
        ip_address=ip_address,
        branch_id=branch_id,
    )
    return {"resolved": True, "student_id": student_id, "marks_obtained": marks}


# ─── Test Portal: answer-key file (reference only, no scoring) ────────────────


def _answer_key_storage_key(test_id: uuid.UUID, filename: str) -> str:
    """Namespaced, path-safe storage key for a test's answer-key file."""
    safe = safe_filename(filename)
    return f"answer-keys/{test_id}--{safe}"


async def set_answer_key(
    session: AsyncSession,
    test_id: uuid.UUID,
    branch_id: uuid.UUID,
    filename: str,
    content: bytes,
    storage: StorageBackend,
    current_user_id: uuid.UUID,
    ip_address: str | None = None,
) -> dict:
    """Store an uploaded answer-key file for reference (§4.2). Phase 1 doesn't
    score against it — ZipGrade already scored the sheets — it's kept so staff
    can eyeball the key. Replaces any prior key on the test."""
    test = await test_repository.get_test_by_id(session, test_id)
    if not test:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")
    if test.branch_id != branch_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this branch")

    new_key = _answer_key_storage_key(test_id, filename)
    prior = test.answer_key_file
    storage.write(new_key, content)
    # Drop the previous file if it was under a different key (name changed).
    if prior and prior != new_key:
        storage.delete(prior)
    test.answer_key_file = new_key
    await session.flush()

    await audit_service.log_action(
        session,
        user_id=current_user_id,
        action="UPDATE",
        table_name="tests",
        record_id=test_id,
        new_values={"answer_key_file": new_key},
        ip_address=ip_address,
        branch_id=branch_id,
    )
    return {"answer_key_file": new_key, "filename": safe_filename(filename)}


async def get_answer_key(
    session: AsyncSession,
    test_id: uuid.UUID,
    branch_id: uuid.UUID,
    storage: StorageBackend,
) -> tuple[str, bytes]:
    """Return (download_filename, bytes) for a test's stored answer key, or 404
    if none is set."""
    test = await test_repository.get_test_by_id(session, test_id)
    if not test:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")
    if test.branch_id != branch_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this branch")
    if not test.answer_key_file:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No answer key on this test")
    try:
        data = storage.read(test.answer_key_file)
    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Answer key file missing")
    # The stored key ends with "<uuid>--<original name>"; hand that name back.
    download_name = test.answer_key_file.rsplit("--", 1)[-1] or "answer-key"
    return download_name, data


# ─── StudentResponse Service (Tier 11) ───────────────────────────────────────

async def submit_responses(
    session: AsyncSession,
    test_id: uuid.UUID,
    payload,  # ResponseBulkSubmit
    branch_id: uuid.UUID,
    current_user_id: uuid.UUID,
    ip_address: str | None = None,
) -> dict:
    """Bulk-submit per-question student responses.

    Algorithm:
      1. Validate test exists in this branch and is loaded.
      2. Load the test's questions (TestQuestion rows) — defines which
         question_ids are valid for this test and their per-question
         marks_allocated.
      3. Load the underlying Question rows so we know correct_answer.
      4. For each submitted response:
         - reject if question_id isn't in this test's question set
         - mark is_correct by comparing selected_answer to question's
           correct_answer (case-insensitive trim)
         - marks_obtained = TestQuestion.marks_allocated if correct else 0
         - upsert into student_responses (replaces any earlier answer
           for the same (student, test, question) triple)
      5. For each unique student touched, recompute their StudentMark
         row from the sum of correct marks.

    Returns counts of inserts/updates/students-marked plus any row-level
    errors so the admin upload UI can show feedback.
    """
    test = await test_repository.get_test_by_id(session, test_id)
    if test is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Test not found"
        )
    if test.branch_id != branch_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No access to this branch",
        )

    test_questions = await test_repository.get_test_questions(session, test_id)
    if not test_questions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Test has no questions configured yet",
        )

    # Map question_id → (correct_answer, marks_allocated)
    marks_by_qid: dict[uuid.UUID, float] = {
        tq.question_id: float(tq.marks_allocated) for tq in test_questions
    }
    valid_qids = set(marks_by_qid.keys())

    # Pull correct answers once.
    answers_by_qid: dict[uuid.UUID, str] = {}
    for qid in valid_qids:
        q = await test_repository.get_question_by_id(session, qid)
        if q is not None:
            answers_by_qid[qid] = (q.correct_answer or "").strip().upper()

    max_marks = sum(marks_by_qid.values())
    now = datetime.now(timezone.utc)

    inserted = 0
    updated = 0
    errors: list[str] = []
    touched_students: set[uuid.UUID] = set()

    for idx, r in enumerate(payload.responses):
        if r.question_id not in valid_qids:
            errors.append(
                f"row {idx}: question {r.question_id} is not part of this test"
            )
            continue
        selected = (r.selected_answer or "").strip()
        is_correct = (
            selected.upper() == answers_by_qid.get(r.question_id, "")
            if selected
            else False
        )
        marks = marks_by_qid[r.question_id] if is_correct else 0.0
        _, created = await test_repository.upsert_response(
            session,
            student_id=r.student_id,
            test_id=test_id,
            question_id=r.question_id,
            selected_answer=selected or None,
            is_correct=is_correct,
            marks_obtained=marks,
            submitted_at=now,
            branch_id=branch_id,
            academic_year_id=test.academic_year_id,
        )
        if created:
            inserted += 1
        else:
            updated += 1
        touched_students.add(r.student_id)

    # Refresh StudentMark for every student we touched.
    for student_id in touched_students:
        total = await test_repository.sum_correct_marks_for_student(
            session, student_id, test_id
        )
        await test_repository.upsert_student_mark(
            session,
            student_id=student_id,
            test_id=test_id,
            marks_obtained=total,
            max_marks=max_marks,
            branch_id=branch_id,
            academic_year_id=test.academic_year_id,
            marked_at=now,
        )

    await audit_service.log_action(
        session,
        user_id=current_user_id,
        action="CREATE",
        table_name="student_responses",
        record_id=test_id,
        new_values={
            "test_id": str(test_id),
            "inserted": inserted,
            "updated": updated,
            "students_marked": len(touched_students),
            "errors": errors[:10],
        },
        ip_address=ip_address,
        branch_id=branch_id,
    )

    return {
        "test_id": test_id,
        "inserted": inserted,
        "updated": updated,
        "students_marked": len(touched_students),
        "errors": errors,
    }
