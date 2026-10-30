import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.base import BaseModel

# Leave request lifecycle. "approved" is the default so existing admin-created
# leaves (pre-0068) keep blocking scheduling exactly as before.
LEAVE_STATUSES = frozenset({"pending", "approved", "rejected"})


class Teacher(BaseModel):
    __tablename__ = "teachers"

    branch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("branch.id"), nullable=False
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=True
    )
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    qualification: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Years of teaching experience — surfaced on the teachers list.
    years_experience: Mapped[int | None] = mapped_column(Integer, nullable=True)


class TeacherSubjectMapping(BaseModel):
    __tablename__ = "teacher_subject_mappings"

    teacher_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("teachers.id"), nullable=False
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("subjects.id"), nullable=False
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("branch.id"), nullable=False
    )


class TeacherLeave(BaseModel):
    """A teacher's planned unavailability (inclusive start_date … end_date).

    Scheduling rejects a lecture that lands on a teacher's leave, and the
    substitute suggester excludes teachers who are on leave (S5)."""

    __tablename__ = "teacher_leaves"

    teacher_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("teachers.id"), nullable=False
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("branch.id"), nullable=False
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    end_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Leave classification (migration 0071, Teacher Portal Changes §4). One of
    # casual | sick | paid | lwp (Leave Without Pay, no quota). Defaults to
    # "casual" so pre-0071 rows keep a sensible type.
    leave_type: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="casual", default="casual"
    )
    # A half-day leave counts as 0.5 day (single date). Full day otherwise.
    half_day: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false", default=False
    )

    # Approval workflow (migration 0068). Self-service requests start "pending"
    # and only block scheduling once "approved". Admin-created leaves and all
    # pre-0068 rows default to "approved" so behaviour is unchanged for them.
    # NOTE: named approval_status, NOT status — BaseModel already defines a
    # generic `status` column (active/inactive); reusing it would both clash on
    # the ADD COLUMN and carry the wrong default ("active").
    approval_status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="approved",
        default="approved", index=True,
    )
    requested_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    decided_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    decision_note: Mapped[str | None] = mapped_column(String(255), nullable=True)


class LeaveTypeQuota(BaseModel):
    """Per-branch, per-calendar-year leave quota for a leave type (migration
    0071). Set by the Super Admin in Leave Settings. ``leave_type`` matches
    TeacherLeave.leave_type; LWP has no quota row (unlimited). No carry-over."""

    __tablename__ = "leave_type_quotas"
    __table_args__ = (
        UniqueConstraint(
            "branch_id", "year", "leave_type", name="uq_leave_type_quota"
        ),
    )

    branch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("branch.id"), nullable=False
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    leave_type: Mapped[str] = mapped_column(String(20), nullable=False)
    quota_days: Mapped[float] = mapped_column(Numeric(5, 1), nullable=False)


class TeacherWofOpening(BaseModel):
    """A teacher's opening Weekly-Off / banked-leave balance as of a date
    (migration 0071). The live WOF balance = this opening + the extra days worked
    since (present − 24 per month, see teacher_portal.wof_service). Seeded from
    the client's 'WOF Till Sept 26' list."""

    __tablename__ = "teacher_wof_openings"
    __table_args__ = (
        UniqueConstraint("teacher_id", name="uq_teacher_wof_opening"),
    )

    teacher_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("teachers.id"), nullable=False
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("branch.id"), nullable=False
    )
    opening_balance: Mapped[float] = mapped_column(Numeric(6, 1), nullable=False)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)


class TeacherBatchMapping(BaseModel):
    __tablename__ = "teacher_batch_mappings"

    teacher_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("teachers.id"), nullable=False
    )
    batch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("batches.id"), nullable=False
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("branch.id"), nullable=False
    )


class TeacherBatchSubjectMapping(BaseModel):
    """A SECONDARY subject a teacher teaches for a SPECIFIC batch — on top of
    their core subject(s) in ``TeacherSubjectMapping``, which are never touched.

    This is what lets a core-Maths teacher be scheduled for IT in Batch D & E
    only. The Subject→Teacher lock treats a (teacher, subject, batch) row here
    exactly like a core-subject qualification, but scoped to that one batch.
    """

    __tablename__ = "teacher_batch_subject_mappings"
    __table_args__ = (
        # One live row per (teacher, subject, batch).
        Index(
            "uq_teacher_batch_subject",
            "teacher_id",
            "subject_id",
            "batch_id",
            unique=True,
            postgresql_where=text("is_deleted = false"),
            sqlite_where=text("is_deleted = 0"),
        ),
    )

    teacher_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("teachers.id"), nullable=False
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("subjects.id"), nullable=False
    )
    batch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("batches.id"), nullable=False
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("branch.id"), nullable=False
    )
