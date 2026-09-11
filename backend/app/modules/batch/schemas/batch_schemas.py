import re
import uuid
from datetime import date

from pydantic import BaseModel, field_validator

# "HH:MM" 24-hour, e.g. 09:00, 14:30. Empty/None allowed (falls back to the
# global class-start).
_HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def _validate_hhmm(v: str | None) -> str | None:
    if v is None or v == "":
        return None
    if not _HHMM.match(v):
        raise ValueError("time must be HH:MM (24-hour), e.g. 14:30")
    return v


class BatchCreate(BaseModel):
    branch_id: uuid.UUID
    start_academic_year_id: uuid.UUID
    course_id: uuid.UUID
    name: str
    code: str
    capacity: int = 30
    target_exam_date: date | None = None
    class_start_time: str | None = None
    class_end_time: str | None = None

    _v_start = field_validator("class_start_time")(_validate_hhmm)
    _v_end = field_validator("class_end_time")(_validate_hhmm)


class BatchUpdate(BaseModel):
    name: str | None = None
    code: str | None = None
    capacity: int | None = None
    target_exam_date: date | None = None
    class_start_time: str | None = None
    class_end_time: str | None = None

    _v_start = field_validator("class_start_time")(_validate_hhmm)
    _v_end = field_validator("class_end_time")(_validate_hhmm)


class BatchResponse(BaseModel):
    id: uuid.UUID
    branch_id: uuid.UUID
    start_academic_year_id: uuid.UUID
    end_academic_year_id: uuid.UUID
    course_id: uuid.UUID
    name: str
    code: str
    capacity: int
    duration_years: int
    target_exam_date: date | None = None
    class_start_time: str | None = None
    class_end_time: str | None = None
    status: str
    model_config = {"from_attributes": True}
