import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.teacher.models.teacher_models import Teacher, TeacherSubjectMapping


async def create(session: AsyncSession, **kwargs) -> Teacher:
    teacher = Teacher(**kwargs)
    session.add(teacher)
    await session.flush()
    return teacher


async def get_by_id(session: AsyncSession, teacher_id: uuid.UUID) -> Teacher | None:
    result = await session.execute(
        select(Teacher).where(Teacher.id == teacher_id, Teacher.is_deleted == False)
    )
    return result.scalar_one_or_none()


async def list_by_branch(
    session: AsyncSession, branch_id: uuid.UUID, offset: int = 0, limit: int = 50
) -> list[Teacher]:
    result = await session.execute(
        select(Teacher)
        .where(Teacher.branch_id == branch_id, Teacher.is_deleted == False)
        .offset(offset)
        .limit(limit)
    )
    return list(result.scalars().all())


async def update(session: AsyncSession, teacher: Teacher, **kwargs) -> Teacher:
    for key, value in kwargs.items():
        if value is not None:
            setattr(teacher, key, value)
    await session.flush()
    return teacher


async def soft_delete(session: AsyncSession, teacher: Teacher) -> None:
    teacher.is_deleted = True
    await session.flush()


async def list_with_stats(
    session: AsyncSession, branch_id: uuid.UUID
) -> list[dict]:
    """Roster + per-teacher adherence + outcome metrics for the
    MSA_Design teachers list.

    Three lightweight aggregations, joined in Python:
      - lectures_30d: count of lectures whose actual_teacher_id (or
        teacher_id if unchanged) resolves to this teacher in the last 30
        days, lecture_status = 'completed'.
      - sub_rate_pct: % of those 30d lectures where actual_teacher_id
        was set AND != teacher_id (they substituted in for someone).
      - avg_outcome_delta_pp: placeholder — we don't have a baseline
        score per lecture yet, so we surface the avg test percentage
        across the teacher's primary subject in the last 30d as a
        directional outcome signal (NULL when no tests linked)."""
    from app.modules.academic.models.academic_models import Subject
    from app.modules.lectures.models.lecture_models import Lecture
    from app.modules.tests.models.test_models import StudentMark, Test

    teachers = (
        await session.execute(
            select(Teacher).where(
                Teacher.branch_id == branch_id,
                Teacher.is_deleted == False,
            )
        )
    ).scalars().all()

    teacher_ids = [t.id for t in teachers]

    # Primary subject lookup (first mapped subject wins for the badge).
    subject_by_teacher: dict[uuid.UUID, tuple[uuid.UUID, str]] = {}
    if teacher_ids:
        rows = (
            await session.execute(
                select(
                    TeacherSubjectMapping.teacher_id,
                    Subject.id,
                    Subject.name,
                )
                .join(Subject, Subject.id == TeacherSubjectMapping.subject_id)
                .where(
                    TeacherSubjectMapping.teacher_id.in_(teacher_ids),
                    TeacherSubjectMapping.is_deleted == False,
                )
            )
        ).all()
        for tid, sid, sname in rows:
            subject_by_teacher.setdefault(tid, (sid, sname))

    cutoff = datetime.now(timezone.utc) - timedelta(days=30)

    # Lectures-30d + substitution rate: bucket by the effective teacher.
    lectures_count: dict[uuid.UUID, int] = {}
    sub_count: dict[uuid.UUID, int] = {}
    if teacher_ids:
        rows = (
            await session.execute(
                select(
                    Lecture.teacher_id,
                    Lecture.actual_teacher_id,
                ).where(
                    Lecture.is_deleted == False,
                    Lecture.lecture_status == "completed",
                    Lecture.scheduled_start >= cutoff,
                    Lecture.branch_id == branch_id,
                )
            )
        ).all()
        for planned, actual in rows:
            effective = actual or planned
            if effective in teacher_ids:
                lectures_count[effective] = lectures_count.get(effective, 0) + 1
                if actual is not None and actual != planned:
                    sub_count[effective] = sub_count.get(effective, 0) + 1

    # Avg test percentage (directional outcome) — by teacher's primary
    # subject, last 30 days.
    avg_outcome: dict[uuid.UUID, float] = {}
    subject_ids = [v[0] for v in subject_by_teacher.values()]
    if subject_ids:
        rows = (
            await session.execute(
                select(
                    Test.subject_id,
                    func.avg(StudentMark.percentage),
                )
                .join(StudentMark, StudentMark.test_id == Test.id)
                .where(
                    Test.subject_id.in_(subject_ids),
                    Test.is_deleted == False,
                    Test.branch_id == branch_id,
                    StudentMark.is_absent == False,
                    StudentMark.is_deleted == False,
                    Test.created_at >= cutoff,
                )
                .group_by(Test.subject_id)
            )
        ).all()
        avg_by_subject = {sid: float(avg or 0.0) for sid, avg in rows}
        for tid, (sid, _name) in subject_by_teacher.items():
            if sid in avg_by_subject:
                avg_outcome[tid] = round(avg_by_subject[sid], 1)

    out: list[dict] = []
    for t in teachers:
        sid, sname = subject_by_teacher.get(t.id, (None, None))
        total = lectures_count.get(t.id, 0)
        subs = sub_count.get(t.id, 0)
        out.append({
            "id": t.id,
            "first_name": t.first_name,
            "last_name": t.last_name,
            "qualification": t.qualification,
            "years_experience": t.years_experience,
            "subject_id": sid,
            "subject_name": sname,
            "lectures_30d": total,
            "sub_rate_pct": round(100.0 * subs / total, 1) if total > 0 else 0.0,
            "avg_outcome_delta_pp": avg_outcome.get(t.id),
        })
    return out


async def add_subject_mappings(
    session: AsyncSession,
    teacher_id: uuid.UUID,
    branch_id: uuid.UUID,
    subject_ids: list[uuid.UUID],
) -> None:
    for subject_id in subject_ids:
        session.add(
            TeacherSubjectMapping(
                teacher_id=teacher_id,
                subject_id=subject_id,
                branch_id=branch_id,
            )
        )
    await session.flush()
