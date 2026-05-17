import importlib
import json
import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.services import audit_service
from app.modules.plugins.repositories import plugin_repository

_loaded_plugins: dict[uuid.UUID, object] = {}


async def register_plugin(
    session: AsyncSession,
    *,
    data: dict,
    current_user_id: uuid.UUID,
    ip_address: str | None = None,
) -> object:
    existing = await plugin_repository.get_plugin_by_name(session, data["name"])
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Plugin with this name already exists",
        )

    plugin = await plugin_repository.create_plugin(session, **data)

    await audit_service.log_action(
        session,
        user_id=current_user_id,
        action="CREATE",
        table_name="plugins",
        record_id=plugin.id,
        new_values=data,
        ip_address=ip_address,
    )

    return plugin


async def list_plugins(
    session: AsyncSession,
    branch_id: uuid.UUID | None = None,
    offset: int = 0,
    limit: int = 50,
):
    return await plugin_repository.list_plugins(session, branch_id, offset, limit)


async def get_plugin(session: AsyncSession, plugin_id: uuid.UUID):
    plugin = await plugin_repository.get_plugin_by_id(session, plugin_id)
    if not plugin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Plugin not found"
        )
    return plugin


async def enable_plugin(
    session: AsyncSession,
    plugin_id: uuid.UUID,
    *,
    current_user_id: uuid.UUID,
    ip_address: str | None = None,
):
    plugin = await get_plugin(session, plugin_id)

    deps_ok, missing = await validate_dependencies(session, plugin_id)
    if not deps_ok:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsatisfied dependencies: {', '.join(missing)}",
        )

    plugin = await plugin_repository.update_plugin(session, plugin, is_enabled=True)
    await load_plugin(plugin_id, plugin.entry_point)

    await audit_service.log_action(
        session,
        user_id=current_user_id,
        action="UPDATE",
        table_name="plugins",
        record_id=plugin.id,
        old_values={"is_enabled": False},
        new_values={"is_enabled": True},
        ip_address=ip_address,
    )

    return plugin


async def disable_plugin(
    session: AsyncSession,
    plugin_id: uuid.UUID,
    *,
    current_user_id: uuid.UUID,
    ip_address: str | None = None,
):
    plugin = await get_plugin(session, plugin_id)
    plugin = await plugin_repository.update_plugin(session, plugin, is_enabled=False)
    await unload_plugin(plugin_id)

    await audit_service.log_action(
        session,
        user_id=current_user_id,
        action="UPDATE",
        table_name="plugins",
        record_id=plugin.id,
        old_values={"is_enabled": True},
        new_values={"is_enabled": False},
        ip_address=ip_address,
    )

    return plugin


async def delete_plugin(
    session: AsyncSession,
    plugin_id: uuid.UUID,
    *,
    current_user_id: uuid.UUID,
    ip_address: str | None = None,
):
    plugin = await get_plugin(session, plugin_id)
    await plugin_repository.update_plugin(session, plugin, is_deleted=True)
    await unload_plugin(plugin_id)

    await audit_service.log_action(
        session,
        user_id=current_user_id,
        action="DELETE",
        table_name="plugins",
        record_id=plugin.id,
        old_values={"is_deleted": False},
        new_values={"is_deleted": True},
        ip_address=ip_address,
    )


async def set_config(
    session: AsyncSession,
    plugin_id: uuid.UUID,
    *,
    key: str,
    value: str,
    is_secret: bool = False,
    current_user_id: uuid.UUID,
    ip_address: str | None = None,
):
    await get_plugin(session, plugin_id)
    config = await plugin_repository.set_plugin_config(
        session, plugin_id, key, value, is_secret
    )

    await audit_service.log_action(
        session,
        user_id=current_user_id,
        action="UPDATE",
        table_name="plugin_config",
        record_id=config.id,
        new_values={"key": key, "value": "***" if is_secret else value},
        ip_address=ip_address,
    )

    return config


async def list_configs(session: AsyncSession, plugin_id: uuid.UUID):
    await get_plugin(session, plugin_id)
    configs = await plugin_repository.list_plugin_configs(session, plugin_id)
    result = []
    for c in configs:
        result.append({
            "id": c.id,
            "plugin_id": c.plugin_id,
            "key": c.key,
            "value": "***" if c.is_secret else c.value,
            "is_secret": c.is_secret,
            "created_at": c.created_at,
        })
    return result


async def subscribe_event(
    session: AsyncSession,
    plugin_id: uuid.UUID,
    *,
    event_type: str,
    handler: str,
    current_user_id: uuid.UUID,
    ip_address: str | None = None,
):
    await get_plugin(session, plugin_id)
    event_sub = await plugin_repository.create_event_subscription(
        session, plugin_id=plugin_id, event_type=event_type, handler=handler
    )

    await audit_service.log_action(
        session,
        user_id=current_user_id,
        action="CREATE",
        table_name="plugin_events",
        record_id=event_sub.id,
        new_values={"event_type": event_type, "handler": handler},
        ip_address=ip_address,
    )

    return event_sub


async def trigger_plugin_event(
    session: AsyncSession,
    event_type: str,
    event_data: dict,
    branch_id: uuid.UUID | None = None,
):
    subscriptions = await plugin_repository.get_plugins_for_event(
        session, event_type, branch_id
    )

    results = []
    for plugin, plugin_event in subscriptions:
        try:
            handler_fn = _resolve_handler(plugin_event.handler)
            if handler_fn:
                handler_fn(event_data)
                results.append({"plugin": plugin.name, "status": "SUCCESS"})
            else:
                results.append({"plugin": plugin.name, "status": "HANDLER_NOT_FOUND"})
        except Exception as exc:
            results.append({"plugin": plugin.name, "status": "ERROR", "error": str(exc)})

    return results


async def get_plugin_status(session: AsyncSession, plugin_id: uuid.UUID) -> dict:
    plugin = await get_plugin(session, plugin_id)
    return {
        "id": plugin.id,
        "name": plugin.name,
        "version": plugin.version,
        "is_enabled": plugin.is_enabled,
        "is_loaded": plugin_id in _loaded_plugins,
    }


async def validate_dependencies(
    session: AsyncSession, plugin_id: uuid.UUID
) -> tuple[bool, list[str]]:
    deps = await plugin_repository.get_dependencies(session, plugin_id)
    missing = []
    for dep in deps:
        dep_plugin = await plugin_repository.get_plugin_by_id(
            session, dep.depends_on_plugin_id
        )
        if not dep_plugin or not dep_plugin.is_enabled:
            missing.append(str(dep.depends_on_plugin_id))
    return (len(missing) == 0, missing)


async def load_plugin(plugin_id: uuid.UUID, entry_point: str):
    try:
        module_path, class_name = entry_point.rsplit(":", 1)
        module = importlib.import_module(module_path)
        plugin_class = getattr(module, class_name)
        instance = plugin_class()
        if hasattr(instance, "on_load"):
            instance.on_load()
        _loaded_plugins[plugin_id] = instance
    except Exception:
        _loaded_plugins[plugin_id] = None


async def unload_plugin(plugin_id: uuid.UUID):
    instance = _loaded_plugins.pop(plugin_id, None)
    if instance and hasattr(instance, "on_unload"):
        instance.on_unload()


def _resolve_handler(handler_path: str):
    try:
        module_path, func_name = handler_path.rsplit(":", 1)
        module = importlib.import_module(module_path)
        return getattr(module, func_name, None)
    except Exception:
        return None
