import uuid

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.services import audit_service
from app.modules.staff.models.staff_models import DEPARTMENT_SEED, Department, Staff
from app.modules.staff.repositories import staff_repository
from app.modules.staff.schemas.staff_schemas import StaffCreate, StaffUpdate


async def ensure_departments(session: AsyncSession, branch_id: uuid.UUID) -> None:
    """Seed the six canonical departments for a branch that has none yet.

    Idempotent: no-op once they exist. Covers branches created after migration
    0056 (which seeds only the branches present at upgrade time)."""
    existing = await staff_repository.list_departments(session, branch_id)
    if existing:
        return
    for name, start, end in DEPARTMENT_SEED:
        session.add(
            Department(
                branch_id=branch_id, name=name, id_range_start=start, id_range_end=end
            )
        )
    await session.flush()


def _code_in_range(emp_code: str, dept: Department) -> bool:
    """Whether a numeric emp_code sits inside the department's reserved range.
    Non-numeric codes are treated as out-of-range (legacy)."""
    try:
        n = int(emp_code)
    except (TypeError, ValueError):
        return False
    return dept.id_range_start <= n <= dept.id_range_end


def next_emp_code(existing_codes: list[str], dept: Department) -> str | None:
    """The next free code inside ``[id_range_start, id_range_end]``.

    = max(existing numeric code within range) + 1, or ``id_range_start`` when
    none are in range yet. Returns None when the range is exhausted. Legacy
    out-of-range codes are ignored, so they never block allocation."""
    in_range = [
        n
        for c in existing_codes
        if (n := _to_int(c)) is not None and dept.id_range_start <= n <= dept.id_range_end
    ]
    candidate = (max(in_range) + 1) if in_range else dept.id_range_start
    if candidate > dept.id_range_end:
        return None
    return str(candidate)


def _to_int(value: str) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


async def allocate_emp_code(
    session: AsyncSession, branch_id: uuid.UUID, dept: Department
) -> str:
    existing = await staff_repository.emp_codes_in_department(
        session, branch_id, dept.id
    )
    code = next_emp_code(existing, dept)
    if code is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Department '{dept.name}' code range "
                f"{dept.id_range_start}–{dept.id_range_end} is full"
            ),
        )
    return code


async def list_departments(session: AsyncSession, branch_id: uuid.UUID):
    """Departments + range-fill so the create dialog can preview the next ID."""
    await ensure_departments(session, branch_id)
    depts = await staff_repository.list_departments(session, branch_id)
    out = []
    for d in depts:
        codes = await staff_repository.emp_codes_in_department(session, branch_id, d.id)
        in_range = [
            n for c in codes
            if (n := _to_int(c)) is not None and d.id_range_start <= n <= d.id_range_end
        ]
        out.append({
            "id": d.id,
            "branch_id": d.branch_id,
            "name": d.name,
            "id_range_start": d.id_range_start,
            "id_range_end": d.id_range_end,
            "used": len(in_range),
            "next_emp_code": next_emp_code(codes, d),
        })
    return out


async def _department_name(session: AsyncSession, department_id: uuid.UUID) -> str | None:
    dept = await staff_repository.get_department(session, department_id)
    return dept.name if dept else None


async def _to_response(session: AsyncSession, staff: Staff) -> dict:
    return {
        **{k: getattr(staff, k) for k in (
            "id", "branch_id", "emp_code", "title", "first_name", "last_name",
            "department_id", "designation", "linked_teacher_id", "email", "phone",
            "is_legacy_code", "shift_start", "shift_end", "weekly_off_days", "status",
        )},
        "department_name": await _department_name(session, staff.department_id),
    }


async def create_staff(
    session: AsyncSession,
    data: StaffCreate,
    current_user_id: uuid.UUID,
    ip_address: str | None = None,
) -> dict:
    dept = await staff_repository.get_department(session, data.department_id)
    if not dept or dept.branch_id != data.branch_id:
        raise HTTPException(status_code=404, detail="Department not found")

    is_legacy = False
    if data.emp_code:
        emp_code = data.emp_code.strip()
        existing = await staff_repository.get_by_emp_code(
            session, data.branch_id, emp_code
        )
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Employee code {emp_code} already in use",
            )
        is_legacy = not _code_in_range(emp_code, dept)
    else:
        emp_code = await allocate_emp_code(session, data.branch_id, dept)

    payload = data.model_dump(exclude={"emp_code"})
    staff = await staff_repository.create(
        session, **payload, emp_code=emp_code, is_legacy_code=is_legacy
    )
    await audit_service.log_action(
        session,
        user_id=current_user_id,
        action="CREATE",
        table_name="staff",
        record_id=staff.id,
        new_values={**data.model_dump(mode="json"), "emp_code": emp_code},
        ip_address=ip_address,
        branch_id=data.branch_id,
    )
    return await _to_response(session, staff)


async def get_staff(session: AsyncSession, staff_id: uuid.UUID, branch_id: uuid.UUID) -> dict:
    staff = await _load_scoped(session, staff_id, branch_id)
    return await _to_response(session, staff)


async def list_staff(
    session: AsyncSession,
    branch_id: uuid.UUID,
    department_id: uuid.UUID | None = None,
) -> list[dict]:
    rows = await staff_repository.list_by_branch(session, branch_id, department_id)
    names = {
        d.id: d.name for d in await staff_repository.list_departments(session, branch_id)
    }
    return [
        {
            **{k: getattr(s, k) for k in (
                "id", "branch_id", "emp_code", "title", "first_name", "last_name",
                "department_id", "designation", "linked_teacher_id", "email", "phone",
                "is_legacy_code", "shift_start", "shift_end", "weekly_off_days", "status",
            )},
            "department_name": names.get(s.department_id),
        }
        for s in rows
    ]


async def _load_scoped(
    session: AsyncSession, staff_id: uuid.UUID, branch_id: uuid.UUID
) -> Staff:
    staff = await staff_repository.get_by_id(session, staff_id)
    if not staff:
        raise HTTPException(status_code=404, detail="Staff not found")
    if staff.branch_id != branch_id:
        raise HTTPException(status_code=403, detail="No access to this branch")
    return staff


async def update_staff(
    session: AsyncSession,
    staff_id: uuid.UUID,
    data: StaffUpdate,
    branch_id: uuid.UUID,
    current_user_id: uuid.UUID,
    ip_address: str | None = None,
) -> dict:
    staff = await _load_scoped(session, staff_id, branch_id)
    update_data = data.model_dump(exclude_unset=True)

    # Re-validate emp_code (uniqueness + legacy flag against the target dept).
    if "emp_code" in update_data and update_data["emp_code"]:
        new_code = update_data["emp_code"].strip()
        if new_code != staff.emp_code:
            clash = await staff_repository.get_by_emp_code(session, branch_id, new_code)
            if clash is not None and clash.id != staff.id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Employee code {new_code} already in use",
                )
        dept_id = update_data.get("department_id", staff.department_id)
        dept = await staff_repository.get_department(session, dept_id)
        update_data["emp_code"] = new_code
        update_data["is_legacy_code"] = not (dept and _code_in_range(new_code, dept))

    staff = await staff_repository.update(session, staff, **update_data)
    await audit_service.log_action(
        session,
        user_id=current_user_id,
        action="UPDATE",
        table_name="staff",
        record_id=staff.id,
        new_values=data.model_dump(mode="json", exclude_unset=True),
        ip_address=ip_address,
        branch_id=branch_id,
    )
    return await _to_response(session, staff)


async def link_teacher(
    session: AsyncSession,
    staff_id: uuid.UUID,
    teacher_id: uuid.UUID | None,
    branch_id: uuid.UUID,
    current_user_id: uuid.UUID,
    ip_address: str | None = None,
) -> dict:
    """Link (or unlink, teacher_id=None) a staff row to a teacher so lectures can
    be joined for the Faculty Activity Report."""
    staff = await _load_scoped(session, staff_id, branch_id)
    if teacher_id is not None:
        from app.modules.teacher.repositories import teacher_repository

        teacher = await teacher_repository.get_by_id(session, teacher_id)
        if not teacher or teacher.branch_id != branch_id:
            raise HTTPException(status_code=404, detail="Teacher not found")
    staff = await staff_repository.update(session, staff, linked_teacher_id=teacher_id)
    await audit_service.log_action(
        session,
        user_id=current_user_id,
        action="UPDATE",
        table_name="staff",
        record_id=staff.id,
        new_values={"linked_teacher_id": str(teacher_id) if teacher_id else None},
        ip_address=ip_address,
        branch_id=branch_id,
    )
    return await _to_response(session, staff)


async def delete_staff(
    session: AsyncSession,
    staff_id: uuid.UUID,
    branch_id: uuid.UUID,
    current_user_id: uuid.UUID,
    ip_address: str | None = None,
) -> None:
    staff = await _load_scoped(session, staff_id, branch_id)
    await staff_repository.soft_delete(session, staff)
    await audit_service.log_action(
        session,
        user_id=current_user_id,
        action="DELETE",
        table_name="staff",
        record_id=staff.id,
        old_values={"emp_code": staff.emp_code, "first_name": staff.first_name},
        ip_address=ip_address,
        branch_id=branch_id,
    )


async def bulk_delete_staff(
    session: AsyncSession,
    branch_id: uuid.UUID,
    staff_ids: list[uuid.UUID],
    current_user_id: uuid.UUID,
    ip_address: str | None = None,
) -> dict[str, int]:
    if not staff_ids:
        return {"deleted": 0}
    valid_ids = list(
        (
            await session.execute(
                select(Staff.id).where(
                    Staff.id.in_(staff_ids),
                    Staff.branch_id == branch_id,
                    Staff.is_deleted == False,  # noqa: E712
                )
            )
        ).scalars().all()
    )
    if not valid_ids:
        return {"deleted": 0}
    await session.execute(
        update(Staff).where(Staff.id.in_(valid_ids)).values(is_deleted=True)
    )
    await audit_service.log_action(
        session,
        user_id=current_user_id,
        action="DELETE",
        table_name="staff",
        record_id=valid_ids[0],
        new_values={"bulk_deleted": [str(i) for i in valid_ids]},
        ip_address=ip_address,
        branch_id=branch_id,
    )
    return {"deleted": len(valid_ids)}
