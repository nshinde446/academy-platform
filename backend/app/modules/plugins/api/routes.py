import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.modules.auth.permissions.rbac import require_roles
from app.modules.plugins.schemas.plugin_schemas import (
    PluginConfigCreate,
    PluginConfigResponse,
    PluginCreate,
    PluginEventCreate,
    PluginEventResponse,
    PluginResponse,
)
from app.modules.plugins.services import plugin_service

router = APIRouter(prefix="/plugins", tags=["plugins"])


@router.post("", response_model=PluginResponse, status_code=201)
async def register_plugin(
    body: PluginCreate,
    request: Request,
    current_user: dict = Depends(require_roles(["super_admin"])),
    session: AsyncSession = Depends(get_db),
):
    return await plugin_service.register_plugin(
        session,
        data=body.model_dump(),
        current_user_id=current_user["user_id"],
        ip_address=request.client.host if request.client else None,
    )


@router.get("", response_model=list[PluginResponse])
async def list_plugins(
    branch_id: uuid.UUID | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin"])),
    session: AsyncSession = Depends(get_db),
):
    return await plugin_service.list_plugins(
        session, branch_id=branch_id, offset=offset, limit=limit
    )


@router.get("/{plugin_id}", response_model=PluginResponse)
async def get_plugin(
    plugin_id: uuid.UUID,
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin"])),
    session: AsyncSession = Depends(get_db),
):
    return await plugin_service.get_plugin(session, plugin_id)


@router.patch("/{plugin_id}/enable", response_model=PluginResponse)
async def enable_plugin(
    plugin_id: uuid.UUID,
    request: Request,
    current_user: dict = Depends(require_roles(["super_admin"])),
    session: AsyncSession = Depends(get_db),
):
    return await plugin_service.enable_plugin(
        session,
        plugin_id,
        current_user_id=current_user["user_id"],
        ip_address=request.client.host if request.client else None,
    )


@router.patch("/{plugin_id}/disable", response_model=PluginResponse)
async def disable_plugin(
    plugin_id: uuid.UUID,
    request: Request,
    current_user: dict = Depends(require_roles(["super_admin"])),
    session: AsyncSession = Depends(get_db),
):
    return await plugin_service.disable_plugin(
        session,
        plugin_id,
        current_user_id=current_user["user_id"],
        ip_address=request.client.host if request.client else None,
    )


@router.delete("/{plugin_id}", status_code=204)
async def delete_plugin(
    plugin_id: uuid.UUID,
    request: Request,
    current_user: dict = Depends(require_roles(["super_admin"])),
    session: AsyncSession = Depends(get_db),
):
    await plugin_service.delete_plugin(
        session,
        plugin_id,
        current_user_id=current_user["user_id"],
        ip_address=request.client.host if request.client else None,
    )


@router.post("/{plugin_id}/config", response_model=PluginConfigResponse, status_code=201)
async def set_config(
    plugin_id: uuid.UUID,
    body: PluginConfigCreate,
    request: Request,
    current_user: dict = Depends(require_roles(["super_admin"])),
    session: AsyncSession = Depends(get_db),
):
    return await plugin_service.set_config(
        session,
        plugin_id,
        key=body.key,
        value=body.value,
        is_secret=body.is_secret,
        current_user_id=current_user["user_id"],
        ip_address=request.client.host if request.client else None,
    )


@router.get("/{plugin_id}/config")
async def list_configs(
    plugin_id: uuid.UUID,
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin"])),
    session: AsyncSession = Depends(get_db),
):
    return await plugin_service.list_configs(session, plugin_id)


@router.post("/{plugin_id}/events", response_model=PluginEventResponse, status_code=201)
async def subscribe_event(
    plugin_id: uuid.UUID,
    body: PluginEventCreate,
    request: Request,
    current_user: dict = Depends(require_roles(["super_admin"])),
    session: AsyncSession = Depends(get_db),
):
    return await plugin_service.subscribe_event(
        session,
        plugin_id,
        event_type=body.event_type,
        handler=body.handler,
        current_user_id=current_user["user_id"],
        ip_address=request.client.host if request.client else None,
    )
