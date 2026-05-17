import uuid
from datetime import datetime

from pydantic import BaseModel, Field

VALID_REPORT_TYPES = {
    "REPORT_CARD",
    "ATTENDANCE_REPORT",
    "PRODUCTIVITY_REPORT",
    "ANALYTICS_EXPORT",
}

VALID_OUTPUT_FORMATS = {"PDF", "EXCEL"}


class TemplateCreate(BaseModel):
    name: str = Field(..., max_length=100)
    report_type: str = Field(..., max_length=50)
    template_file: str = Field(..., max_length=255)
    config: dict | None = None
    is_active: bool = True
    branch_id: uuid.UUID | None = None


class TemplateUpdate(BaseModel):
    name: str | None = None
    report_type: str | None = None
    template_file: str | None = None
    config: dict | None = None
    is_active: bool | None = None


class TemplateResponse(BaseModel):
    id: uuid.UUID
    name: str
    report_type: str
    template_file: str
    config: dict | None = None
    is_active: bool
    branch_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class JobCreate(BaseModel):
    template_id: uuid.UUID
    parameters: dict | None = None
    output_format: str = "PDF"
    branch_id: uuid.UUID | None = None


class JobResponse(BaseModel):
    id: uuid.UUID
    template_id: uuid.UUID
    parameters: dict | None = None
    job_status: str
    output_url: str | None = None
    output_format: str
    requested_by: uuid.UUID
    requested_at: datetime
    completed_at: datetime | None = None
    error_message: str | None = None
    branch_id: uuid.UUID | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
