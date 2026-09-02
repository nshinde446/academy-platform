import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.base import BaseModel


class Question(BaseModel):
    __tablename__ = "questions"

    content: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[str | None] = mapped_column(Text, nullable=True)
    correct_answer: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    subject_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("subjects.id"), nullable=False
    )
    topic_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("topics.id"), nullable=True
    )
    difficulty: Mapped[str] = mapped_column(
        String(20), nullable=False, default="MEDIUM"
    )
    blooms_taxonomy: Mapped[str] = mapped_column(
        String(20), nullable=False, default="REMEMBER"
    )
    concept_tags: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Provenance + quality (Tier 11.5). source examples:
    #   "PYQ-JEEMAIN-2019" | "PYQ-NEET-2022" | "studymat-{zip_name}"
    #   | "AI-DEEPSEEK" | "AI-GEMINI" | "HUMAN" | NULL (legacy/manual)
    source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    diagram_ref: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Drives the admin review queue. "approved" by default for legacy rows.
    review_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="approved", server_default="approved"
    )
    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    # M1 — link back to the source material (PDF/doc/etc.) this question
    # was extracted from. Nullable so legacy rows pre-backfill stay valid.
    material_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("materials.id"), nullable=True
    )
    # Inherited from material.exam_types at ingest; per-question override
    # allowed for PYQ datasets that span exams. ARRAY in Postgres prod;
    # JSON variant on SQLite (test suite) — SQLAlchemy converts list↔both.
    exam_types: Mapped[list[str]] = mapped_column(
        ARRAY(Text).with_variant(JSON(), "sqlite"),
        nullable=False, default=list,
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("branch.id"), nullable=False
    )
    academic_year_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("academic_years.id"), nullable=False
    )


class QuestionTopic(BaseModel):
    __tablename__ = "question_topics"

    question_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("questions.id"), nullable=False
    )
    topic_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("topics.id"), nullable=False
    )
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)


class QuestionMetadata(BaseModel):
    __tablename__ = "question_metadata"

    question_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("questions.id"), nullable=False
    )
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)


class Test(BaseModel):
    __tablename__ = "tests"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # DPP | CPP | TEST — the composer (M4) builds all three on this table.
    paper_type: Mapped[str] = mapped_column(
        String(10), nullable=False, default="TEST", server_default="TEST"
    )
    batch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("batches.id"), nullable=False
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("subjects.id"), nullable=False
    )
    scheduled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    total_marks: Mapped[float] = mapped_column(Float, nullable=False, default=100.0)
    test_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="DRAFT"
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("branch.id"), nullable=False
    )
    academic_year_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("academic_years.id"), nullable=False
    )
    # The completed lecture this paper was generated off, when the composer was
    # opened via the lectures "Generate DPP" flow. Powers DPP-coverage on the
    # lectures dashboard. Nullable: most papers aren't lecture-anchored.
    source_lecture_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("lectures.id"), nullable=True
    )
    # Test Portal (offline OMR flow): the OMR sheet layout the ZipGrade CSV was
    # scanned against, e.g. "50Q" | "100Q". NULL for composer-built papers.
    omr_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # Uploaded answer-key file kept for reference (Phase 1 doesn't score with it —
    # ZipGrade already scored). Stored path/key; set in PR-B.
    answer_key_file: Mapped[str | None] = mapped_column(String(500), nullable=True)


class TestSubject(BaseModel):
    """Subjects covered by a test (full multi-subject). ``tests.subject_id``
    still holds the first/primary subject for backward compatibility with the
    paper composer, ranking and student history."""

    __tablename__ = "test_subjects"

    test_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tests.id"), nullable=False
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("subjects.id"), nullable=False
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("branch.id"), nullable=False
    )


class TestImportReview(BaseModel):
    """A ZipGrade CSV row whose PRN didn't match any student in the test's batch
    — flagged for an admin to fix (typo / wrong batch). Resolution (assign a
    student -> create a StudentMark) lands in PR-B."""

    __tablename__ = "test_import_review"

    test_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tests.id"), nullable=False
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("branch.id"), nullable=False
    )
    csv_prn: Mapped[str | None] = mapped_column(String(100), nullable=True)
    csv_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    raw_row: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    resolved: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    resolved_student_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("students.id"), nullable=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class TestQuestion(BaseModel):
    __tablename__ = "test_questions"

    test_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tests.id"), nullable=False
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("questions.id"), nullable=False
    )
    marks_allocated: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class StudentMark(BaseModel):
    __tablename__ = "student_marks"

    student_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("students.id"), nullable=False
    )
    test_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tests.id"), nullable=False
    )
    marks_obtained: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    max_marks: Mapped[float] = mapped_column(Float, nullable=False, default=100.0)
    percentage: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    grade: Mapped[str | None] = mapped_column(String(10), nullable=True)
    is_absent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Original ZipGrade CSV row this mark came from (audit / re-processing).
    # NULL for marks entered by hand.
    raw_csv_row: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    marked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    marked_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=True
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("branch.id"), nullable=False
    )
    academic_year_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("academic_years.id"), nullable=False
    )


class StudentResponse(BaseModel):
    """Per-question student answer (Tier 11).

    Foundation for topic mastery, item analysis, weakness identification.
    The aggregate `StudentMark` row is recomputed from these by the
    service whenever responses are submitted in bulk.
    """

    __tablename__ = "student_responses"

    student_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("students.id"), nullable=False
    )
    test_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tests.id"), nullable=False
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("questions.id"), nullable=False
    )
    # Option letter ("A"|"B"|"C"|"D") or free text for integer/short-answer.
    selected_answer: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_correct: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    marks_obtained: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, server_default="0.0"
    )
    submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("branch.id"), nullable=False
    )
    academic_year_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("academic_years.id"), nullable=False
    )
