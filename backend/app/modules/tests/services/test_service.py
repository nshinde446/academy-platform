import json
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.services import audit_service
from app.modules.batch.repositories import batch_repository
from app.modules.events.services import event_service
from app.modules.tests.repositories import test_repository

VALID_DIFFICULTIES = {"EASY", "MEDIUM", "HARD"}
VALID_BLOOMS = {"REMEMBER", "UNDERSTAND", "APPLY", "ANALYZE", "EVALUATE", "CREATE"}
VALID_TEST_STATUSES = {"DRAFT", "SCHEDULED", "ACTIVE", "COMPLETED", "CANCELLED"}
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


async def list_questions(
    session: AsyncSession,
    branch_id: uuid.UUID,
    subject_id: uuid.UUID | None = None,
    topic_id: uuid.UUID | None = None,
    difficulty: str | None = None,
    blooms_taxonomy: str | None = None,
    offset: int = 0,
    limit: int = 50,
):
    questions = await test_repository.list_questions(
        session, branch_id, subject_id, topic_id, difficulty, blooms_taxonomy, offset, limit
    )
    return [_format_question(q) for q in questions]


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
        "concept_tags": json.loads(question.concept_tags) if question.concept_tags else None,
        "branch_id": question.branch_id,
        "academic_year_id": question.academic_year_id,
        "status": question.status,
    }


# ─── Test Service ─────────────────────────────────────────────────────────────

async def create_test(
    session: AsyncSession,
    data: dict,
    current_user_id: uuid.UUID,
    ip_address: str | None = None,
):
    batch = await batch_repository.get_by_id(session, data["batch_id"])
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")

    test = await test_repository.create_test(
        session,
        name=data["name"],
        description=data.get("description"),
        batch_id=data["batch_id"],
        subject_id=data["subject_id"],
        scheduled_at=data.get("scheduled_at"),
        duration_minutes=data.get("duration_minutes", 60),
        total_marks=data.get("total_marks", 100.0),
        test_status="DRAFT",
        branch_id=batch.branch_id,
        academic_year_id=batch.start_academic_year_id,
    )

    await audit_service.log_action(
        session,
        user_id=current_user_id,
        action="CREATE",
        table_name="tests",
        record_id=test.id,
        new_values={"name": data["name"]},
        ip_address=ip_address,
        branch_id=batch.branch_id,
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
