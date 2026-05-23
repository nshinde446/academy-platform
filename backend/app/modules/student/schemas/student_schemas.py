import uuid
from datetime import date

from pydantic import BaseModel


class StudentCreate(BaseModel):
    branch_id: uuid.UUID
    academic_year_id: uuid.UUID
    first_name: str
    last_name: str
    # Required at enrolment so the analytics layer can segment students
    # by class and exam track from day one. Validated against the
    # VALID_STANDARDS / VALID_TARGET_EXAMS sets in the service layer.
    standard: str
    target_exam: str
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
    standard: str | None = None
    target_exam: str | None = None


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
    standard: str | None = None
    target_exam: str | None = None
    status: str
    model_config = {"from_attributes": True}


class ImportSummary(BaseModel):
    imported: int
    skipped: int
    errors: list[str] = []
