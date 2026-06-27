import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.academic.repositories import academic_repository
from app.modules.audit.services import audit_service
from app.modules.batch.repositories import batch_repository
from app.modules.batch.schemas.batch_schemas import BatchCreate, BatchUpdate


def _attach_duration(batch, start_year: int, end_year: int):
    batch.duration_years = end_year - start_year + 1
    return batch


async def _attach_duration_for_list(session: AsyncSession, batches: list):
    if not batches:
        return batches
    year_ids = {b.start_academic_year_id for b in batches} | {
        b.end_academic_year_id for b in batches
    }
    year_lookup: dict[uuid.UUID, int] = {}
    for yid in year_ids:
        ay = await academic_repository.get_academic_year(session, yid)
        if ay:
            year_lookup[yid] = ay.start_year
    for b in batches:
        start = year_lookup.get(b.start_academic_year_id)
        end = year_lookup.get(b.end_academic_year_id)
        b.duration_years = (end - start + 1) if start is not None and end is not None else 1
    return batches


async def create_batch(
    session: AsyncSession,
    data: BatchCreate,
    current_user_id: uuid.UUID,
    ip_address: str | None = None,
):
    course = await academic_repository.get_course(session, data.course_id)
    if not course:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Course not found"
        )

    start_year = await academic_repository.get_academic_year(
        session, data.start_academic_year_id
    )
    if not start_year:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Start academic year not found",
        )

    duration = max(int(course.duration_years or 1), 1)
    end_year_start = start_year.start_year + duration - 1

    end_year = await academic_repository.get_academic_year_by_start_year(
        session, data.branch_id, end_year_start
    )
    if not end_year:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Cannot find academic year starting at {end_year_start} for this branch. "
                f"Create it before creating a {duration}-year batch."
            ),
        )

    payload = data.model_dump()
    payload["end_academic_year_id"] = end_year.id

    batch = await batch_repository.create(session, **payload)

    await audit_service.log_action(
        session,
        user_id=current_user_id,
        action="CREATE",
        table_name="batches",
        record_id=batch.id,
        new_values=payload,
        ip_address=ip_address,
        branch_id=data.branch_id,
    )
    return _attach_duration(batch, start_year.start_year, end_year.start_year)


async def get_batch(session: AsyncSession, batch_id: uuid.UUID, branch_id: uuid.UUID):
    batch = await batch_repository.get_by_id(session, batch_id)
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")
    if batch.branch_id != branch_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this branch")
    batches = await _attach_duration_for_list(session, [batch])
    return batches[0]


async def list_batches(session: AsyncSession, branch_id: uuid.UUID, offset: int = 0, limit: int = 50):
    batches = await batch_repository.list_by_branch(session, branch_id, offset, limit)
    return await _attach_duration_for_list(session, batches)


async def update_batch(
    session: AsyncSession,
    batch_id: uuid.UUID,
    data: BatchUpdate,
    branch_id: uuid.UUID,
    current_user_id: uuid.UUID,
    ip_address: str | None = None,
):
    batch = await batch_repository.get_by_id(session, batch_id)
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")
    if batch.branch_id != branch_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this branch")

    old_values = {"name": batch.name, "code": batch.code, "capacity": batch.capacity}
    update_data = data.model_dump(exclude_unset=True)
    batch = await batch_repository.update(session, batch, **update_data)

    await audit_service.log_action(
        session,
        user_id=current_user_id,
        action="UPDATE",
        table_name="batches",
        record_id=batch.id,
        old_values=old_values,
        new_values=update_data,
        ip_address=ip_address,
        branch_id=branch_id,
    )
    batches = await _attach_duration_for_list(session, [batch])
    return batches[0]


async def delete_batch(
    session: AsyncSession,
    batch_id: uuid.UUID,
    branch_id: uuid.UUID,
    current_user_id: uuid.UUID,
    ip_address: str | None = None,
):
    batch = await batch_repository.get_by_id(session, batch_id)
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")
    if batch.branch_id != branch_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this branch")

    await batch_repository.soft_delete(session, batch)
    # Cascade: clear the batch's weekly timetable so its slots don't outlive it
    # as orphans the schedule generator has to skip.
    cleared = await batch_repository.soft_delete_schedules(session, batch.id)
    await audit_service.log_action(
        session,
        user_id=current_user_id,
        action="DELETE",
        table_name="batches",
        record_id=batch.id,
        old_values={
            "name": batch.name,
            "code": batch.code,
            "timetable_slots_cleared": cleared,
        },
        ip_address=ip_address,
        branch_id=branch_id,
    )
