import uuid
from datetime import datetime

from pydantic import BaseModel


class RawPunchCreate(BaseModel):
    device_id: str
    student_id: uuid.UUID
    punch_timestamp: datetime
    sync_batch_id: str | None = None


class RawPunchBatchCreate(BaseModel):
    punches: list[RawPunchCreate]


class RawPunchResponse(BaseModel):
    id: uuid.UUID
    device_id: str
    student_id: uuid.UUID
    punch_timestamp: datetime
    sync_batch_id: str | None = None
    synced_at: datetime | None = None
    branch_id: uuid.UUID
    model_config = {"from_attributes": True}


class AttendanceMarkRequest(BaseModel):
    student_id: uuid.UUID
    attendance_status: str = "PRESENT"
    source: str = "MANUAL"


class AttendanceRecordResponse(BaseModel):
    id: uuid.UUID
    student_id: uuid.UUID
    lecture_id: uuid.UUID
    attendance_status: str
    marked_at: datetime
    marked_by: uuid.UUID | None = None
    source: str
    branch_id: uuid.UUID
    status: str
    model_config = {"from_attributes": True}


class ExceptionCreate(BaseModel):
    student_id: uuid.UUID
    lecture_id: uuid.UUID
    reason: str


class ExceptionResolve(BaseModel):
    resolution_notes: str | None = None


class ExceptionResponse(BaseModel):
    id: uuid.UUID
    student_id: uuid.UUID
    lecture_id: uuid.UUID
    reason: str
    resolved: bool
    resolved_at: datetime | None = None
    resolved_by: uuid.UUID | None = None
    resolution_notes: str | None = None
    branch_id: uuid.UUID
    status: str
    model_config = {"from_attributes": True}


class AttendanceReportResponse(BaseModel):
    lecture_id: uuid.UUID
    total_students: int
    present: int
    absent: int
    late: int
    partial: int
    excused: int
