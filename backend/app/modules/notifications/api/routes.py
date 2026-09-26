import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.modules.auth.permissions.rbac import require_roles
from app.modules.notifications.schemas.notification_schemas import (
    DeliveryLogRow,
    QueueItemResponse,
    SettingsResponse,
    SettingsUpdate,
    TemplateCreate,
    TemplateResponse,
    TemplateUpdate,
    WhatsappBatchesUpdate,
    WhatsappBatchRow,
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


@router.get("/settings", response_model=SettingsResponse)
async def get_settings(
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin"])),
    session: AsyncSession = Depends(get_db),
):
    return await notification_service.get_notification_settings(session, branch_id)


@router.put("/settings", response_model=SettingsResponse)
async def update_settings(
    body: SettingsUpdate,
    request: Request,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin"])),
    session: AsyncSession = Depends(get_db),
):
    return await notification_service.update_notification_settings(
        session,
        branch_id=branch_id,
        data=body.model_dump(exclude_unset=True),
        current_user_id=current_user["user_id"],
        ip_address=request.client.host if request.client else None,
    )


@router.get("/whatsapp-batches", response_model=list[WhatsappBatchRow])
async def list_whatsapp_batches(
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin"])),
    session: AsyncSession = Depends(get_db),
):
    """The branch's batches with active-student counts and whether each has
    WhatsApp parent notifications switched on (the per-batch pilot selection)."""
    return await notification_service.list_whatsapp_batches(session, branch_id)


@router.put("/whatsapp-batches", response_model=list[WhatsappBatchRow])
async def set_whatsapp_batches(
    body: WhatsappBatchesUpdate,
    request: Request,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin"])),
    session: AsyncSession = Depends(get_db),
):
    """Replace the branch's enabled-batch set. Empty list = notify nobody."""
    return await notification_service.set_whatsapp_batches(
        session,
        branch_id=branch_id,
        batch_ids=body.batch_ids,
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


@router.get("/delivery-log", response_model=list[DeliveryLogRow])
async def delivery_log(
    branch_id: uuid.UUID | None = Query(None),
    delivery_status: str | None = Query(None),
    batch_id: uuid.UUID | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    q: str | None = Query(None, max_length=100),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin"])),
    session: AsyncSession = Depends(get_db),
):
    """WhatsApp absence-notification delivery log (§5): which parents received a
    message, so the team can confirm coverage and re-send to anyone missed.

    Filterable by batch, a ``date_from``/``date_to`` range, and a free-text ``q``
    over student name / parent number, in addition to delivery status."""
    return await notification_service.delivery_log(
        session, branch_id=branch_id, delivery_status=delivery_status,
        batch_id=batch_id, date_from=date_from, date_to=date_to, q=q,
        offset=offset, limit=limit,
    )
