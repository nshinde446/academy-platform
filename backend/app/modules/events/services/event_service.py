import json
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.events.repositories import event_repository


async def emit_event(
    session: AsyncSession,
    event_type: str,
    branch_id: uuid.UUID | None = None,
    student_id: uuid.UUID | None = None,
    teacher_id: uuid.UUID | None = None,
    batch_id: uuid.UUID | None = None,
    subject_id: uuid.UUID | None = None,
    topic_id: uuid.UUID | None = None,
    lecture_id: uuid.UUID | None = None,
    test_id: uuid.UUID | None = None,
    metadata: dict | None = None,
):
    event_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    metadata_json = json.dumps(metadata, default=str) if metadata else None

    event = await event_repository.create_event(
        session,
        event_id=event_id,
        event_type=event_type,
        student_id=student_id,
        teacher_id=teacher_id,
        batch_id=batch_id,
        subject_id=subject_id,
        topic_id=topic_id,
        lecture_id=lecture_id,
        test_id=test_id,
        timestamp=now,
        metadata_json=metadata_json,
        processed=False,
        branch_id=branch_id,
    )
    return event


async def process_event(
    session: AsyncSession,
    event_id: uuid.UUID,
    consumer_name: str,
    success: bool = True,
    error_message: str | None = None,
):
    event = await event_repository.get_event_by_event_id(session, event_id)
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")

    now = datetime.now(timezone.utc)
    processing_status = "SUCCESS" if success else "FAILED"

    pe = await event_repository.mark_processed(
        session, event_id, consumer_name, processing_status, now, error_message
    )

    if success:
        await event_repository.update_event_processed_flag(session, event, True)

    return pe


async def replay_event(
    session: AsyncSession,
    event_pk: uuid.UUID,
):
    event = await event_repository.get_event_by_id(session, event_pk)
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")

    await event_repository.update_event_processed_flag(session, event, False)
    return event


async def list_events(
    session: AsyncSession,
    event_type: str | None = None,
    branch_id: uuid.UUID | None = None,
    processed: bool | None = None,
    offset: int = 0,
    limit: int = 50,
):
    return await event_repository.list_events(
        session, event_type, branch_id, processed, offset, limit
    )


async def get_unprocessed_events(
    session: AsyncSession, consumer_name: str, limit: int = 100
):
    return await event_repository.get_unprocessed_events(session, consumer_name, limit)
