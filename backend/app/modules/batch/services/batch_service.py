import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.services import audit_service
from app.modules.batch.repositories import batch_repository
from app.modules.batch.schemas.batch_schemas import BatchCreate, BatchUpdate


async def create_batch(
    session: AsyncSession,
    data: BatchCreate,
    current_user_id: uuid.UUID,
    ip_address: str | None = None,
):
    batch = await batch_repository.create(session, **data.model_dump())
    await audit_service.log_action(
        session,
        user_id=current_user_id,
        action="CREATE",
        table_name="batches",
        record_id=batch.id,
        new_values=data.model_dump(),
        ip_address=ip_address,
        branch_id=data.branch_id,
    )
    return batch


async def get_batch(session: AsyncSession, batch_id: uuid.UUID, branch_id: uuid.UUID):
    batch = await batch_repository.get_by_id(session, batch_id)
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")
    if batch.branch_id != branch_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this branch")
    return batch


async def list_batches(session: AsyncSession, branch_id: uuid.UUID, offset: int = 0, limit: int = 50):
    return await batch_repository.list_by_branch(session, branch_id, offset, limit)


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
    return batch


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
    await audit_service.log_action(
        session,
        user_id=current_user_id,
        action="DELETE",
        table_name="batches",
        record_id=batch.id,
        old_values={"name": batch.name, "code": batch.code},
        ip_address=ip_address,
        branch_id=branch_id,
    )
