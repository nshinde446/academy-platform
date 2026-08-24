import uuid
from datetime import datetime, timezone

from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.notifications.models.notification_models import (
    NotificationEvent,
    NotificationQueue,
    NotificationSettings,
    NotificationTemplate,
)


async def create_template(
    session: AsyncSession, **kwargs
) -> NotificationTemplate:
    template = NotificationTemplate(**kwargs)
    session.add(template)
    await session.flush()
    return template


async def get_template(
    session: AsyncSession, template_id: uuid.UUID
) -> NotificationTemplate | None:
    result = await session.execute(
        select(NotificationTemplate).where(
            NotificationTemplate.id == template_id,
            NotificationTemplate.is_deleted == False,
        )
    )
    return result.scalar_one_or_none()


async def list_templates(
    session: AsyncSession,
    branch_id: uuid.UUID | None = None,
    event_type: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> list[NotificationTemplate]:
    stmt = select(NotificationTemplate).where(
        NotificationTemplate.is_deleted == False,
    )
    if branch_id is not None:
        stmt = stmt.where(
            or_(
                NotificationTemplate.branch_id == branch_id,
                NotificationTemplate.branch_id.is_(None),
            )
        )
    if event_type is not None:
        stmt = stmt.where(NotificationTemplate.event_type == event_type)
    stmt = stmt.offset(offset).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_active_templates(
    session: AsyncSession, event_type: str, branch_id: uuid.UUID | None
) -> list[NotificationTemplate]:
    stmt = select(NotificationTemplate).where(
        NotificationTemplate.event_type == event_type,
        NotificationTemplate.is_active == True,
        NotificationTemplate.is_deleted == False,
    )
    if branch_id is not None:
        stmt = stmt.where(
            or_(
                NotificationTemplate.branch_id == branch_id,
                NotificationTemplate.branch_id.is_(None),
            )
        )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def update_template(
    session: AsyncSession, template: NotificationTemplate, **kwargs
) -> NotificationTemplate:
    for key, value in kwargs.items():
        setattr(template, key, value)
    await session.flush()
    await session.refresh(template)
    return template


async def enqueue_notification(
    session: AsyncSession, **kwargs
) -> NotificationQueue:
    item = NotificationQueue(**kwargs)
    session.add(item)
    await session.flush()
    return item


async def get_pending_notifications(
    session: AsyncSession, limit: int = 100
) -> list[NotificationQueue]:
    now = datetime.now(timezone.utc)
    result = await session.execute(
        select(NotificationQueue).where(
            NotificationQueue.delivery_status == "PENDING",
            NotificationQueue.is_deleted == False,
            or_(
                NotificationQueue.scheduled_at.is_(None),
                NotificationQueue.scheduled_at <= now,
            ),
        ).limit(limit)
    )
    return list(result.scalars().all())


async def get_queue_item(
    session: AsyncSession, queue_id: uuid.UUID
) -> NotificationQueue | None:
    result = await session.execute(
        select(NotificationQueue).where(
            NotificationQueue.id == queue_id,
            NotificationQueue.is_deleted == False,
        )
    )
    return result.scalar_one_or_none()


async def list_queue(
    session: AsyncSession,
    delivery_status: str | None = None,
    branch_id: uuid.UUID | None = None,
    channel: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> list[NotificationQueue]:
    stmt = select(NotificationQueue).where(
        NotificationQueue.is_deleted == False,
    )
    if delivery_status is not None:
        stmt = stmt.where(NotificationQueue.delivery_status == delivery_status)
    if branch_id is not None:
        stmt = stmt.where(NotificationQueue.branch_id == branch_id)
    if channel is not None:
        stmt = stmt.where(NotificationQueue.channel == channel)
    stmt = stmt.order_by(NotificationQueue.created_at.desc()).offset(offset).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def mark_sent(session: AsyncSession, item: NotificationQueue) -> None:
    item.delivery_status = "SENT"
    item.sent_at = datetime.now(timezone.utc)
    await session.flush()


async def mark_failed(
    session: AsyncSession, item: NotificationQueue, error_message: str
) -> None:
    item.retry_count += 1
    item.error_message = error_message
    if item.retry_count >= item.max_retries:
        item.delivery_status = "FAILED"
    await session.flush()


async def create_notification_event(
    session: AsyncSession, **kwargs
) -> NotificationEvent:
    event = NotificationEvent(**kwargs)
    session.add(event)
    await session.flush()
    return event


async def get_settings(
    session: AsyncSession, branch_id: uuid.UUID
) -> NotificationSettings | None:
    result = await session.execute(
        select(NotificationSettings).where(
            NotificationSettings.branch_id == branch_id,
            NotificationSettings.is_deleted == False,
        )
    )
    return result.scalar_one_or_none()


async def upsert_settings(
    session: AsyncSession, branch_id: uuid.UUID, **fields
) -> NotificationSettings:
    settings = await get_settings(session, branch_id)
    if settings is None:
        settings = NotificationSettings(branch_id=branch_id, **fields)
        session.add(settings)
    else:
        for key, value in fields.items():
            setattr(settings, key, value)
    await session.flush()
    await session.refresh(settings)
    return settings


async def list_settings_enabled_for_digest(
    session: AsyncSession,
) -> list[NotificationSettings]:
    """Every branch whose daily digest is switched on — the nightly task's
    worklist."""
    result = await session.execute(
        select(NotificationSettings).where(
            NotificationSettings.daily_digest_enabled == True,
            NotificationSettings.is_deleted == False,
        )
    )
    return list(result.scalars().all())
