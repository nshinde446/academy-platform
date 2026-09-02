import uuid
from datetime import datetime

from pydantic import BaseModel


class QuestionCreate(BaseModel):
    content: str
    options: dict | None = None
    correct_answer: str
    explanation: str | None = None
    subject_id: uuid.UUID
    topic_id: uuid.UUID | None = None
    difficulty: str = "MEDIUM"
    blooms_taxonomy: str = "REMEMBER"
    concept_tags: list[str] | None = None


class QuestionUpdate(BaseModel):
    content: str | None = None
    options: dict | None = None
    correct_answer: str | None = None
    explanation: str | None = None
    subject_id: uuid.UUID | None = None
    topic_id: uuid.UUID | None = None
    difficulty: str | None = None
    blooms_taxonomy: str | None = None
    concept_tags: list[str] | None = None
    review_status: str | None = None


class QuestionResponse(BaseModel):
    id: uuid.UUID
    content: str
    options: dict | None = None
    correct_answer: str
    explanation: str | None = None
    subject_id: uuid.UUID
    topic_id: uuid.UUID | None = None
    difficulty: str
    blooms_taxonomy: str
    concept_tags: list[str] | None = None
    source: str | None = None
    source_ref: str | None = None
    diagram_ref: str | None = None
    review_status: str
    quality_score: float | None = None
    branch_id: uuid.UUID
    academic_year_id: uuid.UUID
    status: str
    model_config = {"from_attributes": True}


class QuestionBulkAction(BaseModel):
    """Bulk approve / reject payload."""
    question_ids: list[uuid.UUID]


class QuestionBulkResult(BaseModel):
    updated: int
    skipped: list[uuid.UUID] = []


class TestCreate(BaseModel):
    name: str
    description: str | None = None
    paper_type: str = "TEST"  # DPP | CPP | TEST
    batch_id: uuid.UUID
    # A test covers one or more subjects (full multi-subject). Either field may
    # be given: `subject_ids` for the Test Portal multi-subject flow, or the
    # legacy single `subject_id` (paper composer). The primary subject_id is set
    # to the first of subject_ids when only that is provided.
    subject_id: uuid.UUID | None = None
    subject_ids: list[uuid.UUID] | None = None
    scheduled_at: datetime | None = None
    duration_minutes: int = 60
    total_marks: float = 100.0
    # OMR sheet layout the ZipGrade CSV is scanned against ("50Q" | "100Q").
    omr_type: str | None = None
    # Optional link back to the lecture this paper was generated from
    # (set by the lectures "Generate DPP" flow → DPP-coverage metric).
    source_lecture_id: uuid.UUID | None = None


class TestResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None = None
    paper_type: str
    batch_id: uuid.UUID
    subject_id: uuid.UUID
    subject_ids: list[uuid.UUID] = []
    scheduled_at: datetime | None = None
    duration_minutes: int
    total_marks: float
    omr_type: str | None = None
    answer_key_file: str | None = None
    test_status: str
    branch_id: uuid.UUID
    academic_year_id: uuid.UUID
    source_lecture_id: uuid.UUID | None = None
    status: str
    model_config = {"from_attributes": True}


class AutoPickRequest(BaseModel):
    """Composer auto-pick: draw N questions from the bank by facets (M4).

    Either pass `difficulty_mix` (e.g. {"EASY": 4, "MEDIUM": 6, "HARD": 2})
    for a balanced paper, or `count` for any-difficulty selection. Picks
    are randomized server-side and exclude `exclude_ids` (used by
    reshuffle / swap). Defaults to approved questions only.
    """

    subject_id: uuid.UUID | None = None
    class_label: str | None = None
    topic: str | None = None
    exam_type: str | None = None
    review_status: str = "approved"
    difficulty_mix: dict[str, int] | None = None
    count: int | None = None
    exclude_ids: list[uuid.UUID] = []


class TestQuestionAdd(BaseModel):
    question_id: uuid.UUID
    marks_allocated: float = 1.0
    order: int = 0


class TestQuestionsAdd(BaseModel):
    questions: list[TestQuestionAdd]


class MarkSubmit(BaseModel):
    student_id: uuid.UUID
    marks_obtained: float
    is_absent: bool = False


class MarkBatchSubmit(BaseModel):
    marks: list[MarkSubmit]


class MarkResponse(BaseModel):
    id: uuid.UUID
    student_id: uuid.UUID
    test_id: uuid.UUID
    marks_obtained: float
    max_marks: float
    percentage: float
    grade: str | None = None
    is_absent: bool
    marked_at: datetime | None = None
    branch_id: uuid.UUID
    academic_year_id: uuid.UUID
    status: str
    model_config = {"from_attributes": True}


class ResponseSubmit(BaseModel):
    """One student's answer to one question on a test."""

    student_id: uuid.UUID
    question_id: uuid.UUID
    selected_answer: str | None = None


class ResponseBulkSubmit(BaseModel):
    """Bulk submit per-question responses (Tier 11).

    Auto-rolls up to StudentMark on the server. Replaces existing
    responses for the same (student, test, question) triple (so re-runs
    are idempotent).
    """

    responses: list[ResponseSubmit]


class ResponseBulkResult(BaseModel):
    test_id: uuid.UUID
    inserted: int
    updated: int
    students_marked: int
    errors: list[str] = []


class StudentResponseRow(BaseModel):
    id: uuid.UUID
    student_id: uuid.UUID
    test_id: uuid.UUID
    question_id: uuid.UUID
    selected_answer: str | None = None
    is_correct: bool
    marks_obtained: float
    submitted_at: datetime | None = None
    branch_id: uuid.UUID
    academic_year_id: uuid.UUID
    status: str
    model_config = {"from_attributes": True}


class TestReportResponse(BaseModel):
    test_id: uuid.UUID
    total_students: int
    appeared: int
    absent: int
    average: float
    highest: float
    lowest: float
    pass_count: int
    fail_count: int


# ── Test Portal: CSV upload + rank list ─────────────────────────────────────


class UploadResultSummary(BaseModel):
    """Outcome counts after a ZipGrade CSV upload (§4.4)."""
    matched: int
    needs_review: int
    absent: int
    total_rows: int


class RankRow(BaseModel):
    rank: int | None = None  # null for absentees
    student_id: uuid.UUID
    prn: str | None = None
    name: str
    marks_obtained: float | None = None
    percentage: float | None = None
    absent: bool = False


class ReviewRow(BaseModel):
    id: uuid.UUID
    csv_prn: str | None = None
    csv_name: str | None = None
    resolved: bool = False


class RankListResponse(BaseModel):
    test_id: uuid.UUID
    test_name: str
    total_marks: float
    ranked: list[RankRow]       # appeared, highest → lowest
    absentees: list[RankRow]    # grouped at the bottom
    needs_review: list[ReviewRow]  # unmatched CSV rows (excluded from ranking)


class ResolveReviewRequest(BaseModel):
    """Assign an unmatched ZipGrade row to a student (PR-B)."""
    student_id: uuid.UUID


class ResolveReviewResult(BaseModel):
    resolved: bool
    student_id: uuid.UUID
    marks_obtained: float


class AnswerKeyInfo(BaseModel):
    """Result of an answer-key upload."""
    answer_key_file: str
    filename: str
