import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.base import BaseModel


class RawPunchLog(BaseModel):
    __tablename__ = "raw_punch_logs"

    device_id: Mapped[str] = mapped_column(String(100), nullable=False)
    sync_batch_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("students.id"), nullable=False
    )
    punch_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    # Device-reported punch direction when available ("IN" / "OUT"). Many
    # devices omit it, so it's nullable and the day aggregator infers direction
    # (first punch = IN, last = OUT) when missing. See docs/biometric-attendance-design.md.
    direction: Mapped[str | None] = mapped_column(String(10), nullable=True)
    branch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("branch.id"), nullable=False
    )


class DailyAttendance(BaseModel):
    """Population campus-presence for one student on one LOCAL day (Layer 1).

    Canonical for a student's daily attendance %; per-lecture
    ``attendance_records`` are projected from this. Renders both reference
    exports (per-student timeline and classroom P/A register). See
    docs/biometric-attendance-design.md.
    """

    __tablename__ = "daily_attendance"
    __table_args__ = (
        UniqueConstraint(
            "student_id", "attendance_date", name="uq_daily_attendance_student_date"
        ),
    )

    student_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("students.id"), nullable=False
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("branch.id"), nullable=False
    )
    # Branch-LOCAL calendar date this row represents (not UTC).
    attendance_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    # First / last punch of the day (tz-aware UTC instants). NULL when absent;
    # last_out NULL also means "punched in, never out" (signoff=MISSING).
    first_in: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_out: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # PRESENT | LATE | ABSENT
    day_status: Mapped[str] = mapped_column(String(20), nullable=False)
    # COMPLETE | MISSING | NA  (NA = absent, no punches at all)
    signoff: Mapped[str] = mapped_column(String(20), nullable=False, default="NA")
    # BIOMETRIC | MANUAL | SYSTEM (SYSTEM = absent sweep)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="BIOMETRIC")
    # Set when a human edits the row; a MANUAL row is never clobbered by rebuild.
    override_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=True
    )
    override_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class AttendanceRecord(BaseModel):
    __tablename__ = "attendance_records"

    student_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("students.id"), nullable=False
    )
    lecture_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("lectures.id"), nullable=False
    )
    attendance_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="ABSENT"
    )
    marked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    marked_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=True
    )
    source: Mapped[str] = mapped_column(
        String(20), nullable=False, default="MANUAL"
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("branch.id"), nullable=False
    )


class AttendanceException(BaseModel):
    __tablename__ = "attendance_exceptions"

    student_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("students.id"), nullable=False
    )
    lecture_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("lectures.id"), nullable=False
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    resolved: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=True
    )
    resolution_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    branch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("branch.id"), nullable=False
    )
