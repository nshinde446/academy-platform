import uuid
from datetime import date

from pydantic import BaseModel


class StudentCreate(BaseModel):
    branch_id: uuid.UUID
    academic_year_id: uuid.UUID
    first_name: str
    last_name: str
    email: str | None = None
    phone: str | None = None
    date_of_birth: date | None = None
    enrollment_number: str | None = None
    parent_mobile: str | None = None
    rfid_number: str | None = None
    gender: str | None = None
    district: str | None = None
    caste: str | None = None
    username: str | None = None
    course_id: uuid.UUID | None = None


class StudentUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    phone: str | None = None
    date_of_birth: date | None = None
    enrollment_number: str | None = None
    parent_mobile: str | None = None
    rfid_number: str | None = None
    gender: str | None = None
    district: str | None = None
    caste: str | None = None
    username: str | None = None
    course_id: uuid.UUID | None = None


class StudentResponse(BaseModel):
    id: uuid.UUID
    branch_id: uuid.UUID
    academic_year_id: uuid.UUID
    first_name: str
    last_name: str
    email: str | None = None
    phone: str | None = None
    date_of_birth: date | None = None
    enrollment_number: str | None = None
    parent_mobile: str | None = None
    rfid_number: str | None = None
    gender: str | None = None
    district: str | None = None
    caste: str | None = None
    username: str | None = None
    course_id: uuid.UUID | None = None
    status: str
    model_config = {"from_attributes": True}


class ImportSummary(BaseModel):
    imported: int
    skipped: int
    errors: list[str] = []
