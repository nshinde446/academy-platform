import uuid

from pydantic import BaseModel


class BatchCreate(BaseModel):
    branch_id: uuid.UUID
    start_academic_year_id: uuid.UUID
    course_id: uuid.UUID
    name: str
    code: str
    capacity: int = 30


class BatchUpdate(BaseModel):
    name: str | None = None
    code: str | None = None
    capacity: int | None = None


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
    status: str
    model_config = {"from_attributes": True}
