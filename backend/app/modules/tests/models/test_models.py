import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, Uuid
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
