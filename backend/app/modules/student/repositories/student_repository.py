import uuid

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
