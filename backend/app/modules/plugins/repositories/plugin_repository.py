import uuid

from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.plugins.models.plugin_models import (
    Plugin,
    PluginConfig,
    PluginDependency,
    PluginEvent,
)


async def create_plugin(session: AsyncSession, **kwargs) -> Plugin:
    plugin = Plugin(**kwargs)
    session.add(plugin)
    await session.flush()
    await session.refresh(plugin)
    return plugin


async def get_plugin_by_id(session: AsyncSession, plugin_id: uuid.UUID) -> Plugin | None:
    result = await session.execute(
        select(Plugin).where(Plugin.id == plugin_id, Plugin.is_deleted == False)
    )
    return result.scalar_one_or_none()


async def get_plugin_by_name(session: AsyncSession, name: str) -> Plugin | None:
    result = await session.execute(
        select(Plugin).where(Plugin.name == name, Plugin.is_deleted == False)
    )
    return result.scalar_one_or_none()


async def list_plugins(
    session: AsyncSession,
    branch_id: uuid.UUID | None = None,
    offset: int = 0,
    limit: int = 50,
) -> list[Plugin]:
    query = select(Plugin).where(Plugin.is_deleted == False)
    if branch_id:
        query = query.where(
            or_(Plugin.branch_id == branch_id, Plugin.branch_id == None)
        )
    query = query.order_by(Plugin.name).offset(offset).limit(limit)
    result = await session.execute(query)
    return list(result.scalars().all())


async def get_enabled_plugins(
    session: AsyncSession, branch_id: uuid.UUID | None = None
) -> list[Plugin]:
    query = select(Plugin).where(
        Plugin.is_deleted == False,
        Plugin.is_enabled == True,
    )
    if branch_id:
        query = query.where(
            or_(Plugin.branch_id == branch_id, Plugin.branch_id == None)
        )
    result = await session.execute(query)
    return list(result.scalars().all())


async def update_plugin(session: AsyncSession, plugin: Plugin, **kwargs) -> Plugin:
    for k, v in kwargs.items():
        setattr(plugin, k, v)
    await session.flush()
    await session.refresh(plugin)
    return plugin


async def create_config(session: AsyncSession, **kwargs) -> PluginConfig:
    config = PluginConfig(**kwargs)
    session.add(config)
    await session.flush()
    await session.refresh(config)
    return config


async def get_plugin_config(
    session: AsyncSession, plugin_id: uuid.UUID, key: str
) -> PluginConfig | None:
    result = await session.execute(
        select(PluginConfig).where(
            PluginConfig.plugin_id == plugin_id,
            PluginConfig.key == key,
            PluginConfig.is_deleted == False,
        )
    )
    return result.scalar_one_or_none()


async def list_plugin_configs(
    session: AsyncSession, plugin_id: uuid.UUID
) -> list[PluginConfig]:
    result = await session.execute(
        select(PluginConfig).where(
            PluginConfig.plugin_id == plugin_id,
            PluginConfig.is_deleted == False,
        )
    )
    return list(result.scalars().all())


async def set_plugin_config(
    session: AsyncSession,
    plugin_id: uuid.UUID,
    key: str,
    value: str,
    is_secret: bool = False,
) -> PluginConfig:
    existing = await get_plugin_config(session, plugin_id, key)
    if existing:
        existing.value = value
        existing.is_secret = is_secret
        await session.flush()
        await session.refresh(existing)
        return existing
    return await create_config(
        session, plugin_id=plugin_id, key=key, value=value, is_secret=is_secret
    )


async def create_event_subscription(session: AsyncSession, **kwargs) -> PluginEvent:
    event = PluginEvent(**kwargs)
    session.add(event)
    await session.flush()
    await session.refresh(event)
    return event


async def get_plugins_for_event(
    session: AsyncSession, event_type: str, branch_id: uuid.UUID | None = None
) -> list[tuple[Plugin, PluginEvent]]:
    query = (
        select(Plugin, PluginEvent)
        .join(PluginEvent, Plugin.id == PluginEvent.plugin_id)
        .where(
            Plugin.is_deleted == False,
            Plugin.is_enabled == True,
            PluginEvent.is_deleted == False,
            PluginEvent.is_active == True,
            PluginEvent.event_type == event_type,
        )
    )
    if branch_id:
        query = query.where(
            or_(Plugin.branch_id == branch_id, Plugin.branch_id == None)
        )
    result = await session.execute(query)
    return list(result.tuples().all())


async def create_dependency(session: AsyncSession, **kwargs) -> PluginDependency:
    dep = PluginDependency(**kwargs)
    session.add(dep)
    await session.flush()
    await session.refresh(dep)
    return dep


async def get_dependencies(
    session: AsyncSession, plugin_id: uuid.UUID
) -> list[PluginDependency]:
    result = await session.execute(
        select(PluginDependency).where(
            PluginDependency.plugin_id == plugin_id,
            PluginDependency.is_deleted == False,
        )
    )
    return list(result.scalars().all())
