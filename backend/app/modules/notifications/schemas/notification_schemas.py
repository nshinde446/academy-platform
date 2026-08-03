import uuid
from datetime import datetime

from pydantic import BaseModel


VALID_CHANNELS = {"EMAIL", "SMS", "WHATSAPP", "PUSH"}
VALID_EVENT_TYPES = {
    "ATTENDANCE_MARKED",
    "STUDENT_ABSENT",  # emitted per student by the nightly absent sweep -> parent notify
    "LECTURE_COMPLETED",
    "LECTURE_CANCELLED",
    "TEST_UPLOADED",
    "MARKS_UPDATED",
}


class TemplateCreate(BaseModel):
    name: str
    event_type: str
    channel: str
    subject: str | None = None
    body_template: str
    is_active: bool = True
    condition_json: dict | None = None
    branch_id: uuid.UUID | None = None
    # WHATSAPP only — the Meta-approved template name + language code.
    provider_template_name: str | None = None
    provider_language: str | None = None


class TemplateUpdate(BaseModel):
    name: str | None = None
    event_type: str | None = None
    channel: str | None = None
    subject: str | None = None
    body_template: str | None = None
    is_active: bool | None = None
    condition_json: dict | None = None
    provider_template_name: str | None = None
    provider_language: str | None = None


class TemplateResponse(BaseModel):
    id: uuid.UUID
    name: str
    event_type: str
    channel: str
    subject: str | None = None
    body_template: str
    is_active: bool
    condition: dict | None = None
    branch_id: uuid.UUID | None = None
    provider_template_name: str | None = None
    provider_language: str | None = None
    created_at: datetime
    updated_at: datetime


class QueueItemResponse(BaseModel):
    id: uuid.UUID
    template_id: uuid.UUID
    recipient: str
    channel: str
    payload: dict | None = None
    delivery_status: str
    retry_count: int
    max_retries: int
    scheduled_at: datetime | None = None
    sent_at: datetime | None = None
    error_message: str | None = None
    branch_id: uuid.UUID | None = None
    created_at: datetime
