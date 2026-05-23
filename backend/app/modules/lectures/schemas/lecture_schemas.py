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


class LectureSessionCreate(BaseModel):
    """Create an ad-hoc / makeup / planned-completion teaching session.

    batch_ids: 1+ batches that attended (use multiple for merged batches).
    lecture_ids: 0+ scheduled lectures fulfilled by this session.
        - 0 = pure ad-hoc, no plan existed
        - 1 = normal completion / single-plan makeup
        - 2+ = merged batches taught together
    origin: planned | makeup | ad_hoc — defaults to ad_hoc for this endpoint.
    """

    teacher_id: uuid.UUID
    subject_id: uuid.UUID
    batch_ids: list[uuid.UUID]
    lecture_ids: list[uuid.UUID] = []
    classroom_id: uuid.UUID | None = None
    topic_id: uuid.UUID | None = None
    actual_start: datetime
    actual_end: datetime | None = None
    delivery_mode: str = "offline"
    origin: str = "ad_hoc"
    notes: str | None = None


class LectureSessionResponse(BaseModel):
    id: uuid.UUID
    teacher_id: uuid.UUID
    subject_id: uuid.UUID
    topic_id: uuid.UUID | None = None
    classroom_id: uuid.UUID | None = None
    actual_start: datetime
    actual_end: datetime | None = None
    delivery_mode: str
    session_status: str
    origin: str
    notes: str | None = None
    branch_id: uuid.UUID
    academic_year_id: uuid.UUID
    batch_ids: list[uuid.UUID] = []
    lecture_ids: list[uuid.UUID] = []
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
