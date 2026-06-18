import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.student.models.student_models import (
    Student,
    StudentBatchMapping,
)


async def create(session: AsyncSession, **kwargs) -> Student:
    student = Student(**kwargs)
    session.add(student)
    await session.flush()
    return student


async def get_by_id(session: AsyncSession, student_id: uuid.UUID) -> Student | None:
    result = await session.execute(
        select(Student).where(Student.id == student_id, Student.is_deleted == False)
    )
    return result.scalar_one_or_none()


async def list_by_branch(
    session: AsyncSession, branch_id: uuid.UUID, offset: int = 0, limit: int = 50
) -> list[Student]:
    result = await session.execute(
        select(Student)
        .where(Student.branch_id == branch_id, Student.is_deleted == False)
        .offset(offset)
        .limit(limit)
    )
    return list(result.scalars().all())


async def update(session: AsyncSession, student: Student, **kwargs) -> Student:
    for key, value in kwargs.items():
        if value is not None:
            setattr(student, key, value)
    await session.flush()
    return student


async def soft_delete(session: AsyncSession, student: Student) -> None:
    student.is_deleted = True
    await session.flush()


async def list_with_stats(
    session: AsyncSession, branch_id: uuid.UUID
) -> list[dict]:
    """Return every active student in the branch enriched with batch
    info + per-student stats (avg test score, attendance %, DPP
    completion %). Three aggregation queries + one main fetch, all
    joined in Python — keeps each individual query simple and easy
    to reason about with the existing repo style."""
    # Imports inside the function so the SQLAlchemy metadata is
    # already populated by the time we reference cross-module models.
    from app.modules.batch.models.batch_models import Batch
    from app.modules.lectures.models.lecture_models import (
        LectureAttendanceMapping,
        Lecture,
    )
    from app.modules.tests.models.test_models import StudentMark, StudentResponse

    # Step 1: students + batch lookup.
    students = (
        await session.execute(
            select(Student).where(
                Student.branch_id == branch_id,
                Student.is_deleted == False,
            )
        )
    ).scalars().all()

    student_ids = [s.id for s in students]

    batch_map_rows = (
        await session.execute(
            select(StudentBatchMapping.student_id, StudentBatchMapping.batch_id).where(
                StudentBatchMapping.student_id.in_(student_ids),
                StudentBatchMapping.is_deleted == False,
            )
        )
    ).all() if student_ids else []
    batch_by_student: dict[uuid.UUID, uuid.UUID] = {
        r.student_id: r.batch_id for r in batch_map_rows
    }
    batch_ids = list({bid for bid in batch_by_student.values()})

    batches_by_id: dict[uuid.UUID, str] = {}
    if batch_ids:
        batch_rows = (
            await session.execute(
                select(Batch.id, Batch.name).where(Batch.id.in_(batch_ids))
            )
        ).all()
        batches_by_id = {r.id: r.name for r in batch_rows}

    # Step 2: avg test score + tests taken (excludes absentees).
    avg_score_by_student: dict[uuid.UUID, tuple[float, int]] = {}
    if student_ids:
        rows = (
            await session.execute(
                select(
                    StudentMark.student_id,
                    func.avg(StudentMark.percentage),
                    func.count(StudentMark.id),
                ).where(
                    StudentMark.student_id.in_(student_ids),
                    StudentMark.is_deleted == False,
                    StudentMark.is_absent == False,
                ).group_by(StudentMark.student_id)
            )
        ).all()
        for r in rows:
            avg_score_by_student[r[0]] = (float(r[1] or 0.0), int(r[2] or 0))

    # Step 3: attendance % over completed lectures the student's batch
    # actually held.
    attendance_by_student: dict[uuid.UUID, float] = {}
    if student_ids:
        rows = (
            await session.execute(
                select(
                    LectureAttendanceMapping.student_id,
                    func.count(LectureAttendanceMapping.id),
                    func.count().filter(
                        LectureAttendanceMapping.attendance_status == "PRESENT"
                    ),
                )
                .join(Lecture, Lecture.id == LectureAttendanceMapping.lecture_id)
                .where(
                    LectureAttendanceMapping.student_id.in_(student_ids),
                    LectureAttendanceMapping.is_deleted == False,
                    Lecture.lecture_status == "completed",
                )
                .group_by(LectureAttendanceMapping.student_id)
            )
        ).all()
        for r in rows:
            total = int(r[1] or 0)
            present = int(r[2] or 0)
            pct = round(100.0 * present / total, 1) if total > 0 else 0.0
            attendance_by_student[r[0]] = pct

    # Step 4: DPP completion proxy — % of student_responses submitted
    # (any test, any subject) over total questions on those tests. Once
    # the papers table exists we'll narrow this to DPP-typed papers.
    dpp_by_student: dict[uuid.UUID, float] = {}
    if student_ids:
        rows = (
            await session.execute(
                select(
                    StudentResponse.student_id,
                    func.count(StudentResponse.id),
                    func.count().filter(StudentResponse.is_correct == True),
                ).where(
                    StudentResponse.student_id.in_(student_ids),
                    StudentResponse.is_deleted == False,
                ).group_by(StudentResponse.student_id)
            )
        ).all()
        for r in rows:
            attempted = int(r[1] or 0)
            correct = int(r[2] or 0)
            pct = round(100.0 * correct / attempted, 1) if attempted > 0 else 0.0
            dpp_by_student[r[0]] = pct

    # Step 5: build rows, compute batch rank.
    raw_rows: list[dict] = []
    for s in students:
        avg_score, tests_taken = avg_score_by_student.get(s.id, (0.0, 0))
        raw_rows.append({
            "id": s.id,
            "first_name": s.first_name,
            "last_name": s.last_name,
            "enrollment_number": s.enrollment_number,
            "standard": s.standard,
            "target_exam": s.target_exam,
            "fees_status": s.fees_status,
            "batch_id": batch_by_student.get(s.id),
            "batch_name": batches_by_id.get(batch_by_student.get(s.id)) if batch_by_student.get(s.id) else None,
            "avg_score_pct": round(avg_score, 1),
            "attendance_pct": attendance_by_student.get(s.id, 0.0),
            "dpp_completion_pct": dpp_by_student.get(s.id, 0.0),
            "tests_taken": tests_taken,
        })

    # Rank within batch by avg_score desc.
    by_batch: dict[uuid.UUID | None, list[dict]] = {}
    for r in raw_rows:
        by_batch.setdefault(r["batch_id"], []).append(r)
    for bid, rows in by_batch.items():
        rows.sort(key=lambda x: x["avg_score_pct"], reverse=True)
        for idx, r in enumerate(rows, start=1):
            r["batch_rank"] = idx if bid is not None else None
            r["batch_size"] = len(rows) if bid is not None else 0

    return raw_rows


async def get_topic_mastery(
    session: AsyncSession, student_id: uuid.UUID, branch_id: uuid.UUID
) -> list[dict]:
    """Per-topic accuracy for a student, aggregated from their per-question
    responses (Tier 13 weakness map). Returns weakest topics first so the UI
    can lead with where the student is struggling. Questions with no topic tag
    are excluded (the inner join drops them)."""
    from app.modules.academic.models.academic_models import Subject, Topic
    from app.modules.tests.models.test_models import Question, StudentResponse

    student = await get_by_id(session, student_id)
    if student is None or student.branch_id != branch_id:
        return []

    rows = (
        await session.execute(
            select(
                Topic.id,
                Topic.name,
                Subject.name,
                func.count(StudentResponse.id),
                func.count().filter(StudentResponse.is_correct == True),  # noqa: E712
            )
            .join(Question, StudentResponse.question_id == Question.id)
            .join(Topic, Question.topic_id == Topic.id)
            .join(Subject, Question.subject_id == Subject.id)
            .where(
                StudentResponse.student_id == student_id,
                StudentResponse.is_deleted == False,  # noqa: E712
            )
            .group_by(Topic.id, Topic.name, Subject.name)
        )
    ).all()

    out: list[dict] = []
    for r in rows:
        attempted = int(r[3] or 0)
        correct = int(r[4] or 0)
        out.append(
            {
                "topic_id": r[0],
                "topic_name": r[1],
                "subject_name": r[2],
                "attempted": attempted,
                "correct": correct,
                "accuracy_pct": (
                    round(100.0 * correct / attempted, 1) if attempted else 0.0
                ),
            }
        )
    # Weakest first: lowest accuracy, ties broken by most-attempted (most signal).
    out.sort(key=lambda x: (x["accuracy_pct"], -x["attempted"]))
    return out


async def get_test_history(
    session: AsyncSession, student_id: uuid.UUID, branch_id: uuid.UUID
) -> list[dict]:
    """Per-student test history with subject, topics, marks, and
    both batch + institute rankings for each test the student took.

    Drives /students/[id] (Tier 13). One pass per join — no N+1 per
    test — then ranks are computed in Python so the query stays
    portable across Postgres and the SQLite test DB.
    """
    from app.modules.academic.models.academic_models import Subject, Topic
    from app.modules.tests.models.test_models import (
        Question,
        StudentMark,
        Test,
        TestQuestion,
    )

    student = await get_by_id(session, student_id)
    if student is None or student.branch_id != branch_id:
        return []

    student_batch_id = (
        await session.execute(
            select(StudentBatchMapping.batch_id).where(
                StudentBatchMapping.student_id == student_id,
                StudentBatchMapping.is_deleted == False,  # noqa: E712
            )
        )
    ).scalar_one_or_none()

    student_marks = (
        await session.execute(
            select(StudentMark).where(
                StudentMark.student_id == student_id,
                StudentMark.branch_id == branch_id,
                StudentMark.is_deleted == False,  # noqa: E712
            )
        )
    ).scalars().all()
    if not student_marks:
        return []

    test_ids = [m.test_id for m in student_marks]

    test_rows = (
        await session.execute(
            select(Test).where(Test.id.in_(test_ids))
        )
    ).scalars().all()
    test_by_id = {t.id: t for t in test_rows}

    subject_ids = list({t.subject_id for t in test_rows})
    subject_by_id: dict[uuid.UUID, str] = {}
    if subject_ids:
        rows = (
            await session.execute(
                select(Subject.id, Subject.name).where(Subject.id.in_(subject_ids))
            )
        ).all()
        subject_by_id = {r.id: r.name for r in rows}

    # Topics per test — distinct topic names across the test's questions.
    topics_by_test: dict[uuid.UUID, list[str]] = {tid: [] for tid in test_ids}
    if test_ids:
        rows = (
            await session.execute(
                select(TestQuestion.test_id, Topic.name)
                .join(Question, Question.id == TestQuestion.question_id)
                .join(Topic, Topic.id == Question.topic_id)
                .where(
                    TestQuestion.test_id.in_(test_ids),
                    TestQuestion.is_deleted == False,  # noqa: E712
                )
            )
        ).all()
        for r in rows:
            bucket = topics_by_test.setdefault(r.test_id, [])
            if r.name not in bucket:
                bucket.append(r.name)

    # All marks across these tests in the same branch — for ranking.
    all_marks_rows = (
        await session.execute(
            select(StudentMark).where(
                StudentMark.test_id.in_(test_ids),
                StudentMark.branch_id == branch_id,
                StudentMark.is_deleted == False,  # noqa: E712
                StudentMark.is_absent == False,
            )
        )
    ).scalars().all()

    # Batch membership for every student who has a mark on these tests.
    candidate_student_ids = list({m.student_id for m in all_marks_rows})
    batch_by_student: dict[uuid.UUID, uuid.UUID] = {}
    if candidate_student_ids:
        rows = (
            await session.execute(
                select(
                    StudentBatchMapping.student_id, StudentBatchMapping.batch_id
                ).where(
                    StudentBatchMapping.student_id.in_(candidate_student_ids),
                    StudentBatchMapping.is_deleted == False,  # noqa: E712
                )
            )
        ).all()
        batch_by_student = {r.student_id: r.batch_id for r in rows}

    # Per-test ranking buckets.
    marks_by_test: dict[uuid.UUID, list] = {}
    for m in all_marks_rows:
        marks_by_test.setdefault(m.test_id, []).append(m)

    out: list[dict] = []
    for m in student_marks:
        test = test_by_id.get(m.test_id)
        if test is None:
            continue

        siblings = marks_by_test.get(m.test_id, [])
        # Institute rank (whole branch). Absentees already filtered out.
        institute_present = sorted(
            siblings, key=lambda x: x.percentage, reverse=True
        )
        institute_size = len(institute_present)
        institute_rank: int | None = None
        if not m.is_absent:
            for idx, row in enumerate(institute_present, start=1):
                if row.student_id == student_id:
                    institute_rank = idx
                    break

        # Batch rank — only the student's batch peers.
        batch_present: list = []
        if student_batch_id is not None:
            batch_present = sorted(
                (s for s in institute_present
                 if batch_by_student.get(s.student_id) == student_batch_id),
                key=lambda x: x.percentage,
                reverse=True,
            )
        batch_size = len(batch_present)
        batch_rank: int | None = None
        if not m.is_absent and student_batch_id is not None:
            for idx, row in enumerate(batch_present, start=1):
                if row.student_id == student_id:
                    batch_rank = idx
                    break

        out.append({
            "test_id": test.id,
            "test_name": test.name,
            "paper_type": test.paper_type,
            "scheduled_at": test.scheduled_at,
            "subject_id": test.subject_id,
            "subject_name": subject_by_id.get(test.subject_id, ""),
            "topics": topics_by_test.get(test.id, []),
            "marks_obtained": m.marks_obtained,
            "max_marks": m.max_marks,
            "percentage": m.percentage,
            "grade": m.grade,
            "is_absent": m.is_absent,
            "batch_rank": batch_rank,
            "batch_size": batch_size,
            "institute_rank": institute_rank,
            "institute_size": institute_size,
        })

    # Newest tests first; rows without a scheduled_at sink to the bottom.
    out.sort(
        key=lambda r: r["scheduled_at"] or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    return out
