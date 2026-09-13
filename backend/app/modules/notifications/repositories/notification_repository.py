import uuid
from datetime import datetime, timezone

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.batch.models.batch_models import Batch
from app.modules.notifications.models.notification_models import (
    NotificationEvent,
    NotificationQueue,
    NotificationSettings,
    NotificationTemplate,
    NotificationWhatsappBatch,
)
from app.modules.student.models.student_models import Student, StudentBatchMapping


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


# ── Per-batch WhatsApp enablement (pilot control) ──────────────────────────


async def enabled_whatsapp_batch_ids(
    session: AsyncSession, branch_id: uuid.UUID
) -> set[uuid.UUID]:
    """The batch_ids for a branch that have WhatsApp notifications switched ON.

    An empty set is a valid, meaningful answer: notify nobody. Callers gate every
    parent-message producer on this set intersected with the day's scheduled
    batches."""
    result = await session.execute(
        select(NotificationWhatsappBatch.batch_id).where(
            NotificationWhatsappBatch.branch_id == branch_id,
            NotificationWhatsappBatch.is_deleted == False,
        )
    )
    return set(result.scalars().all())


async def set_enabled_whatsapp_batches(
    session: AsyncSession, branch_id: uuid.UUID, batch_ids: set[uuid.UUID]
) -> set[uuid.UUID]:
    """Make ``batch_ids`` the exact enabled set for the branch.

    Soft-deletes live rows no longer wanted, and un-deletes or inserts the rest
    (reusing a soft-deleted row keeps the (branch, batch) unique index happy).
    Returns the resulting enabled set."""
    existing = (await session.execute(
        select(NotificationWhatsappBatch).where(
            NotificationWhatsappBatch.branch_id == branch_id,
        )
    )).scalars().all()
    by_batch = {row.batch_id: row for row in existing}

    for batch_id, row in by_batch.items():
        # Target state: a wanted batch is live (is_deleted False); an unwanted one
        # is soft-deleted. Only touch rows whose state must flip.
        target_deleted = batch_id not in batch_ids
        if row.is_deleted != target_deleted:
            row.is_deleted = target_deleted

    for batch_id in batch_ids:
        if batch_id not in by_batch:
            session.add(
                NotificationWhatsappBatch(branch_id=branch_id, batch_id=batch_id)
            )

    await session.flush()
    return await enabled_whatsapp_batch_ids(session, branch_id)


async def list_branch_batch_counts(
    session: AsyncSession, branch_id: uuid.UUID
) -> list[tuple[uuid.UUID, str, str, int]]:
    """The branch's live batches with their active-student headcount, name-sorted.

    Feeds the per-batch WhatsApp selection UI (reach per batch). Counts distinct
    active, non-deleted students, so a batch with none still appears with 0."""
    result = await session.execute(
        select(
            Batch.id,
            Batch.name,
            Batch.code,
            func.count(func.distinct(Student.id)),
        )
        .outerjoin(
            StudentBatchMapping,
            and_(
                StudentBatchMapping.batch_id == Batch.id,
                StudentBatchMapping.is_deleted == False,
            ),
        )
        .outerjoin(
            Student,
            and_(
                Student.id == StudentBatchMapping.student_id,
                Student.is_deleted == False,
                Student.status == "active",
            ),
        )
        .where(Batch.branch_id == branch_id, Batch.is_deleted == False)
        .group_by(Batch.id, Batch.name, Batch.code)
        .order_by(Batch.name)
    )
    return [tuple(row) for row in result.all()]


async def batch_ids_in_branch(
    session: AsyncSession, branch_id: uuid.UUID, batch_ids: set[uuid.UUID]
) -> set[uuid.UUID]:
    """Of ``batch_ids``, those that are live batches of this branch — for branch
    isolation when saving the enabled set."""
    if not batch_ids:
        return set()
    result = await session.execute(
        select(Batch.id).where(
            Batch.id.in_(batch_ids),
            Batch.branch_id == branch_id,
            Batch.is_deleted == False,
        )
    )
    return set(result.scalars().all())
