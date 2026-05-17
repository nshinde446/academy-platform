import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.base import BaseModel


class Lecture(BaseModel):
    __tablename__ = "lectures"

    teacher_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("teachers.id"), nullable=False
    )
    batch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("batches.id"), nullable=False
    )
    classroom_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("classrooms.id"), nullable=True
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("subjects.id"), nullable=False
    )
    topic_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("topics.id"), nullable=True
    )
    scheduled_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    scheduled_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    actual_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    actual_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    delivery_mode: Mapped[str] = mapped_column(
        String(20), nullable=False, default="offline"
    )
    lecture_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="scheduled"
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    branch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("branch.id"), nullable=False
    )
    academic_year_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("academic_years.id"), nullable=False
    )


class LectureTopicMapping(BaseModel):
    __tablename__ = "lecture_topic_mappings"

    lecture_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("lectures.id"), nullable=False
    )
    topic_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("topics.id"), nullable=False
    )
    order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    branch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("branch.id"), nullable=False
    )


class LectureAttendanceMapping(BaseModel):
    __tablename__ = "lecture_attendance_mappings"

    lecture_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("lectures.id"), nullable=False
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("students.id"), nullable=False
    )
    attendance_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="PRESENT"
    )
    marked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("branch.id"), nullable=False
    )
