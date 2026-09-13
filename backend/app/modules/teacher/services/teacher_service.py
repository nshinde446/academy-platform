import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.academic.repositories import academic_repository
from app.modules.audit.services import audit_service
from app.modules.teacher.repositories import teacher_repository
from app.modules.teacher.schemas.teacher_schemas import TeacherCreate, TeacherUpdate


async def _resolve_subject_ids(
    session: AsyncSession, branch_id: uuid.UUID, names: list[str]
) -> list[uuid.UUID]:
    """Subject names → every matching subject row's id (a name can repeat across
    courses, e.g. JEE Physics and NEET Physics)."""
    subjects = await academic_repository.find_subjects_by_names(
        session, branch_id, names
    )
    return [s.id for s in subjects]


async def create_teacher(
    session: AsyncSession,
    data: TeacherCreate,
    current_user_id: uuid.UUID,
    ip_address: str | None = None,
):
    payload = data.model_dump(exclude={"subjects"})
    teacher = await teacher_repository.create(session, **payload)
    # Assign subjects up front so the teacher is schedulable immediately
    # (Subject→Teacher lock). Unknown names are simply ignored here; the
    # /subjects editor surfaces the available options.
    if data.subjects:
        subject_ids = await _resolve_subject_ids(
            session, data.branch_id, data.subjects
        )
        if subject_ids:
            await teacher_repository.set_subject_mappings(
                session, teacher.id, data.branch_id, subject_ids
            )
    await audit_service.log_action(
        session,
        user_id=current_user_id,
        action="CREATE",
        table_name="teachers",
        record_id=teacher.id,
        new_values=data.model_dump(),
        ip_address=ip_address,
        branch_id=data.branch_id,
    )
    # Auto-mirror the teacher into the Staff roster (MSA-Teachers, 9xxxx code)
    # so staff attendance/reports have them immediately. Idempotent and
    # best-effort — a sync hiccup must never fail teacher creation. Lazy import
    # avoids a teacher<->staff module import cycle.
    try:
        from app.modules.staff.services import staff_service

        await staff_service.sync_teachers_to_staff(
            session, data.branch_id, current_user_id, ip_address
        )
    except Exception:  # noqa: BLE001 — never block teacher creation on the mirror
        pass
    return teacher


async def list_subject_options(
    session: AsyncSession, branch_id: uuid.UUID
) -> list[str]:
    """Distinct subject names in the branch — the assignable-subjects picker."""
    subjects = await academic_repository.list_subjects(session, branch_id)
    return sorted({s.name for s in subjects}, key=str.lower)


async def get_teacher_subjects(
    session: AsyncSession, teacher_id: uuid.UUID, branch_id: uuid.UUID
) -> list[str]:
    teacher = await teacher_repository.get_by_id(session, teacher_id)
    if not teacher:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Teacher not found")
    if teacher.branch_id != branch_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this branch")
    ids = await teacher_repository.list_subject_ids_for_teacher(session, teacher_id)
    if not ids:
        return []
    subjects = await academic_repository.list_subjects(session, branch_id)
    by_id = {s.id: s.name for s in subjects}
    return sorted({by_id[i] for i in ids if i in by_id}, key=str.lower)


async def set_teacher_subjects(
    session: AsyncSession,
    teacher_id: uuid.UUID,
    branch_id: uuid.UUID,
    subject_names: list[str],
    current_user_id: uuid.UUID,
    ip_address: str | None = None,
) -> list[str]:
    """Replace a teacher's subject assignments (by name). Returns the resolved
    distinct names actually applied."""
    teacher = await teacher_repository.get_by_id(session, teacher_id)
    if not teacher:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Teacher not found")
    if teacher.branch_id != branch_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this branch")

    subject_ids = await _resolve_subject_ids(session, branch_id, subject_names)
    await teacher_repository.set_subject_mappings(
        session, teacher_id, branch_id, subject_ids
    )
    await audit_service.log_action(
        session,
        user_id=current_user_id,
        action="UPDATE",
        table_name="teacher_subject_mappings",
        record_id=teacher_id,
        new_values={"subjects": subject_names},
        ip_address=ip_address,
        branch_id=branch_id,
    )
    return await get_teacher_subjects(session, teacher_id, branch_id)


async def _staff_no_map(
    session: AsyncSession, branch_id: uuid.UUID, teacher_ids: list[uuid.UUID]
) -> dict[uuid.UUID, str]:
    """{teacher_id: linked staff emp_code}. Lazy import keeps teacher decoupled
    from staff at module load."""
    from app.modules.staff.repositories import staff_repository

    return await staff_repository.emp_code_by_linked_teacher(
        session, branch_id, teacher_ids
    )


async def get_teacher(session: AsyncSession, teacher_id: uuid.UUID, branch_id: uuid.UUID):
    teacher = await teacher_repository.get_by_id(session, teacher_id)
    if not teacher:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Teacher not found")
    if teacher.branch_id != branch_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this branch")
    teacher.staff_no = (await _staff_no_map(session, branch_id, [teacher.id])).get(teacher.id)
    return teacher


async def list_teachers(session: AsyncSession, branch_id: uuid.UUID, offset: int = 0, limit: int = 50):
    teachers = await teacher_repository.list_by_branch(session, branch_id, offset, limit)
    codes = await _staff_no_map(session, branch_id, [t.id for t in teachers])
    for t in teachers:
        t.staff_no = codes.get(t.id)
    return teachers


async def list_teachers_with_stats(session: AsyncSession, branch_id: uuid.UUID):
    rows = await teacher_repository.list_with_stats(session, branch_id)
    codes = await _staff_no_map(session, branch_id, [r["id"] for r in rows])
    for r in rows:
        r["staff_no"] = codes.get(r["id"])
    return rows


async def list_teachers_for_subject(
    session: AsyncSession, branch_id: uuid.UUID, subject_id: uuid.UUID
):
    """Teachers assigned to a subject — the schedule form's filtered dropdown."""
    return await teacher_repository.list_for_subject(session, branch_id, subject_id)


async def update_teacher(
    session: AsyncSession,
    teacher_id: uuid.UUID,
    data: TeacherUpdate,
    branch_id: uuid.UUID,
    current_user_id: uuid.UUID,
    ip_address: str | None = None,
):
    teacher = await teacher_repository.get_by_id(session, teacher_id)
    if not teacher:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Teacher not found")
    if teacher.branch_id != branch_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this branch")

    old_values = {"first_name": teacher.first_name, "last_name": teacher.last_name, "email": teacher.email}
    update_data = data.model_dump(exclude_unset=True)
    teacher = await teacher_repository.update(session, teacher, **update_data)

    await audit_service.log_action(
        session,
        user_id=current_user_id,
        action="UPDATE",
        table_name="teachers",
        record_id=teacher.id,
        old_values=old_values,
        new_values=update_data,
        ip_address=ip_address,
        branch_id=branch_id,
    )
    return teacher


async def delete_teacher(
    session: AsyncSession,
    teacher_id: uuid.UUID,
    branch_id: uuid.UUID,
    current_user_id: uuid.UUID,
    ip_address: str | None = None,
):
    teacher = await teacher_repository.get_by_id(session, teacher_id)
    if not teacher:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Teacher not found")
    if teacher.branch_id != branch_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this branch")

    await teacher_repository.soft_delete(session, teacher)
    await audit_service.log_action(
        session,
        user_id=current_user_id,
        action="DELETE",
        table_name="teachers",
        record_id=teacher.id,
        old_values={"first_name": teacher.first_name, "last_name": teacher.last_name},
        ip_address=ip_address,
        branch_id=branch_id,
    )


async def bulk_delete_teachers(
    session: AsyncSession,
    branch_id: uuid.UUID,
    teacher_ids: list[uuid.UUID],
    current_user_id: uuid.UUID,
    ip_address: str | None = None,
) -> dict[str, int]:
    """Soft-delete a selected set of teachers (+ their subject/batch mappings).
    Only live teachers in this branch are affected; recoverable like the
    single-row delete."""
    from sqlalchemy import select, update

    from app.modules.teacher.models.teacher_models import (
        Teacher,
        TeacherBatchMapping,
        TeacherSubjectMapping,
    )

    if not teacher_ids:
        return {"deleted": 0}

    valid_ids = list(
        (
            await session.execute(
                select(Teacher.id).where(
                    Teacher.id.in_(teacher_ids),
                    Teacher.branch_id == branch_id,
                    Teacher.is_deleted == False,  # noqa: E712
                )
            )
        ).scalars().all()
    )
    if not valid_ids:
        return {"deleted": 0}

    await session.execute(
        update(Teacher).where(Teacher.id.in_(valid_ids)).values(is_deleted=True)
    )
    for mapping in (TeacherSubjectMapping, TeacherBatchMapping):
        await session.execute(
            update(mapping)
            .where(
                mapping.teacher_id.in_(valid_ids),
                mapping.is_deleted == False,  # noqa: E712
            )
            .values(is_deleted=True)
        )

    await audit_service.log_action(
        session,
        user_id=current_user_id,
        action="DELETE",
        table_name="teachers",
        record_id=valid_ids[0],
        new_values={"bulk_deleted": [str(i) for i in valid_ids]},
        ip_address=ip_address,
        branch_id=branch_id,
    )
    return {"deleted": len(valid_ids)}
