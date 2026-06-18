import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, String, Time, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.base import BaseModel


class Batch(BaseModel):
    __tablename__ = "batches"

    branch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("branch.id"), nullable=False
    )
    start_academic_year_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("academic_years.id"), nullable=False
    )
    end_academic_year_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("academic_years.id"), nullable=False
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("courses.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    # Target exam date (e.g. NEET on 2026-05-04). Drives time-weighted
    # syllabus pace on /insights and /teachers detail. When null the
    # service falls back to mid-May of the end academic year.
    target_exam_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # Set when a batch was auto-created by a student import (design §9), so an
    # "undo import" can reclaim the batches that import spun up. Null for
    # batches created manually on the Batches page.
    import_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, nullable=True, index=True
    )


class BatchSubjectMapping(BaseModel):
    __tablename__ = "batch_subject_mappings"

    batch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("batches.id"), nullable=False
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("subjects.id"), nullable=False
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("branch.id"), nullable=False
    )


class BatchSchedule(BaseModel):
    __tablename__ = "batch_schedules"

    batch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("batches.id"), nullable=False
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("branch.id"), nullable=False
    )
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)
    start_time: Mapped[str] = mapped_column(String(10), nullable=False)
    end_time: Mapped[str] = mapped_column(String(10), nullable=False)
