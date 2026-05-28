import uuid

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.tests.models.test_models import (
    Question,
    QuestionTopic,
    StudentMark,
    StudentResponse,
    Test,
    TestQuestion,
)


# ─── Question Repository ──────────────────────────────────────────────────────

async def create_question(session: AsyncSession, **kwargs) -> Question:
    question = Question(**kwargs)
    session.add(question)
    await session.flush()
    return question


async def get_question_by_id(session: AsyncSession, question_id: uuid.UUID) -> Question | None:
    result = await session.execute(
        select(Question).where(Question.id == question_id, Question.is_deleted == False)
    )
    return result.scalar_one_or_none()


def _apply_question_filters(
    stmt,
    *,
    is_postgres: bool,
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
):
    """Apply all question-bank filters to a select. Joins materials only
    when a material-derived facet (class_label / topic) is requested."""
    from app.modules.materials.models.material_models import Material

    clauses = [Question.branch_id == branch_id, Question.is_deleted == False]
    if subject_id:
        clauses.append(Question.subject_id == subject_id)
    if topic_id:
        clauses.append(Question.topic_id == topic_id)
    if difficulty:
        clauses.append(Question.difficulty == difficulty)
    if blooms_taxonomy:
        clauses.append(Question.blooms_taxonomy == blooms_taxonomy)
    if review_status:
        clauses.append(Question.review_status == review_status)
    if source_prefix:
        clauses.append(Question.source.like(f"{source_prefix}%"))
    if search:
        clauses.append(Question.content.ilike(f"%{search}%"))
    if material_id:
        clauses.append(Question.material_id == material_id)
    # exam_types is a Postgres ARRAY (JSON on the SQLite test DB). The
    # array-contains operator is PG-only; on SQLite we skip it rather
    # than emit invalid SQL.
    if exam_type and is_postgres:
        clauses.append(Question.exam_types.any(exam_type))

    if class_label or topic:
        stmt = stmt.join(Material, Question.material_id == Material.id)
        if class_label:
            clauses.append(Material.class_label == class_label)
        if topic:
            clauses.append(Material.topic == topic)

    return stmt.where(*clauses)


def _is_pg(session: AsyncSession) -> bool:
    return session.bind.dialect.name == "postgresql"


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
) -> list[Question]:
    stmt = _apply_question_filters(
        select(Question),
        is_postgres=_is_pg(session),
        branch_id=branch_id, subject_id=subject_id, topic_id=topic_id,
        difficulty=difficulty, blooms_taxonomy=blooms_taxonomy,
        review_status=review_status, source_prefix=source_prefix, search=search,
        material_id=material_id, class_label=class_label, topic=topic,
        exam_type=exam_type,
    )
    stmt = stmt.order_by(Question.created_at.desc()).offset(offset).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def count_questions(
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
) -> int:
    stmt = _apply_question_filters(
        select(func.count(Question.id)),
        is_postgres=_is_pg(session),
        branch_id=branch_id, subject_id=subject_id, topic_id=topic_id,
        difficulty=difficulty, blooms_taxonomy=blooms_taxonomy,
        review_status=review_status, source_prefix=source_prefix, search=search,
        material_id=material_id, class_label=class_label, topic=topic,
        exam_type=exam_type,
    )
    result = await session.execute(stmt)
    return int(result.scalar() or 0)


async def bulk_update_review_status(
    session: AsyncSession,
    branch_id: uuid.UUID,
    question_ids: list[uuid.UUID],
    new_status: str,
) -> tuple[int, list[uuid.UUID]]:
    """Bulk approve / reject. Returns (updated_count, skipped_ids)."""
    if not question_ids:
        return 0, []
    result = await session.execute(
        select(Question).where(
            Question.id.in_(question_ids),
            Question.branch_id == branch_id,
            Question.is_deleted == False,
        )
    )
    rows = list(result.scalars().all())
    found_ids = {q.id for q in rows}
    skipped = [qid for qid in question_ids if qid not in found_ids]
    for q in rows:
        q.review_status = new_status
    await session.flush()
    return len(rows), skipped


async def update_question(session: AsyncSession, question: Question, **kwargs) -> Question:
    for key, value in kwargs.items():
        if value is not None:
            setattr(question, key, value)
    await session.flush()
    return question


async def soft_delete_question(session: AsyncSession, question: Question) -> None:
    question.is_deleted = True
    await session.flush()


# ─── Test Repository ──────────────────────────────────────────────────────────

async def create_test(session: AsyncSession, **kwargs) -> Test:
    test = Test(**kwargs)
    session.add(test)
    await session.flush()
    return test


async def get_test_by_id(session: AsyncSession, test_id: uuid.UUID) -> Test | None:
    result = await session.execute(
        select(Test).where(Test.id == test_id, Test.is_deleted == False)
    )
    return result.scalar_one_or_none()


async def list_tests(
    session: AsyncSession,
    branch_id: uuid.UUID,
    batch_id: uuid.UUID | None = None,
    subject_id: uuid.UUID | None = None,
    offset: int = 0,
    limit: int = 50,
) -> list[Test]:
    query = select(Test).where(Test.branch_id == branch_id, Test.is_deleted == False)
    if batch_id:
        query = query.where(Test.batch_id == batch_id)
    if subject_id:
        query = query.where(Test.subject_id == subject_id)
    query = query.order_by(Test.created_at.desc()).offset(offset).limit(limit)
    result = await session.execute(query)
    return list(result.scalars().all())


async def update_test(session: AsyncSession, test: Test, **kwargs) -> Test:
    for key, value in kwargs.items():
        if value is not None:
            setattr(test, key, value)
    await session.flush()
    return test


async def soft_delete_test(session: AsyncSession, test: Test) -> None:
    test.is_deleted = True
    await session.flush()


# ─── TestQuestion Repository ──────────────────────────────────────────────────

async def add_questions_to_test(
    session: AsyncSession, test_id: uuid.UUID, questions: list[dict]
) -> list[TestQuestion]:
    objects = []
    for q in questions:
        tq = TestQuestion(
            test_id=test_id,
            question_id=q["question_id"],
            marks_allocated=q.get("marks_allocated", 1.0),
            order=q.get("order", 0),
        )
        objects.append(tq)
    session.add_all(objects)
    await session.flush()
    return objects


async def get_test_questions(session: AsyncSession, test_id: uuid.UUID) -> list[TestQuestion]:
    result = await session.execute(
        select(TestQuestion).where(
            TestQuestion.test_id == test_id, TestQuestion.is_deleted == False
        ).order_by(TestQuestion.order)
    )
    return list(result.scalars().all())


# ─── StudentMark Repository ──────────────────────────────────────────────────

async def create_student_mark(session: AsyncSession, **kwargs) -> StudentMark:
    mark = StudentMark(**kwargs)
    session.add(mark)
    await session.flush()
    return mark


async def get_student_mark(
    session: AsyncSession, student_id: uuid.UUID, test_id: uuid.UUID
) -> StudentMark | None:
    result = await session.execute(
        select(StudentMark).where(
            StudentMark.student_id == student_id,
            StudentMark.test_id == test_id,
            StudentMark.is_deleted == False,
        )
    )
    return result.scalar_one_or_none()


async def update_student_mark(session: AsyncSession, mark: StudentMark, **kwargs) -> StudentMark:
    for key, value in kwargs.items():
        if value is not None:
            setattr(mark, key, value)
    await session.flush()
    return mark


async def get_marks_by_test(
    session: AsyncSession, test_id: uuid.UUID
) -> list[StudentMark]:
    result = await session.execute(
        select(StudentMark).where(
            StudentMark.test_id == test_id, StudentMark.is_deleted == False
        )
    )
    return list(result.scalars().all())


async def get_marks_by_student(
    session: AsyncSession, student_id: uuid.UUID, branch_id: uuid.UUID,
    offset: int = 0, limit: int = 50,
) -> list[StudentMark]:
    result = await session.execute(
        select(StudentMark)
        .where(
            StudentMark.student_id == student_id,
            StudentMark.branch_id == branch_id,
            StudentMark.is_deleted == False,
        )
        .order_by(StudentMark.marked_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_test_statistics(session: AsyncSession, test_id: uuid.UUID) -> dict:
    result = await session.execute(
        select(
            func.count(StudentMark.id),
            func.avg(StudentMark.percentage),
            func.max(StudentMark.marks_obtained),
            func.min(StudentMark.marks_obtained),
        ).where(
            StudentMark.test_id == test_id,
            StudentMark.is_deleted == False,
            StudentMark.is_absent == False,
        )
    )
    row = result.first()
    return {
        "appeared": row[0] or 0,
        "average": float(row[1] or 0),
        "highest": float(row[2] or 0),
        "lowest": float(row[3] or 0),
    }


async def count_absent(session: AsyncSession, test_id: uuid.UUID) -> int:
    result = await session.execute(
        select(func.count(StudentMark.id)).where(
            StudentMark.test_id == test_id,
            StudentMark.is_deleted == False,
            StudentMark.is_absent == True,
        )
    )
    return result.scalar() or 0


# ─── StudentResponse Repository (Tier 11) ────────────────────────────────────

async def get_response(
    session: AsyncSession,
    student_id: uuid.UUID,
    test_id: uuid.UUID,
    question_id: uuid.UUID,
) -> StudentResponse | None:
    result = await session.execute(
        select(StudentResponse).where(
            StudentResponse.student_id == student_id,
            StudentResponse.test_id == test_id,
            StudentResponse.question_id == question_id,
            StudentResponse.is_deleted == False,
        )
    )
    return result.scalar_one_or_none()


async def upsert_response(
    session: AsyncSession,
    *,
    student_id: uuid.UUID,
    test_id: uuid.UUID,
    question_id: uuid.UUID,
    selected_answer: str | None,
    is_correct: bool,
    marks_obtained: float,
    submitted_at,
    branch_id: uuid.UUID,
    academic_year_id: uuid.UUID,
) -> tuple[StudentResponse, bool]:
    """Insert-or-update by (student_id, test_id, question_id).

    Returns (row, created_bool) so the service can count inserts vs updates.
    """
    existing = await get_response(session, student_id, test_id, question_id)
    if existing is not None:
        existing.selected_answer = selected_answer
        existing.is_correct = is_correct
        existing.marks_obtained = marks_obtained
        existing.submitted_at = submitted_at
        await session.flush()
        return existing, False
    row = StudentResponse(
        student_id=student_id,
        test_id=test_id,
        question_id=question_id,
        selected_answer=selected_answer,
        is_correct=is_correct,
        marks_obtained=marks_obtained,
        submitted_at=submitted_at,
        branch_id=branch_id,
        academic_year_id=academic_year_id,
        status="active",
        is_deleted=False,
    )
    session.add(row)
    await session.flush()
    return row, True


async def list_responses_by_test(
    session: AsyncSession, test_id: uuid.UUID
) -> list[StudentResponse]:
    result = await session.execute(
        select(StudentResponse).where(
            StudentResponse.test_id == test_id,
            StudentResponse.is_deleted == False,
        )
    )
    return list(result.scalars().all())


async def sum_correct_marks_for_student(
    session: AsyncSession, student_id: uuid.UUID, test_id: uuid.UUID
) -> float:
    """Total marks earned by a student on a test (sum of correct responses)."""
    result = await session.execute(
        select(func.sum(StudentResponse.marks_obtained)).where(
            StudentResponse.student_id == student_id,
            StudentResponse.test_id == test_id,
            StudentResponse.is_deleted == False,
        )
    )
    return float(result.scalar() or 0.0)


async def get_student_mark(
    session: AsyncSession, student_id: uuid.UUID, test_id: uuid.UUID
) -> StudentMark | None:
    result = await session.execute(
        select(StudentMark).where(
            StudentMark.student_id == student_id,
            StudentMark.test_id == test_id,
            StudentMark.is_deleted == False,
        )
    )
    return result.scalar_one_or_none()


async def upsert_student_mark(
    session: AsyncSession,
    *,
    student_id: uuid.UUID,
    test_id: uuid.UUID,
    marks_obtained: float,
    max_marks: float,
    branch_id: uuid.UUID,
    academic_year_id: uuid.UUID,
    marked_at,
) -> StudentMark:
    """Refresh the aggregate mark row from response totals."""
    existing = await get_student_mark(session, student_id, test_id)
    percentage = (marks_obtained / max_marks * 100.0) if max_marks > 0 else 0.0
    if existing is not None:
        existing.marks_obtained = marks_obtained
        existing.max_marks = max_marks
        existing.percentage = round(percentage, 2)
        existing.is_absent = False
        existing.marked_at = marked_at
        await session.flush()
        return existing
    row = StudentMark(
        student_id=student_id,
        test_id=test_id,
        marks_obtained=marks_obtained,
        max_marks=max_marks,
        percentage=round(percentage, 2),
        is_absent=False,
        marked_at=marked_at,
        branch_id=branch_id,
        academic_year_id=academic_year_id,
        status="active",
        is_deleted=False,
    )
    session.add(row)
    await session.flush()
    return row
