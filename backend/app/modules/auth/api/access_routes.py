"""RBAC access-control management endpoints (Manager only).

Set which batches a Floor Coordinator may act on, and grant/revoke attendance
visibility for Accounts users. Additive scoping — enforcement lands later.
"""

import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.modules.auth.permissions.rbac import require_roles
from app.modules.auth.repositories import access_repository
from app.modules.auth.schemas.access_schemas import (
    AccountsGrantCreateRequest,
    AccountsGrantResponse,
    BatchRef,
    CoordinatorBatchesResponse,
    SetCoordinatorBatchesRequest,
)
from app.modules.auth.services import access_service

router = APIRouter(prefix="/access", tags=["access-control"])

# Manager = super_admin (full access) + branch_admin.
_MANAGER_ROLES = ["super_admin", "branch_admin"]


def _actor_branch_id(current_user: dict) -> uuid.UUID | None:
    raw = current_user.get("branch_id")
    return uuid.UUID(raw) if raw else None


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.get(
    "/coordinators/{user_id}/batches", response_model=CoordinatorBatchesResponse
)
async def get_coordinator_batches(
    user_id: uuid.UUID,
    current_user: dict = Depends(require_roles(_MANAGER_ROLES)),
    session: AsyncSession = Depends(get_db),
):
    batches = await access_service.get_coordinator_batches(session, user_id)
    return CoordinatorBatchesResponse(
        user_id=user_id,
        batches=[BatchRef(id=b.id, name=b.name) for b in batches],
    )


@router.put(
    "/coordinators/{user_id}/batches", response_model=CoordinatorBatchesResponse
)
async def set_coordinator_batches(
    user_id: uuid.UUID,
    body: SetCoordinatorBatchesRequest,
    request: Request,
    current_user: dict = Depends(require_roles(_MANAGER_ROLES)),
    session: AsyncSession = Depends(get_db),
):
    batches = await access_service.set_coordinator_batches(
        session,
        actor_id=current_user["user_id"],
        branch_id=_actor_branch_id(current_user),
        coordinator_id=user_id,
        batch_ids=body.batch_ids,
        ip_address=_client_ip(request),
    )
    await session.commit()
    return CoordinatorBatchesResponse(
        user_id=user_id,
        batches=[BatchRef(id=b.id, name=b.name) for b in batches],
    )


def _grant_response(
    grant, batch_names: dict[uuid.UUID, str]
) -> AccountsGrantResponse:
    return AccountsGrantResponse(
        id=grant.id,
        user_id=grant.user_id,
        branch_id=grant.branch_id,
        batch_id=grant.batch_id,
        batch_name=batch_names.get(grant.batch_id) if grant.batch_id else None,
        expires_at=grant.expires_at,
        granted_by=grant.granted_by,
        created_at=grant.created_at,
    )


@router.get("/accounts-grants", response_model=list[AccountsGrantResponse])
async def list_accounts_grants(
    user_id: uuid.UUID | None = Query(None),
    current_user: dict = Depends(require_roles(_MANAGER_ROLES)),
    session: AsyncSession = Depends(get_db),
):
    branch_id = _actor_branch_id(current_user)
    grants = await access_service.list_grants(
        session, branch_id=branch_id, user_id=user_id
    )
    batch_ids = [g.batch_id for g in grants if g.batch_id]
    batches = await access_repository.batches_for(session, batch_ids)
    names = {b.id: b.name for b in batches}
    return [_grant_response(g, names) for g in grants]


@router.post("/accounts-grants", response_model=AccountsGrantResponse)
async def create_accounts_grant(
    body: AccountsGrantCreateRequest,
    request: Request,
    current_user: dict = Depends(require_roles(_MANAGER_ROLES)),
    session: AsyncSession = Depends(get_db),
):
    branch_id = _actor_branch_id(current_user)
    grant = await access_service.create_grant(
        session,
        actor_id=current_user["user_id"],
        branch_id=branch_id,
        user_id=body.user_id,
        batch_id=body.batch_id,
        expires_at=body.expires_at,
        ip_address=_client_ip(request),
    )
    await session.commit()
    await session.refresh(grant)
    names: dict[uuid.UUID, str] = {}
    if grant.batch_id:
        batches = await access_repository.batches_for(session, [grant.batch_id])
        names = {b.id: b.name for b in batches}
    return _grant_response(grant, names)


@router.delete("/accounts-grants/{grant_id}", status_code=204)
async def revoke_accounts_grant(
    grant_id: uuid.UUID,
    request: Request,
    current_user: dict = Depends(require_roles(_MANAGER_ROLES)),
    session: AsyncSession = Depends(get_db),
):
    await access_service.revoke_grant(
        session,
        actor_id=current_user["user_id"],
        branch_id=_actor_branch_id(current_user),
        grant_id=grant_id,
        ip_address=_client_ip(request),
    )
    await session.commit()
