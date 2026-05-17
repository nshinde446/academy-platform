import uuid
from datetime import datetime

from pydantic import BaseModel


class EventCreate(BaseModel):
    event_type: str
    student_id: uuid.UUID | None = None
    teacher_id: uuid.UUID | None = None
    batch_id: uuid.UUID | None = None
    subject_id: uuid.UUID | None = None
    topic_id: uuid.UUID | None = None
    lecture_id: uuid.UUID | None = None
    test_id: uuid.UUID | None = None
    metadata: dict | None = None
    branch_id: uuid.UUID | None = None


class EventResponse(BaseModel):
    id: uuid.UUID
    event_id: uuid.UUID
    event_type: str
    student_id: uuid.UUID | None = None
    teacher_id: uuid.UUID | None = None
    batch_id: uuid.UUID | None = None
    subject_id: uuid.UUID | None = None
    topic_id: uuid.UUID | None = None
    lecture_id: uuid.UUID | None = None
    test_id: uuid.UUID | None = None
    timestamp: datetime
    metadata: dict | None = None
    processed: bool
    branch_id: uuid.UUID | None = None
    status: str
    model_config = {"from_attributes": True}


class ProcessedEventResponse(BaseModel):
    id: uuid.UUID
    event_id: uuid.UUID
    consumer_name: str
    processed_at: datetime
    processing_status: str
    error_message: str | None = None
    model_config = {"from_attributes": True}
