"""Access-control scoping records for the RBAC roles (Floor Coordinator + Accounts).

These are ADDITIVE scoping tables — enforcement (filtering reads/writes by them)
lands in a later increment. They just record intent set by a Manager:

- ``BatchCoordinator``       — which batches a Floor Coordinator may act on.
- ``AccountsAttendanceGrant`` — attendance visibility a Manager grants the
  Accounts role (whose default scope is fees-only), optionally time-limited.
"""

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, UniqueConstraint, Uuid
from sqlalchemy import DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.base import BaseModel


class BatchCoordinator(BaseModel):
    """One (Floor Coordinator user → batch) assignment, set by a Manager.

    A coordinator can hold several rows (a batch list, floor-agnostic). The
    unique constraint keeps a single live row per (user, batch)."""

    __tablename__ = "batch_coordinators"
    __table_args__ = (
        UniqueConstraint("user_id", "batch_id", name="uq_batch_coordinator"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=False
    )
    batch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("batches.id"), nullable=False
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("branch.id"), nullable=False
    )


class AccountsAttendanceGrant(BaseModel):
    """Attendance visibility a Manager grants an Accounts user.

    Scope is a single batch (``batch_id`` set) or the whole branch
    (``batch_id`` NULL). ``expires_at`` NULL = permanent; otherwise the grant
    lapses at that time (enforcement checks it later)."""

    __tablename__ = "accounts_attendance_grants"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=False
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("branch.id"), nullable=False
    )
    # NULL = branch-wide grant; set = a single batch.
    batch_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("batches.id"), nullable=True
    )
    # NULL = permanent; otherwise auto-expires at this instant.
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    granted_by: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=False
    )
