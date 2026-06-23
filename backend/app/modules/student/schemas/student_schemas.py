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
    # PCM | PCB | PCMB — defaulted from target when omitted.
    stream: str | None = None


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
    # Admins can override the imported/defaulted stream (PCM | PCB | PCMB).
    stream: str | None = None


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
    stream: str | None = None
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
    stream: str | None = None
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


class StudentStatsPage(BaseModel):
    """One page of the roster (server-side pagination). ``total`` is the count
    after search filtering, for page controls."""

    items: list[StudentWithStats] = []
    total: int = 0


class StudentSubjectSyllabus(BaseModel):
    """One subject a student is accountable for (after the stream filter), with
    how much curriculum is loaded — drives a per-student syllabus view."""

    subject_id: uuid.UUID
    subject_name: str
    chapter_count: int
    topic_count: int


class StudentSyllabus(BaseModel):
    """A student's accountable syllabus: their course's subjects filtered to the
    ones their stream actually sits (Physics/Chemistry always; Maths for PCM;
    Biology for PCB)."""

    student_id: uuid.UUID
    stream: str | None = None
    course_id: uuid.UUID | None = None
    subjects: list[StudentSubjectSyllabus] = []


class BulkDeleteSummary(BaseModel):
    """Result of a bulk soft-delete of students."""

    deleted: int


class BulkStudentUpdate(BaseModel):
    """Apply one field change to a set of selected students (roster bulk
    actions). Any field left null is untouched; ``batch_id`` reassigns each
    student's active batch mapping."""

    student_ids: list[uuid.UUID]
    fees_status: str | None = None
    standard: str | None = None
    stream: str | None = None
    batch_id: uuid.UUID | None = None


class BulkStudentDelete(BaseModel):
    student_ids: list[uuid.UUID]


class BulkActionSummary(BaseModel):
    """Result of a bulk field update — how many live students were changed."""

    updated: int


class ImportJobResponse(BaseModel):
    """A background import job — the UI polls this for a progress bar
    (processed_rows/total_rows) and, on completion, the result fields."""

    id: uuid.UUID
    job_status: str  # pending | processing | completed | failed
    filename: str | None = None
    total_rows: int = 0
    processed_rows: int = 0
    imported: int = 0
    skipped: int = 0
    subjects_created: int = 0
    errors: list[str] = []
    warnings: list[str] = []
    batches_created: list[str] = []
    academic_years_created: list[str] = []
    error_detail: str | None = None
    # Undo handle — the job id IS the import_id; null until rows persisted.
    import_id: uuid.UUID | None = None
    model_config = {"from_attributes": True}


class ImportSummary(BaseModel):
    imported: int
    skipped: int
    errors: list[str] = []
    # Non-blocking §3 advisories (e.g. 9th/10th targeting NEET) for rows that
    # were still imported.
    warnings: list[str] = []
    # Codes of batches auto-created during this import (when the admin
    # opted into "create missing batches").
    batches_created: list[str] = []
    # How many subject skeleton rows were auto-created for new courses (§8).
    subjects_created: int = 0
    # Academic years auto-created during this import (date-derived default
    # and/or from the Academic_year column), e.g. ["2026-27"].
    academic_years_created: list[str] = []
    # Handle to undo this import as a unit (design §9). Null when nothing
    # persisted, so the UI only offers undo when there's something to undo.
    import_id: uuid.UUID | None = None


class ImportUndoSummary(BaseModel):
    """Result of reversing a bulk import."""

    students_deleted: int
    batches_deleted: int
    subjects_deleted: int = 0
    parents_deleted: int = 0


class ImportPreviewBatch(BaseModel):
    """One distinct Batch code referenced by an upload, with whether it
    already exists and — when it does not — the course/exam-date we would
    derive from the rows' Target column if asked to create it."""

    code: str
    student_count: int
    exists: bool
    target: str | None = None
    suggested_course_code: str | None = None
    suggested_course_name: str | None = None
    suggested_exam_date: date | None = None
    # Whether auto-create would succeed for a missing code, and why not.
    # Existing batches are always creatable=True, blocker=None.
    creatable: bool = True
    blocker: str | None = None


class ImportPreview(BaseModel):
    """Dry-run of a student upload — surfaces row issues and the
    existing-vs-missing batch split before anything is written."""

    total_rows: int
    importable_rows: int
    rows_missing_name: int
    rows_invalid_enrolment: int
    # §3 cross-field contradictions that block a row, and non-blocking advisories.
    rows_invalid_consistency: int = 0
    rows_with_warnings: int = 0
    # Fuzzy possible duplicates (same name + phone/DOB) — imported with a warning.
    rows_possible_duplicate: int = 0
    duplicate_rows: int = 0
    unbatched_rows: int
    existing_batches: int
    missing_batches: int
    blocked_batches: int = 0
    # Reserved for a hard pre-commit stop; currently always null (academic
    # years are auto-derived, so an empty branch no longer blocks).
    blocking_error: str | None = None
    # Academic years the import would auto-create, e.g. ["2026-27", "2027-28"].
    new_academic_years: list[str] = []
    batches: list[ImportPreviewBatch] = []
    row_issues: list[str] = []
    # File header columns that match no known field — their data would be
    # silently dropped on import, so we surface them for the admin to notice
    # (in their original spelling), e.g. ["Mother Tongue", "Blood Group"].
    unrecognized_columns: list[str] = []


class StudentUpcomingTest(BaseModel):
    """A scheduled test for the student's batch they haven't taken yet —
    drives the Tier 13 'upcoming tests' section (soonest first)."""

    test_id: uuid.UUID
    test_name: str
    paper_type: str
    subject_name: str
    scheduled_at: datetime | None = None


class StudentTopicMastery(BaseModel):
    """Per-topic accuracy from a student's per-question responses — drives the
    Tier 13 weakness map (weakest topics first)."""

    topic_id: uuid.UUID
    topic_name: str
    subject_name: str
    attempted: int
    correct: int
    accuracy_pct: float


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
