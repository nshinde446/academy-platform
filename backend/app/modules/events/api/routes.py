import json
import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.modules.auth.permissions.rbac import require_roles
from app.modules.events.schemas.event_schemas import EventResponse
from app.modules.events.services import event_service

router = APIRouter(prefix="/events", tags=["events"])


@router.get("", response_model=list[EventResponse])
async def list_events(
    event_type: str | None = Query(None),
    branch_id: uuid.UUID | None = Query(None),
    processed: bool | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(require_roles(["super_admin"])),
    session: AsyncSession = Depends(get_db),
):
    events = await event_service.list_events(
        session, event_type, branch_id, processed, offset, limit
    )
    return [_format_event(e) for e in events]


@router.post("/replay/{event_id}", response_model=EventResponse)
async def replay_event(
    event_id: uuid.UUID,
    current_user: dict = Depends(require_roles(["super_admin"])),
    session: AsyncSession = Depends(get_db),
):
    event = await event_service.replay_event(session, event_id)
    return _format_event(event)


def _format_event(event):
    return {
        "id": event.id,
        "event_id": event.event_id,
        "event_type": event.event_type,
        "student_id": event.student_id,
        "teacher_id": event.teacher_id,
        "batch_id": event.batch_id,
        "subject_id": event.subject_id,
        "topic_id": event.topic_id,
        "lecture_id": event.lecture_id,
        "test_id": event.test_id,
        "timestamp": event.timestamp,
        "metadata": json.loads(event.metadata_json) if event.metadata_json else None,
        "processed": event.processed,
        "branch_id": event.branch_id,
        "status": event.status,
    }
