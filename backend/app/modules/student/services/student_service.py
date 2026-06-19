import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.services import audit_service
from app.modules.student.repositories import student_repository
from app.modules.student.schemas.student_schemas import StudentCreate, StudentUpdate

# Enrolment validations. Drives the /students/[id] cohort segmentation
# and the future at-risk / topic-mastery analytics.
VALID_STANDARDS = {"9", "10", "11", "12", "Dropper"}
VALID_TARGET_EXAMS = {
    "NEET",
    "JEE-Main",
    "JEE-Advanced",
    "MHT-CET",    # Maharashtra state engineering / pharmacy entrance
    "Both",       # NEET + JEE dual-prep
    "Foundation", # Class 9/10 foundation programs
    "Other",
}


# Streams a student can opt into for their target exam. Decides which subjects
# they actually sit (Physics/Chemistry common to all; Maths PCM-only; Biology
# PCB-only).
VALID_STREAMS = {"PCM", "PCB", "PCMB"}

# Default stream from target when the admin leaves Stream blank. MHT-CET falls
# back to PCB (most students); the few PCM ones get flagged/overridden.
DEFAULT_STREAM_FOR_TARGET = {
    "NEET": "PCB",
    "JEE-Main": "PCM",
    "JEE-Advanced": "PCM",
    "Both": "PCMB",
    "MHT-CET": "PCB",
}

# Subject-name families used to filter a course's subjects down to the ones a
# given stream actually sits.
_COMMON_SUBJECTS = {"physics", "chemistry"}
_MATHS_SUBJECTS = {"mathematics", "maths"}
_BIO_SUBJECTS = {"biology", "botany", "zoology"}


def default_stream(target_exam: str | None) -> str | None:
    return DEFAULT_STREAM_FOR_TARGET.get(target_exam or "")


def stream_includes_subject(stream: str | None, subject_name: str) -> bool:
    """Whether a student on ``stream`` sits ``subject_name``. Physics/Chemistry
    are common; Maths is PCM/PCMB; Biology (incl. Botany/Zoology) is PCB/PCMB.
    Unknown stream or unrecognized subject -> not filtered out."""
    if not stream:
        return True
    name = subject_name.strip().lower()
    s = stream.strip().upper()
    if name in _COMMON_SUBJECTS:
        return True
    if name in _MATHS_SUBJECTS:
        return s in {"PCM", "PCMB"}
    if name in _BIO_SUBJECTS:
        return s in {"PCB", "PCMB"}
    return True


def _validate_stream(stream: str | None):
    if stream is not None and stream not in VALID_STREAMS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid stream '{stream}'. Allowed: {sorted(VALID_STREAMS)}",
        )


def _validate_enrolment_fields(standard: str | None, target_exam: str | None):
    if standard is not None and standard not in VALID_STANDARDS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Invalid standard '{standard}'. "
                f"Allowed: {sorted(VALID_STANDARDS)}"
            ),
        )
    if target_exam is not None and target_exam not in VALID_TARGET_EXAMS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Invalid target_exam '{target_exam}'. "
                f"Allowed: {sorted(VALID_TARGET_EXAMS)}"
            ),
        )


async def create_student(
    session: AsyncSession,
    data: StudentCreate,
    current_user_id: uuid.UUID,
    ip_address: str | None = None,
):
    _validate_enrolment_fields(data.standard, data.target_exam)
    _validate_stream(data.stream)
    payload = data.model_dump()
    # Single-student form: default the stream from target when left blank.
    if not payload.get("stream"):
        payload["stream"] = default_stream(data.target_exam)
    student = await student_repository.create(session, **payload)

    await audit_service.log_action(
        session,
        user_id=current_user_id,
        action="CREATE",
        table_name="students",
        record_id=student.id,
        new_values=payload,
        ip_address=ip_address,
        branch_id=data.branch_id,
    )
    return student


async def get_student(
    session: AsyncSession, student_id: uuid.UUID, branch_id: uuid.UUID
):
    student = await student_repository.get_by_id(session, student_id)
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")
    if student.branch_id != branch_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this branch")
    return student


async def list_students(session: AsyncSession, branch_id: uuid.UUID, offset: int = 0, limit: int = 50):
    return await student_repository.list_by_branch(session, branch_id, offset, limit)


# Sort keys the roster supports → how to read them off a computed stats row.
_STATS_SORT_KEYS = {
    "name": lambda r: (
        (r.get("first_name") or "").lower(),
        (r.get("last_name") or "").lower(),
    ),
    "avg_score_pct": lambda r: r.get("avg_score_pct") or 0.0,
    "attendance_pct": lambda r: r.get("attendance_pct") or 0.0,
    "dpp_completion_pct": lambda r: r.get("dpp_completion_pct") or 0.0,
    "tests_taken": lambda r: r.get("tests_taken") or 0,
    # Rank: missing (no batch) sorts last regardless of direction.
    "batch_rank": lambda r: (r.get("batch_rank") is None, r.get("batch_rank") or 0),
}


async def list_students_with_stats(session: AsyncSession, branch_id: uuid.UUID):
    """Full branch roster with stats — used where the whole set is needed
    (attendance batch roster, a student's batch-rank context)."""
    return await student_repository.list_with_stats(session, branch_id)


async def list_students_roster(
    session: AsyncSession,
    branch_id: uuid.UUID,
    offset: int = 0,
    limit: int = 50,
    search: str = "",
    sort_by: str = "name",
    order: str = "asc",
):
    """One page of the roster. Stats (incl. batch rank) are computed across the
    whole branch for correctness, then the result is searched, sorted, and
    sliced — so the client only ships/renders a page, not thousands of rows."""
    rows = await student_repository.list_with_stats(session, branch_id)

    q = search.strip().lower()
    if q:
        rows = [
            r
            for r in rows
            if q in f"{r['first_name']} {r['last_name']}".lower()
            or q in (r.get("enrollment_number") or "").lower()
        ]

    key = _STATS_SORT_KEYS.get(sort_by, _STATS_SORT_KEYS["name"])
    # 'name' ascending is the natural default; numeric stats are usually most
    # useful high-to-low, but we honour whatever the client asks.
    rows.sort(key=key, reverse=(order == "desc"))

    total = len(rows)
    page = rows[max(offset, 0) : max(offset, 0) + max(limit, 0)]
    return {"items": page, "total": total}


async def get_test_history(
    session: AsyncSession, student_id: uuid.UUID, branch_id: uuid.UUID
):
    # Ownership check — surfaces 404 the same way get_student does.
    await get_student(session, student_id, branch_id)
    return await student_repository.get_test_history(session, student_id, branch_id)


async def get_topic_mastery(
    session: AsyncSession, student_id: uuid.UUID, branch_id: uuid.UUID
):
    # Ownership check — surfaces 404 the same way get_student does.
    await get_student(session, student_id, branch_id)
    return await student_repository.get_topic_mastery(session, student_id, branch_id)


async def get_upcoming_tests(
    session: AsyncSession, student_id: uuid.UUID, branch_id: uuid.UUID
):
    # Ownership check — surfaces 404 the same way get_student does.
    await get_student(session, student_id, branch_id)
    return await student_repository.get_upcoming_tests(session, student_id, branch_id)


async def delete_all_students(
    session: AsyncSession,
    branch_id: uuid.UUID,
    current_user_id: uuid.UUID,
    ip_address: str | None = None,
) -> dict[str, int]:
    """Soft-delete every active student in the branch (and their batch
    mappings). Batches, courses, subjects and curriculum are left intact, so a
    re-import recreates students against the existing structure. Recoverable —
    rows stay with is_deleted=true."""
    from sqlalchemy import func, select, update

    from app.modules.student.models.student_models import (
        Student,
        StudentBatchMapping,
    )

    count = (
        await session.execute(
            select(func.count())
            .select_from(Student)
            .where(
                Student.branch_id == branch_id,
                Student.is_deleted == False,  # noqa: E712
            )
        )
    ).scalar_one()

    if count:
        await session.execute(
            update(Student)
            .where(
                Student.branch_id == branch_id,
                Student.is_deleted == False,  # noqa: E712
            )
            .values(is_deleted=True)
        )
        await session.execute(
            update(StudentBatchMapping)
            .where(
                StudentBatchMapping.branch_id == branch_id,
                StudentBatchMapping.is_deleted == False,  # noqa: E712
            )
            .values(is_deleted=True)
        )

    await audit_service.log_action(
        session,
        user_id=current_user_id,
        action="DELETE_ALL",
        table_name="students",
        record_id=uuid.uuid4(),
        new_values={"deleted": int(count)},
        ip_address=ip_address,
        branch_id=branch_id,
    )
    return {"deleted": int(count)}


async def get_student_syllabus(
    session: AsyncSession, student_id: uuid.UUID, branch_id: uuid.UUID
):
    """The student's accountable syllabus: the subjects of their batch's course,
    filtered to the ones their stream actually sits, with how much curriculum is
    loaded for each."""
    from sqlalchemy import select

    from app.modules.academic.repositories import academic_repository
    from app.modules.batch.models.batch_models import Batch
    from app.modules.student.models.student_models import StudentBatchMapping

    student = await get_student(session, student_id, branch_id)

    batch_id = (
        await session.execute(
            select(StudentBatchMapping.batch_id)
            .where(
                StudentBatchMapping.student_id == student_id,
                StudentBatchMapping.is_deleted == False,  # noqa: E712
            )
            .limit(1)
        )
    ).scalar_one_or_none()

    course_id = None
    if batch_id is not None:
        course_id = (
            await session.execute(select(Batch.course_id).where(Batch.id == batch_id))
        ).scalar_one_or_none()

    subjects_out: list[dict] = []
    if course_id is not None:
        subjects = await academic_repository.list_subjects(
            session, branch_id, course_id
        )
        for subj in subjects:
            if not stream_includes_subject(student.stream, subj.name):
                continue
            chapters = await academic_repository.list_chapters(
                session, branch_id, subj.id
            )
            topics = await academic_repository.list_topics_by_subject(
                session, branch_id, subj.id
            )
            subjects_out.append(
                {
                    "subject_id": subj.id,
                    "subject_name": subj.name,
                    "chapter_count": len(chapters),
                    "topic_count": len(topics),
                }
            )

    return {
        "student_id": student_id,
        "stream": student.stream,
        "course_id": course_id,
        "subjects": subjects_out,
    }


async def update_student(
    session: AsyncSession,
    student_id: uuid.UUID,
    data: StudentUpdate,
    branch_id: uuid.UUID,
    current_user_id: uuid.UUID,
    ip_address: str | None = None,
):
    student = await student_repository.get_by_id(session, student_id)
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")
    if student.branch_id != branch_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this branch")

    old_values = {
        "first_name": student.first_name,
        "last_name": student.last_name,
        "email": student.email,
        "phone": student.phone,
    }

    update_data = data.model_dump(exclude_unset=True)
    _validate_enrolment_fields(
        update_data.get("standard"), update_data.get("target_exam")
    )
    _validate_stream(update_data.get("stream"))
    student = await student_repository.update(session, student, **update_data)

    await audit_service.log_action(
        session,
        user_id=current_user_id,
        action="UPDATE",
        table_name="students",
        record_id=student.id,
        old_values=old_values,
        new_values=update_data,
        ip_address=ip_address,
        branch_id=branch_id,
    )
    return student


async def delete_student(
    session: AsyncSession,
    student_id: uuid.UUID,
    branch_id: uuid.UUID,
    current_user_id: uuid.UUID,
    ip_address: str | None = None,
):
    student = await student_repository.get_by_id(session, student_id)
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")
    if student.branch_id != branch_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this branch")

    await student_repository.soft_delete(session, student)

    await audit_service.log_action(
        session,
        user_id=current_user_id,
        action="DELETE",
        table_name="students",
        record_id=student.id,
        old_values={"first_name": student.first_name, "last_name": student.last_name},
        ip_address=ip_address,
        branch_id=branch_id,
    )
