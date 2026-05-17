import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.events.models.event_models import AcademicEvent, ProcessedEvent


async def create_event(session: AsyncSession, **kwargs) -> AcademicEvent:
    event = AcademicEvent(**kwargs)
    session.add(event)
    await session.flush()
    return event


async def get_event_by_event_id(session: AsyncSession, event_id: uuid.UUID) -> AcademicEvent | None:
    result = await session.execute(
        select(AcademicEvent).where(
            AcademicEvent.event_id == event_id,
            AcademicEvent.is_deleted == False,
        )
    )
    return result.scalar_one_or_none()


async def get_event_by_id(session: AsyncSession, pk: uuid.UUID) -> AcademicEvent | None:
    result = await session.execute(
        select(AcademicEvent).where(
            AcademicEvent.id == pk,
            AcademicEvent.is_deleted == False,
        )
    )
    return result.scalar_one_or_none()


async def list_events(
    session: AsyncSession,
    event_type: str | None = None,
    branch_id: uuid.UUID | None = None,
    processed: bool | None = None,
    offset: int = 0,
    limit: int = 50,
) -> list[AcademicEvent]:
    query = select(AcademicEvent).where(AcademicEvent.is_deleted == False)
    if event_type:
        query = query.where(AcademicEvent.event_type == event_type)
    if branch_id:
        query = query.where(AcademicEvent.branch_id == branch_id)
    if processed is not None:
        query = query.where(AcademicEvent.processed == processed)
    query = query.order_by(AcademicEvent.timestamp.desc()).offset(offset).limit(limit)
    result = await session.execute(query)
    return list(result.scalars().all())


async def get_unprocessed_events(
    session: AsyncSession, consumer_name: str, limit: int = 100
) -> list[AcademicEvent]:
    already_processed = select(ProcessedEvent.event_id).where(
        ProcessedEvent.consumer_name == consumer_name,
        ProcessedEvent.processing_status == "SUCCESS",
    ).scalar_subquery()

    result = await session.execute(
        select(AcademicEvent)
        .where(
            AcademicEvent.is_deleted == False,
            AcademicEvent.event_id.notin_(already_processed),
        )
        .order_by(AcademicEvent.timestamp)
        .limit(limit)
    )
    return list(result.scalars().all())


async def mark_processed(
    session: AsyncSession,
    event_id: uuid.UUID,
    consumer_name: str,
    processing_status: str,
    processed_at: datetime,
    error_message: str | None = None,
) -> ProcessedEvent:
    pe = ProcessedEvent(
        event_id=event_id,
        consumer_name=consumer_name,
        processed_at=processed_at,
        processing_status=processing_status,
        error_message=error_message,
    )
    session.add(pe)
    await session.flush()
    return pe


async def update_event_processed_flag(
    session: AsyncSession, event: AcademicEvent, processed: bool
) -> AcademicEvent:
    event.processed = processed
    await session.flush()
    return event
