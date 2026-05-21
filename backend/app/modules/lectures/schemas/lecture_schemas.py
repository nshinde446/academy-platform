import uuid
from datetime import datetime

from pydantic import BaseModel


class LectureCreate(BaseModel):
    teacher_id: uuid.UUID
    batch_id: uuid.UUID
    classroom_id: uuid.UUID | None = None
    subject_id: uuid.UUID
    topic_id: uuid.UUID | None = None
    scheduled_start: datetime
    scheduled_end: datetime
    delivery_mode: str = "offline"
    notes: str | None = None


class LectureUpdate(BaseModel):
    topic_id: uuid.UUID | None = None
    notes: str | None = None


class LectureReschedule(BaseModel):
    scheduled_start: datetime
    scheduled_end: datetime
    classroom_id: uuid.UUID | None = None


class LectureSubstitute(BaseModel):
    """Mark a lecture as taught by someone other than the scheduled teacher.
    Set actual_teacher_id to null to clear the substitution."""

    actual_teacher_id: uuid.UUID | None
    change_reason: str | None = "SUBSTITUTE"
    change_notes: str | None = None


class LectureResponse(BaseModel):
    id: uuid.UUID
    teacher_id: uuid.UUID
    batch_id: uuid.UUID
    classroom_id: uuid.UUID | None = None
    subject_id: uuid.UUID
    topic_id: uuid.UUID | None = None
    scheduled_start: datetime
    scheduled_end: datetime
    actual_start: datetime | None = None
    actual_end: datetime | None = None
    delivery_mode: str
    lecture_status: str
    notes: str | None = None
    actual_teacher_id: uuid.UUID | None = None
    change_reason: str | None = None
    change_notes: str | None = None
    branch_id: uuid.UUID
    academic_year_id: uuid.UUID
    status: str
    model_config = {"from_attributes": True}


class AttendanceMark(BaseModel):
    student_id: uuid.UUID
    attendance_status: str = "PRESENT"


class AttendanceResponse(BaseModel):
    id: uuid.UUID
    lecture_id: uuid.UUID
    student_id: uuid.UUID
    attendance_status: str
    marked_at: datetime
    model_config = {"from_attributes": True}
