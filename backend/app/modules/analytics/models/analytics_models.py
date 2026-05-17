import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.base import BaseModel


class AnalyticsStudentSummary(BaseModel):
    __tablename__ = "analytics_student_summary"

    student_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("students.id"), nullable=False
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("branch.id"), nullable=False
    )
    academic_year_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("academic_years.id"), nullable=False
    )
    total_attendance: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    present_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    absent_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    late_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    attendance_percentage: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_tests: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    average_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    weak_topics: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class AnalyticsTeacherSummary(BaseModel):
    __tablename__ = "analytics_teacher_summary"

    teacher_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("teachers.id"), nullable=False
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("branch.id"), nullable=False
    )
    academic_year_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("academic_years.id"), nullable=False
    )
    total_lectures: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completed_lectures: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completion_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    avg_delay_minutes: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    avg_student_attendance: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class AnalyticsBatchSummary(BaseModel):
    __tablename__ = "analytics_batch_summary"

    batch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("batches.id"), nullable=False
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("branch.id"), nullable=False
    )
    academic_year_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("academic_years.id"), nullable=False
    )
    total_students: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avg_attendance: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    avg_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    weak_subjects: Mapped[str | None] = mapped_column(Text, nullable=True)
    top_performers: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
