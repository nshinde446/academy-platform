import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.modules.auth.permissions.rbac import get_current_user, require_roles
from app.modules.batch.schemas.batch_schemas import (
    BatchCreate,
    BatchResponse,
    BatchUpdate,
)
from app.modules.batch.services import batch_service

router = APIRouter(prefix="/batches", tags=["batches"])


@router.post("", response_model=BatchResponse)
async def create_batch(
    body: BatchCreate,
    request: Request,
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin"])),
    session: AsyncSession = Depends(get_db),
):
    return await batch_service.create_batch(
        session, body, current_user["user_id"],
        request.client.host if request.client else None,
    )


@router.get("", response_model=list[BatchResponse])
async def list_batches(
    branch_id: uuid.UUID = Query(...),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    return await batch_service.list_batches(session, branch_id, offset, limit)


@router.get("/{batch_id}", response_model=BatchResponse)
async def get_batch(
    batch_id: uuid.UUID,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    return await batch_service.get_batch(session, batch_id, branch_id)


@router.patch("/{batch_id}", response_model=BatchResponse)
async def update_batch(
    batch_id: uuid.UUID,
    body: BatchUpdate,
    request: Request,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin"])),
    session: AsyncSession = Depends(get_db),
):
    return await batch_service.update_batch(
        session, batch_id, body, branch_id, current_user["user_id"],
        request.client.host if request.client else None,
    )


@router.delete("/{batch_id}", status_code=204)
async def delete_batch(
    batch_id: uuid.UUID,
    request: Request,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin"])),
    session: AsyncSession = Depends(get_db),
):
    await batch_service.delete_batch(
        session, batch_id, branch_id, current_user["user_id"],
        request.client.host if request.client else None,
    )
