import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.modules.auth.permissions.rbac import require_roles
from app.modules.notifications.schemas.notification_schemas import (
    QueueItemResponse,
    TemplateCreate,
    TemplateResponse,
    TemplateUpdate,
)
from app.modules.notifications.services import notification_service

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.post("/templates", response_model=TemplateResponse, status_code=201)
async def create_template(
    body: TemplateCreate,
    request: Request,
    current_user: dict = Depends(require_roles(["super_admin"])),
    session: AsyncSession = Depends(get_db),
):
    return await notification_service.create_template(
        session,
        data=body.model_dump(),
        current_user_id=current_user["user_id"],
        ip_address=request.client.host if request.client else None,
    )


@router.get("/templates", response_model=list[TemplateResponse])
async def list_templates(
    branch_id: uuid.UUID | None = Query(None),
    event_type: str | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin"])),
    session: AsyncSession = Depends(get_db),
):
    return await notification_service.list_templates(
        session, branch_id=branch_id, event_type=event_type,
        offset=offset, limit=limit,
    )


@router.patch("/templates/{template_id}", response_model=TemplateResponse)
async def update_template(
    template_id: uuid.UUID,
    body: TemplateUpdate,
    request: Request,
    current_user: dict = Depends(require_roles(["super_admin"])),
    session: AsyncSession = Depends(get_db),
):
    return await notification_service.update_template(
        session, template_id,
        data=body.model_dump(exclude_unset=True),
        current_user_id=current_user["user_id"],
        ip_address=request.client.host if request.client else None,
    )


@router.delete("/templates/{template_id}", status_code=204)
async def delete_template(
    template_id: uuid.UUID,
    request: Request,
    current_user: dict = Depends(require_roles(["super_admin"])),
    session: AsyncSession = Depends(get_db),
):
    await notification_service.delete_template(
        session, template_id,
        current_user_id=current_user["user_id"],
        ip_address=request.client.host if request.client else None,
    )


@router.get("/queue", response_model=list[QueueItemResponse])
async def list_queue(
    delivery_status: str | None = Query(None),
    branch_id: uuid.UUID | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(require_roles(["super_admin"])),
    session: AsyncSession = Depends(get_db),
):
    return await notification_service.list_queue(
        session, delivery_status=delivery_status, branch_id=branch_id,
        offset=offset, limit=limit,
    )
