import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, Uuid
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
    # Derived from the actuals (see lecture_service._derive_actuals), persisted
    # so the teacher-productivity report can aggregate/index without recomputing
    # the formula per row. late_flag = actual_start > scheduled_start + 10 min.
    late_flag: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    actual_duration_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    delivery_mode: Mapped[str] = mapped_column(
        String(20), nullable=False, default="offline"
    )
    lecture_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="scheduled"
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Plan-vs-actual tracking. If actual_teacher_id is set, it overrides
    # teacher_id for "who actually delivered this lecture" reporting.
    # change_reason: SUBSTITUTE | SUBJECT_SWAP | TOPIC_CHANGE | COMBINED_BATCH | OTHER
    actual_teacher_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("teachers.id"), nullable=True
    )
    change_reason: Mapped[str | None] = mapped_column(String(40), nullable=True)
    change_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Set together with lecture_status='no_show'. Reason buckets:
    # TEACHER_NO_SHOW | STUDENT_NO_SHOW | EXTERNAL | OTHER
    no_show_reason: Mapped[str | None] = mapped_column(String(40), nullable=True)
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


class LectureSession(BaseModel):
    """A teaching event that actually happened.

    Tier 2 of Plan-vs-Actual. A session may be linked to 0 lectures (pure
    ad-hoc / makeup), 1 lecture (normal case), or 2+ lectures (merged
    batches taught together). origin distinguishes how it was created.
    """

    __tablename__ = "lecture_sessions"

    teacher_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("teachers.id"), nullable=False
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
    actual_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    actual_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    delivery_mode: Mapped[str] = mapped_column(
        String(20), nullable=False, default="offline"
    )
    session_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="completed"
    )
    # planned | makeup | ad_hoc
    origin: Mapped[str] = mapped_column(String(20), nullable=False, default="planned")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    branch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("branch.id"), nullable=False
    )
    academic_year_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("academic_years.id"), nullable=False
    )


class LectureSessionPlan(BaseModel):
    """Join between a session and the lecture plan(s) it fulfils.

    Zero rows for ad_hoc sessions; one for normal; two+ for merged batches.
    """

    __tablename__ = "lecture_session_plans"

    session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("lecture_sessions.id"), nullable=False
    )
    lecture_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("lectures.id"), nullable=False
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("branch.id"), nullable=False
    )


class LectureSessionBatch(BaseModel):
    """Join between a session and the batch(es) that attended it.

    A session must have at least one batch. Stored separately from plans so
    ad-hoc sessions (no plan) can still record which batch attended.
    """

    __tablename__ = "lecture_session_batches"

    session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("lecture_sessions.id"), nullable=False
    )
    batch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("batches.id"), nullable=False
    )
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
