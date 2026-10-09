"""Accounts / Fees module models (spec Section 10).

Five tables: a per-course standard fee, a per-student fee profile created at
admission, its installment schedule, the payments received, and the call-log
remarks. ``created_by`` (from BaseModel) is the staff who created each row — it
serves as the spec's ``recorded_by`` (PaymentRecords) and ``created_by``
(FeeRemarks); we never add a duplicate column for it.
"""

import uuid
from datetime import date

from sqlalchemy import Date, Float, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.base import BaseModel

# payment_mode on the profile
ONE_TIME = "ONE_TIME"
INSTALLMENT = "INSTALLMENT"

# installment status
PENDING = "PENDING"
PAID = "PAID"
OVERDUE = "OVERDUE"
PARTIAL = "PARTIAL"

# payment instrument
PAYMENT_MODES = {"CASH", "UPI", "CHEQUE", "BANK_TRANSFER"}


class CourseFeeConfig(BaseModel):
    """Standard (default) fee for a course, per branch. Auto-fills a new fee
    profile's actual_fee; changing it affects only NEW admissions (spec §1)."""

    __tablename__ = "course_fee_configs"

    course_name: Mapped[str] = mapped_column(String(50), nullable=False)  # CET / JEE / NEET
    standard_fee: Mapped[float] = mapped_column(Float, nullable=False)
    branch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("branch.id"), nullable=False
    )


class StudentFeeProfile(BaseModel):
    """One fee profile per student, created at admission (spec §2 / §10.2)."""

    __tablename__ = "student_fee_profiles"

    student_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("students.id"), nullable=False
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("branch.id"), nullable=False
    )
    batch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("batches.id"), nullable=False
    )
    actual_fee: Mapped[float] = mapped_column(Float, nullable=False)
    agreed_fee: Mapped[float] = mapped_column(Float, nullable=False)
    discount_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    payment_mode: Mapped[str] = mapped_column(String(20), nullable=False)  # ONE_TIME | INSTALLMENT
    total_paid: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_pending: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    admission_date: Mapped[date] = mapped_column(Date, nullable=False)


class Installment(BaseModel):
    """One row per installment of a student's plan (spec §10.3)."""

    __tablename__ = "fee_installments"

    profile_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("student_fee_profiles.id"), nullable=False
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("students.id"), nullable=False
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("branch.id"), nullable=False
    )
    installment_number: Mapped[int] = mapped_column(nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    # PENDING | PAID | OVERDUE | PARTIAL
    installment_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=PENDING, server_default=PENDING
    )
    paid_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    paid_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    payment_mode: Mapped[str | None] = mapped_column(String(20), nullable=True)


class PaymentRecord(BaseModel):
    """Every payment received — one installment can have several (spec §10.4).
    ``created_by`` (BaseModel) is the staff who recorded it."""

    __tablename__ = "fee_payment_records"

    student_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("students.id"), nullable=False
    )
    installment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("fee_installments.id"), nullable=False
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("branch.id"), nullable=False
    )
    amount_paid: Mapped[float] = mapped_column(Float, nullable=False)
    payment_date: Mapped[date] = mapped_column(Date, nullable=False)
    payment_mode: Mapped[str] = mapped_column(String(20), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class FeeRemark(BaseModel):
    """Call-log entry — one per conversation (spec §10.5). ``created_by``
    (BaseModel) is the staff who made the call; ``next_followup_date`` drives the
    Commitments list."""

    __tablename__ = "fee_remarks"

    student_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("students.id"), nullable=False
    )
    profile_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("student_fee_profiles.id"), nullable=False
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("branch.id"), nullable=False
    )
    remark_text: Mapped[str] = mapped_column(Text, nullable=False)
    call_date: Mapped[date] = mapped_column(Date, nullable=False)
    next_followup_date: Mapped[date | None] = mapped_column(Date, nullable=True)
