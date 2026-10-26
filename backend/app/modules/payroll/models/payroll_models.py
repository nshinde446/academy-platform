"""Payroll module — days-based payroll tables (new tables only).

The Payroll module sits *on top of* the existing staff attendance: it reads
``StaffDailyAttendance`` (Full day = 1, Half day = 0.5) and the existing late
fine, and never changes either. See ``docs/payroll-module.md`` for the full
business logic; the spec is ``Payroll_Module_Explained.pdf``.

Six new tables plus a key/value ``payroll_config``. Existing attendance, shift,
late-fine and audit tables are reused and untouched. Everything is branch-scoped
and soft-deletable (``BaseModel``) except the append-only ledger, which is never
edited or deleted — a correction is a new ``reversal`` row (enforced at the DB
level by a trigger on Postgres, see migration 0069).
"""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database.base import Base, BaseModel

# Month lifecycle (§6) and request/ledger/holiday enumerations, kept as plain
# strings (the codebase convention) rather than DB enums so a new value never
# needs a migration.
MONTH_STATUSES = ("OPEN", "CLOSED", "LOCKED")
REQUEST_STATUSES = ("PENDING", "APPROVED", "REJECTED", "CANCELLED", "EXPIRED")
# Statuses that hold a "live" claim on a staff-month (one at a time, see the
# partial unique index on ``extra_day_requests``).
REQUEST_ACTIVE_STATUSES = ("PENDING", "APPROVED")
LEDGER_ENTRY_TYPES = (
    "extra_added",
    "compensation_used",
    "cap_trim",
    "makeup_credit",
    "reversal",
    "manual_adjustment",
)
HOLIDAY_KINDS = ("HOLIDAY", "LEAVE")

# Numeric precision for day counts. Days move in 0.5 steps (half days), so one
# decimal place is enough; money (late fine) keeps two.
_DAYS = Numeric(6, 1)
_MONEY = Numeric(10, 2)


class PayrollMonthSettings(BaseModel):
    """Per-month, per-branch payroll setup (§1). Super Admin sets the required
    working days for the month (applies to all staff) and the month moves
    OPEN → CLOSED → LOCKED over its lifecycle (§6)."""

    __tablename__ = "payroll_month_settings"
    __table_args__ = (
        Index(
            "uq_payroll_month_settings_branch_ym",
            "branch_id",
            "year",
            "month",
            unique=True,
            postgresql_where=text("is_deleted = false"),
            sqlite_where=text("is_deleted = 0"),
        ),
    )

    branch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("branch.id"), nullable=False
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)  # 1–12
    required_days: Mapped[float] = mapped_column(_DAYS, nullable=False)
    # Month lifecycle (§6): OPEN | CLOSED | LOCKED. Distinct from BaseModel.status
    # (the generic active/inactive record flag), which is left untouched.
    lifecycle: Mapped[str] = mapped_column(
        String(10), nullable=False, server_default="OPEN", default="OPEN"
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class PayrollMonthHoliday(BaseModel):
    """A paid holiday or leave the Super Admin declares for a month (§1). Counts
    as ``credit_days`` credited days by default (configurable in payroll_config:
    ``holiday_treatment``). Shown in the setup screen and the report."""

    __tablename__ = "payroll_month_holidays"
    __table_args__ = (
        Index(
            "ix_payroll_month_holidays_branch_ym",
            "branch_id",
            "year",
            "month",
        ),
    )

    branch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("branch.id"), nullable=False
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    holiday_date: Mapped[date] = mapped_column(Date, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    # HOLIDAY | LEAVE
    kind: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="HOLIDAY", default="HOLIDAY"
    )
    credit_days: Mapped[float] = mapped_column(
        Numeric(3, 1), nullable=False, server_default="1.0", default=1.0
    )


class PayrollStaffMonth(BaseModel):
    """The computed payroll row for one staff member in one month (§2, §7). A
    snapshot of the month-end calculation — required/credited/net/extra/shortfall,
    carry-forward in and out, and the late-fine total — recomputed freely while
    the month is OPEN and frozen once it is CLOSED."""

    __tablename__ = "payroll_staff_month"
    __table_args__ = (
        UniqueConstraint(
            "staff_id",
            "year",
            "month",
            name="uq_payroll_staff_month_staff_ym",
        ),
        Index("ix_payroll_staff_month_branch_ym", "branch_id", "year", "month"),
    )

    branch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("branch.id"), nullable=False
    )
    staff_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("staff.id"), nullable=False
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)

    # Inputs / effective targets.
    required_days: Mapped[float] = mapped_column(_DAYS, nullable=False, default=0)
    makeup_days: Mapped[float] = mapped_column(_DAYS, nullable=False, default=0)
    # Effective required = required + makeup (stored so the report needn't re-add).
    effective_required: Mapped[float] = mapped_column(_DAYS, nullable=False, default=0)

    # Credited breakdown (present + paid leave/holiday). ``present_days`` already
    # folds half days at 0.5; ``half_days`` is the raw count, shown per §7.
    present_days: Mapped[float] = mapped_column(_DAYS, nullable=False, default=0)
    half_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    paid_leave_days: Mapped[float] = mapped_column(_DAYS, nullable=False, default=0)
    credited_days: Mapped[float] = mapped_column(_DAYS, nullable=False, default=0)

    # Results.
    net_days: Mapped[float] = mapped_column(_DAYS, nullable=False, default=0)
    extra_days: Mapped[float] = mapped_column(_DAYS, nullable=False, default=0)
    shortfall_days: Mapped[float] = mapped_column(_DAYS, nullable=False, default=0)
    balance_in: Mapped[float] = mapped_column(_DAYS, nullable=False, default=0)
    balance_out: Mapped[float] = mapped_column(_DAYS, nullable=False, default=0)
    # Shortfall left after the carry-forward balance was applied.
    uncovered_days: Mapped[float] = mapped_column(_DAYS, nullable=False, default=0)
    # Uncovered shortfall that an approved extra-day request deferred — not unpaid.
    deferred_days: Mapped[float] = mapped_column(_DAYS, nullable=False, default=0)
    late_fine_total: Mapped[float] = mapped_column(_MONEY, nullable=False, default=0)

    # Mirrors the owning month's lifecycle (§6) so a row carries its own state.
    # Distinct from BaseModel.status (generic active/inactive).
    lifecycle: Mapped[str] = mapped_column(
        String(10), nullable=False, server_default="OPEN", default="OPEN"
    )


class CarryForwardLedger(BaseModel):
    """Append-only carry-forward ledger (§4). One row per balance movement, with
    a running balance that can never go below zero. Nothing is ever edited or
    deleted — a correction is a new ``reversal`` row. Append-only is enforced at
    the DB level (trigger, migration 0069) in addition to the service never
    issuing an UPDATE or DELETE. ``created_by`` / ``created_at`` are the "who" and
    "when"; ``is_deleted`` is always false and exists only for ``BaseModel``
    uniformity."""

    __tablename__ = "carry_forward_ledger"
    __table_args__ = (
        Index(
            "ix_carry_forward_ledger_staff",
            "branch_id",
            "staff_id",
            "year",
            "month",
        ),
    )

    branch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("branch.id"), nullable=False
    )
    staff_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("staff.id"), nullable=False
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    # Per-staff monotonic sequence, assigned on append. Gives a stable total
    # order within a staff's ledger even when several rows are written in one
    # transaction (Postgres ``now()`` is identical across a transaction, so
    # ``created_at`` can't order them).
    seq: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0", default=0
    )
    # extra_added | compensation_used | cap_trim | makeup_credit | reversal |
    # manual_adjustment
    entry_type: Mapped[str] = mapped_column(String(30), nullable=False)
    # Signed day movement (+ adds to balance, − consumes it).
    days: Mapped[float] = mapped_column(_DAYS, nullable=False)
    running_balance: Mapped[float] = mapped_column(_DAYS, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class ExtraDayRequest(BaseModel):
    """A request to make up an uncovered shortfall next month (§5). Raised by HR /
    Accounts / Branch Admin, approved by the Super Admin. Only one active (PENDING
    or APPROVED) request per staff per source month — enforced by the partial
    unique index below and re-checked in the service."""

    __tablename__ = "extra_day_requests"
    __table_args__ = (
        # One live claim (pending or approved) per staff per source month.
        Index(
            "uq_extra_day_request_active",
            "branch_id",
            "staff_id",
            "source_year",
            "source_month",
            unique=True,
            postgresql_where=text(
                "is_deleted = false AND request_status IN ('PENDING', 'APPROVED')"
            ),
            sqlite_where=text(
                "is_deleted = 0 AND request_status IN ('PENDING', 'APPROVED')"
            ),
        ),
    )

    branch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("branch.id"), nullable=False
    )
    staff_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("staff.id"), nullable=False
    )
    # The month that closed with the uncovered shortfall.
    source_year: Mapped[int] = mapped_column(Integer, nullable=False)
    source_month: Mapped[int] = mapped_column(Integer, nullable=False)
    # The month the make-up days are added to (required + N). Normally source + 1.
    target_year: Mapped[int] = mapped_column(Integer, nullable=False)
    target_month: Mapped[int] = mapped_column(Integer, nullable=False)
    shortfall_days: Mapped[float] = mapped_column(_DAYS, nullable=False)
    # Workflow status (§5): PENDING | APPROVED | REJECTED | CANCELLED | EXPIRED.
    # Named ``request_status`` to leave BaseModel.status (active/inactive) intact.
    request_status: Mapped[str] = mapped_column(
        String(12), nullable=False, server_default="PENDING", default="PENDING"
    )
    requested_by: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    decided_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class ExtraDayRequestHistory(Base):
    """Append-only history of every status change on an extra-day request (§5) —
    who, when and a note. Separate from the business audit log so the request
    drawer can show its own timeline cheaply."""

    __tablename__ = "extra_day_request_history"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    request_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("extra_day_requests.id"), nullable=False, index=True
    )
    from_status: Mapped[str | None] = mapped_column(String(12), nullable=True)
    to_status: Mapped[str] = mapped_column(String(12), nullable=False)
    changed_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class PayrollConfig(Base):
    """Key/value payroll settings (§8), seeded with the spec defaults (migration
    0069) so each can change without a deploy. ``value`` is JSON so each key keeps
    its natural type. Mirrors ``teacher_portal_config``."""

    __tablename__ = "payroll_config"

    key: Mapped[str] = mapped_column(String(50), primary_key=True)
    value: Mapped[object] = mapped_column(JSON, nullable=False)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
