import uuid
from datetime import date, datetime

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


# ── Day-attendance reports (Layer 1) ───────────────────────────────────────


class DailyAttendanceResponse(BaseModel):
    """One day row — the unit of the per-student timeline (Reference A)."""
    id: uuid.UUID
    student_id: uuid.UUID
    branch_id: uuid.UUID
    attendance_date: date
    first_in: datetime | None = None
    last_out: datetime | None = None
    day_status: str
    signoff: str
    source: str
    model_config = {"from_attributes": True}


class ClassroomRegisterRow(BaseModel):
    """One student's P/A line in a classroom day register (Reference B)."""
    student_id: uuid.UUID
    name: str
    enrollment_number: str | None = None
    parent_mobile: str | None = None
    mark: str  # "P" | "A"
    day_status: str
    first_in: datetime | None = None
    last_out: datetime | None = None
    signoff: str


class AttendanceSummaryResponse(BaseModel):
    """Monthly/range % for one student (working_days = days with a lecture)."""
    student_id: uuid.UUID
    working_days: int
    present_days: int
    absent_days: int
    attendance_pct: float
