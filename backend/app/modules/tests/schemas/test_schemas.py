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
    subject_id: uuid.UUID
    scheduled_at: datetime | None = None
    duration_minutes: int = 60
    total_marks: float = 100.0
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
    scheduled_at: datetime | None = None
    duration_minutes: int
    total_marks: float
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
