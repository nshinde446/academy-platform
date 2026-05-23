import uuid
from datetime import date

from pydantic import BaseModel


class BatchCreate(BaseModel):
    branch_id: uuid.UUID
    start_academic_year_id: uuid.UUID
    course_id: uuid.UUID
    name: str
    code: str
    capacity: int = 30
    target_exam_date: date | None = None


class BatchUpdate(BaseModel):
    name: str | None = None
    code: str | None = None
    capacity: int | None = None
    target_exam_date: date | None = None


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
    status: str
    model_config = {"from_attributes": True}
