import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.base import BaseModel


class AcademicEvent(BaseModel):
    __tablename__ = "academic_events"

    event_id: Mapped[uuid.UUID] = mapped_column(Uuid, unique=True, nullable=False)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    student_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("students.id"), nullable=True
    )
    teacher_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("teachers.id"), nullable=True
    )
    batch_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("batches.id"), nullable=True
    )
    subject_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("subjects.id"), nullable=True
    )
    topic_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("topics.id"), nullable=True
    )
    lecture_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("lectures.id"), nullable=True
    )
    test_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("tests.id"), nullable=True
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    processed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    branch_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("branch.id"), nullable=True
    )


class ProcessedEvent(BaseModel):
    __tablename__ = "processed_events"

    event_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    consumer_name: Mapped[str] = mapped_column(String(100), nullable=False)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    processing_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="SUCCESS"
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
