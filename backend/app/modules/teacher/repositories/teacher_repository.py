import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.teacher.models.teacher_models import (
    Teacher,
    TeacherLeave,
    TeacherSubjectMapping,
)


def _same_name_subject_ids(
    subject_id: uuid.UUID, branch_id: uuid.UUID | None = None
):
    """Scalar subquery of subject ids in the branch that share ``subject_id``'s
    NAME.

    A subject name (e.g. "Chemistry") is carried by one Subject row per course,
    so prod has many "Chemistry" rows. Teacher qualifications and the schedule
    treat the *name* as the unit, but a slot's subject dropdown collapses the
    name to one arbitrary id. Matching teacher mappings by name across sibling
    rows means a teacher qualified for any "Chemistry" is offered for every
    "Chemistry" — the same fix applied to the question bank. Mirrors the
    branch-wide semantic without depending on which duplicate id was picked.

    When ``branch_id`` is given it scopes directly; otherwise the branch is
    derived from ``subject_id`` (for call sites without a branch in hand)."""
    from app.modules.academic.models.academic_models import Subject

    name_subq = (
        select(Subject.name).where(Subject.id == subject_id).scalar_subquery()
    )
    conds = [Subject.name == name_subq, Subject.is_deleted == False]  # noqa: E712
    if branch_id is not None:
        conds.append(Subject.branch_id == branch_id)
    else:
        branch_subq = (
            select(Subject.branch_id)
            .where(Subject.id == subject_id)
            .scalar_subquery()
        )
        conds.append(Subject.branch_id == branch_subq)
    return select(Subject.id).where(*conds).scalar_subquery()


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


# --- Teacher leave (S5) -----------------------------------------------------

async def list_leaves(
    session: AsyncSession, branch_id: uuid.UUID, teacher_id: uuid.UUID | None = None
) -> list[TeacherLeave]:
    query = select(TeacherLeave).where(
        TeacherLeave.branch_id == branch_id,
        TeacherLeave.is_deleted == False,
    )
    if teacher_id is not None:
        query = query.where(TeacherLeave.teacher_id == teacher_id)
    result = await session.execute(query.order_by(TeacherLeave.start_date))
    return list(result.scalars().all())


async def get_leave_by_id(
    session: AsyncSession, leave_id: uuid.UUID
) -> TeacherLeave | None:
    result = await session.execute(
        select(TeacherLeave).where(
            TeacherLeave.id == leave_id, TeacherLeave.is_deleted == False
        )
    )
    return result.scalar_one_or_none()


async def create_leave(session: AsyncSession, **kwargs) -> TeacherLeave:
    leave = TeacherLeave(**kwargs)
    session.add(leave)
    await session.flush()
    return leave


async def soft_delete_leave(session: AsyncSession, leave: TeacherLeave) -> None:
    leave.is_deleted = True
    await session.flush()


async def teacher_on_leave(
    session: AsyncSession, teacher_id: uuid.UUID, on_date
) -> bool:
    """Whether the teacher has an active leave covering ``on_date`` (inclusive)."""
    result = await session.execute(
        select(TeacherLeave.id).where(
            TeacherLeave.teacher_id == teacher_id,
            TeacherLeave.is_deleted == False,
            TeacherLeave.start_date <= on_date,
            TeacherLeave.end_date >= on_date,
        )
    )
    return result.first() is not None


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


async def teacher_teaches_subject(
    session: AsyncSession,
    teacher_id: uuid.UUID,
    subject_id: uuid.UUID,
) -> bool:
    """Whether an active TeacherSubjectMapping links this teacher to this
    subject. The single source of truth for the Subject→Teacher lock — both
    the schedule form's dropdown filter and the backend write-path validation
    resolve through here."""
    result = await session.execute(
        select(TeacherSubjectMapping.id)
        .where(
            TeacherSubjectMapping.teacher_id == teacher_id,
            # Match across same-named sibling subject rows (per-course
            # duplicates) so the lock isn't defeated by which "Chemistry" id
            # the schedule slot happened to pick.
            TeacherSubjectMapping.subject_id.in_(_same_name_subject_ids(subject_id)),
            TeacherSubjectMapping.is_deleted == False,  # noqa: E712
        )
        .limit(1)
    )
    return result.scalar_one_or_none() is not None


async def list_subject_ids_for_teacher(
    session: AsyncSession, teacher_id: uuid.UUID
) -> list[uuid.UUID]:
    """Active subject IDs a teacher is assigned to."""
    result = await session.execute(
        select(TeacherSubjectMapping.subject_id).where(
            TeacherSubjectMapping.teacher_id == teacher_id,
            TeacherSubjectMapping.is_deleted == False,  # noqa: E712
        )
    )
    return [r[0] for r in result.all()]


async def set_subject_mappings(
    session: AsyncSession,
    teacher_id: uuid.UUID,
    branch_id: uuid.UUID,
    subject_ids: list[uuid.UUID],
) -> None:
    """Replace a teacher's subject assignments with ``subject_ids`` (a delta:
    existing rows that survive are kept, removed ones are soft-deleted, new ones
    added). Idempotent — re-applying the same set is a no-op."""
    keep = set(subject_ids)
    result = await session.execute(
        select(TeacherSubjectMapping).where(
            TeacherSubjectMapping.teacher_id == teacher_id,
            TeacherSubjectMapping.is_deleted == False,  # noqa: E712
        )
    )
    have: set[uuid.UUID] = set()
    for mapping in result.scalars().all():
        if mapping.subject_id in keep:
            have.add(mapping.subject_id)
        else:
            mapping.is_deleted = True
    for sid in keep:
        if sid not in have:
            session.add(
                TeacherSubjectMapping(
                    teacher_id=teacher_id,
                    subject_id=sid,
                    branch_id=branch_id,
                )
            )
    await session.flush()


async def list_for_subject(
    session: AsyncSession,
    branch_id: uuid.UUID,
    subject_id: uuid.UUID,
) -> list[Teacher]:
    """Active teachers in the branch assigned to teach ``subject_id``.

    Powers the schedule form's teacher dropdown so a wrong-subject teacher is
    never even offered (the backend still validates on save — UI filtering is
    convenience, not the guarantee)."""
    result = await session.execute(
        select(Teacher)
        .join(
            TeacherSubjectMapping,
            TeacherSubjectMapping.teacher_id == Teacher.id,
        )
        .where(
            Teacher.branch_id == branch_id,
            Teacher.is_deleted == False,  # noqa: E712
            # Offer every teacher qualified for any same-named subject row in
            # the branch, not just the one duplicate id the slot selected.
            TeacherSubjectMapping.subject_id.in_(
                _same_name_subject_ids(subject_id, branch_id)
            ),
            TeacherSubjectMapping.is_deleted == False,  # noqa: E712
        )
        .order_by(Teacher.first_name, Teacher.last_name)
    )
    return list(result.scalars().unique().all())


async def list_active(
    session: AsyncSession, branch_id: uuid.UUID
) -> list[Teacher]:
    """Every active teacher in the branch, regardless of subject. Powers the
    cross-subject substitute picker, where any available teacher may cover a
    class (the same-subject lock is opt-out there, not enforced)."""
    result = await session.execute(
        select(Teacher)
        .where(
            Teacher.branch_id == branch_id,
            Teacher.is_deleted == False,  # noqa: E712
        )
        .order_by(Teacher.first_name, Teacher.last_name)
    )
    return list(result.scalars().unique().all())


async def subject_names_for_teachers(
    session: AsyncSession, teacher_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[str]]:
    """{teacher_id: [subject name, …]} for the given teachers (active mappings),
    de-duplicated by name so per-course sibling rows collapse to one label. Used
    to show a cross-subject candidate's own subject(s) in the picker."""
    from app.modules.academic.models.academic_models import Subject

    if not teacher_ids:
        return {}
    result = await session.execute(
        select(TeacherSubjectMapping.teacher_id, Subject.name)
        .join(Subject, Subject.id == TeacherSubjectMapping.subject_id)
        .where(
            TeacherSubjectMapping.teacher_id.in_(teacher_ids),
            TeacherSubjectMapping.is_deleted == False,  # noqa: E712
            Subject.is_deleted == False,  # noqa: E712
        )
    )
    out: dict[uuid.UUID, list[str]] = {}
    for teacher_id, name in result.all():
        names = out.setdefault(teacher_id, [])
        if name not in names:
            names.append(name)
    for names in out.values():
        names.sort()
    return out
