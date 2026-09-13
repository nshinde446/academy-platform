import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.staff.models.staff_models import Department, Staff


# --- Departments ------------------------------------------------------------

async def list_departments(
    session: AsyncSession, branch_id: uuid.UUID
) -> list[Department]:
    result = await session.execute(
        select(Department)
        .where(Department.branch_id == branch_id, Department.is_deleted == False)  # noqa: E712
        .order_by(Department.id_range_start)
    )
    return list(result.scalars().all())


async def get_department(
    session: AsyncSession, department_id: uuid.UUID
) -> Department | None:
    result = await session.execute(
        select(Department).where(
            Department.id == department_id, Department.is_deleted == False  # noqa: E712
        )
    )
    return result.scalar_one_or_none()


# --- Staff ------------------------------------------------------------------

async def create(session: AsyncSession, **kwargs) -> Staff:
    staff = Staff(**kwargs)
    session.add(staff)
    await session.flush()
    return staff


async def get_by_id(session: AsyncSession, staff_id: uuid.UUID) -> Staff | None:
    result = await session.execute(
        select(Staff).where(Staff.id == staff_id, Staff.is_deleted == False)  # noqa: E712
    )
    return result.scalar_one_or_none()


async def get_by_emp_code(
    session: AsyncSession, branch_id: uuid.UUID, emp_code: str
) -> Staff | None:
    result = await session.execute(
        select(Staff).where(
            Staff.branch_id == branch_id,
            Staff.emp_code == emp_code,
            Staff.is_deleted == False,  # noqa: E712
        )
    )
    return result.scalar_one_or_none()


async def list_by_branch(
    session: AsyncSession,
    branch_id: uuid.UUID,
    department_id: uuid.UUID | None = None,
) -> list[Staff]:
    query = select(Staff).where(
        Staff.branch_id == branch_id, Staff.is_deleted == False  # noqa: E712
    )
    if department_id is not None:
        query = query.where(Staff.department_id == department_id)
    result = await session.execute(
        query.order_by(Staff.emp_code)
    )
    return list(result.scalars().all())


async def emp_codes_in_department(
    session: AsyncSession, branch_id: uuid.UUID, department_id: uuid.UUID
) -> list[str]:
    """All live emp_codes for a department — used to compute the next code in
    range. Volume per department is tiny (tens), so Python-side max keeps the
    numeric parse portable across SQLite and Postgres."""
    result = await session.execute(
        select(Staff.emp_code).where(
            Staff.branch_id == branch_id,
            Staff.department_id == department_id,
            Staff.is_deleted == False,  # noqa: E712
        )
    )
    return [r[0] for r in result.all()]


async def emp_code_by_linked_teacher(
    session: AsyncSession, branch_id: uuid.UUID, teacher_ids: list[uuid.UUID]
) -> dict[uuid.UUID, str]:
    """{teacher_id: staff emp_code} for teachers linked to a live staff row.
    Powers the 'Staff No' shown on the teachers list/profile/reports."""
    if not teacher_ids:
        return {}
    rows = await session.execute(
        select(Staff.linked_teacher_id, Staff.emp_code).where(
            Staff.branch_id == branch_id,
            Staff.linked_teacher_id.in_(teacher_ids),
            Staff.is_deleted == False,  # noqa: E712
        )
    )
    return {tid: code for tid, code in rows.all() if tid}


async def update(session: AsyncSession, staff: Staff, **kwargs) -> Staff:
    for key, value in kwargs.items():
        setattr(staff, key, value)
    await session.flush()
    return staff


async def soft_delete(session: AsyncSession, staff: Staff) -> None:
    staff.is_deleted = True
    await session.flush()
