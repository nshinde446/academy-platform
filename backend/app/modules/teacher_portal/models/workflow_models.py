"""Weekend Plan & Teacher Star-System workflow entities (SRD §8).

Star System (daily self-assessment), the per-teacher approver mapping, the
permanent approver decision log shared by both record types, and the lean in-app
notification inbox. The Weekend Plan itself reuses the reconciled
``weekend_work`` table (see ``teacher.models.teacher_models``); only its
structured work-breakdown lines live separately (``WeekendPlanItem`` there).

Conventions: every table carries ``branch_id`` (branch isolation is a
data-correctness rule) and soft-delete via ``BaseModel.is_deleted``.
See docs/weekend-and-star-system-roadmap.md.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.base import BaseModel

# ── Star System lifecycle (mirrors the Weekend Plan one) ─────────────────────
SELF_ASSESSMENT_STATUSES = frozenset(
    {"DRAFT", "PENDING", "APPROVED", "REJECTED", "ABSENT"}
)

# Assessment item input controls (SRD 5.2.1 "Proposed option sets").
#   COUNT   — a count dropdown, e.g. 0,1,2,...,8+
#   STATUS  — Not Applicable | Not Done | Partially Done | Done
#   DEDUCTION — a No/Yes chip, or a 0..5 count for Late Entry / Off Lecture / Half Day
ASSESSMENT_INPUT_TYPES = frozenset({"COUNT", "STATUS", "DEDUCTION"})

# Record types used by the shared ApproverLog and in-app notifications.
RECORD_TYPES = frozenset({"WEEKEND_PLAN", "SELF_ASSESSMENT"})

# Approver / workflow actions written to the permanent log.
APPROVER_ACTIONS = frozenset(
    {"SUBMIT", "WITHDRAW", "RESUBMIT", "APPROVE", "REJECT", "MARK_ABSENT"}
)


class ApproverMapping(BaseModel):
    """Which Senior/Admin approves a given teacher (SRD ApproverMapping).

    ``approver_user_id`` is a ``User`` (an approver account). ``is_default`` marks
    the primary approver; Admins act as fallback for any teacher (resolved in the
    service, open-question 1 default)."""

    __tablename__ = "approver_mappings"
    __table_args__ = (
        Index(
            "uq_approver_mapping_active",
            "branch_id",
            "staff_id",
            "approver_user_id",
            unique=True,
            postgresql_where=text("is_deleted = false"),
            sqlite_where=text("is_deleted = 0"),
        ),
    )

    branch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("branch.id"), nullable=False
    )
    staff_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("staff.id"), nullable=False, index=True
    )
    approver_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=False
    )
    is_default: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true", default=True
    )


class ApproverLog(BaseModel):
    """Permanent record of every workflow decision (SRD ApproverLog, BR-06).

    Shared by Weekend Plans and Self-Assessments via ``record_type`` +
    ``record_id``. Never deleted; the teacher's History tab reads it. ``comment``
    is mandatory for decision actions (BR-01), enforced in the service."""

    __tablename__ = "approver_logs"
    __table_args__ = (
        Index("ix_approver_logs_record", "record_type", "record_id"),
        Index("ix_approver_logs_branch", "branch_id", "created_at"),
    )

    branch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("branch.id"), nullable=False
    )
    record_type: Mapped[str] = mapped_column(String(20), nullable=False)
    record_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    approver_user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)


class PortalNotification(BaseModel):
    """Lean in-app notification to a teacher or approver (SRD Notification).

    In-app only for v1 (open-question 8). Points at the originating record so the
    client can deep-link to it."""

    __tablename__ = "portal_notifications"
    __table_args__ = (
        Index("ix_portal_notifications_user", "user_id", "is_read", "created_at"),
    )

    branch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("branch.id"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=False
    )
    record_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    record_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    is_read: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false", default=False
    )


# ── Star System (daily self-assessment) ──────────────────────────────────────


class AssessmentCategory(BaseModel):
    """One of the Star-System categories (SRD 5.2.1). Four are star-rated; the
    Discipline Deductions category has ``is_deduction = true`` and is not rated.
    Admin-configurable; seeded with the five SRD categories."""

    __tablename__ = "assessment_categories"
    __table_args__ = (
        Index("ix_assessment_categories_branch", "branch_id", "sort_order"),
    )

    branch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("branch.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0", default=0
    )
    is_deduction: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false", default=False
    )
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true", default=True
    )


class AssessmentItemMaster(BaseModel):
    """An item inside a category with its dropdown options (SRD AssessmentItemMaster).

    ``options`` is the ordered list of allowed selected values (JSON array). The
    only free-text field in the whole form is Miscellaneous, which is stored on
    the assessment itself, not as an item."""

    __tablename__ = "assessment_item_master"
    __table_args__ = (
        Index("ix_assessment_item_master_cat", "category_id", "sort_order"),
    )

    branch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("branch.id"), nullable=False
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("assessment_categories.id"), nullable=False
    )
    item_name: Mapped[str] = mapped_column(String(80), nullable=False)
    input_type: Mapped[str] = mapped_column(String(20), nullable=False)
    options: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0", default=0
    )
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true", default=True
    )


class SelfAssessment(BaseModel):
    """One daily Star-System form per teacher per date (SRD SelfAssessment, SA-06).

    ``final_total_star`` is the sum of the four category stars (max 20),
    recomputed on save. Lifecycle mirrors the Weekend Plan:
    DRAFT -> PENDING -> APPROVED | REJECTED | ABSENT."""

    __tablename__ = "self_assessments"
    __table_args__ = (
        # One live assessment per teacher per date.
        Index(
            "uq_self_assessment_active",
            "branch_id",
            "staff_id",
            "assess_date",
            unique=True,
            postgresql_where=text("is_deleted = false"),
            sqlite_where=text("is_deleted = 0"),
        ),
        Index("ix_self_assessments_status", "branch_id", "status_code"),
    )

    branch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("branch.id"), nullable=False
    )
    staff_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("staff.id"), nullable=False, index=True
    )
    assess_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    miscellaneous_text: Mapped[str | None] = mapped_column(String(300), nullable=True)
    final_total_star: Mapped[float] = mapped_column(
        Numeric(4, 1), nullable=False, server_default="0", default=0
    )
    # Named status_code (not BaseModel.status) exactly as WeekendWork.approval_status.
    status_code: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="DRAFT", default="DRAFT"
    )
    approver_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    latest_approver_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class SelfAssessmentItem(BaseModel):
    """The option selected for one assessment item (SRD SelfAssessmentItem)."""

    __tablename__ = "self_assessment_items"
    __table_args__ = (
        Index("ix_self_assessment_items_assess", "self_assessment_id"),
    )

    branch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("branch.id"), nullable=False
    )
    self_assessment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("self_assessments.id"), nullable=False
    )
    item_master_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("assessment_item_master.id"), nullable=False
    )
    selected_value: Mapped[str] = mapped_column(String(40), nullable=False)


class SelfAssessmentStar(BaseModel):
    """Star rating (1–5) for one of the four main categories (SRD SelfAssessmentStar)."""

    __tablename__ = "self_assessment_stars"
    __table_args__ = (
        Index("ix_self_assessment_stars_assess", "self_assessment_id"),
    )

    branch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("branch.id"), nullable=False
    )
    self_assessment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("self_assessments.id"), nullable=False
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("assessment_categories.id"), nullable=False
    )
    stars: Mapped[int] = mapped_column(Integer, nullable=False)
