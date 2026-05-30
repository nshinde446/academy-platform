import uuid
from datetime import date, datetime

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
    fees_status: str | None = None


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
    fees_status: str | None = None


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
    fees_status: str | None = None
    status: str
    model_config = {"from_attributes": True}


class StudentWithStats(BaseModel):
    """Student row enriched with computed analytics for the table view.

    Powers the MSA_Design students list (Rank, Avg score, Attendance,
    DPP completion, Fees). Aggregations join through student_marks,
    lecture_attendance_mappings, and student_responses respectively.
    """

    id: uuid.UUID
    first_name: str
    last_name: str
    enrollment_number: str | None = None
    standard: str | None = None
    target_exam: str | None = None
    batch_id: uuid.UUID | None = None
    batch_name: str | None = None
    fees_status: str | None = None
    # Computed
    avg_score_pct: float
    attendance_pct: float
    dpp_completion_pct: float
    batch_rank: int | None = None  # rank within their batch by avg_score
    batch_size: int = 0
    tests_taken: int = 0


class ImportSummary(BaseModel):
    imported: int
    skipped: int
    errors: list[str] = []


class StudentTestHistoryRow(BaseModel):
    """One row per test the student has taken — drives the per-student
    dashboard test series + rankings (Tier 13)."""

    test_id: uuid.UUID
    test_name: str
    paper_type: str
    scheduled_at: datetime | None = None
    subject_id: uuid.UUID
    subject_name: str
    topics: list[str] = []
    marks_obtained: float
    max_marks: float
    percentage: float
    grade: str | None = None
    is_absent: bool
    batch_rank: int | None = None
    batch_size: int = 0
    institute_rank: int | None = None
    institute_size: int = 0
