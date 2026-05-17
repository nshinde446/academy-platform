import uuid

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.tests.models.test_models import (
    Question,
    QuestionTopic,
    StudentMark,
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


async def list_questions(
    session: AsyncSession,
    branch_id: uuid.UUID,
    subject_id: uuid.UUID | None = None,
    topic_id: uuid.UUID | None = None,
    difficulty: str | None = None,
    blooms_taxonomy: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> list[Question]:
    query = select(Question).where(
        Question.branch_id == branch_id, Question.is_deleted == False
    )
    if subject_id:
        query = query.where(Question.subject_id == subject_id)
    if topic_id:
        query = query.where(Question.topic_id == topic_id)
    if difficulty:
        query = query.where(Question.difficulty == difficulty)
    if blooms_taxonomy:
        query = query.where(Question.blooms_taxonomy == blooms_taxonomy)
    query = query.order_by(Question.created_at.desc()).offset(offset).limit(limit)
    result = await session.execute(query)
    return list(result.scalars().all())


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
