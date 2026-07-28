"""BioMax device provisioning — outbound command queue + user mirror.

Server → device provisioning (push a student's identity to the terminal so
staff never hand-type a name + roll number for thousands of students). BioMax's
own SmartOffice does this by queuing commands the device fetches *in the reply to
its own AIData push* — the ``cmd_code`` channel. We replicate that queue here.

Two tables, both branch-isolated (``docs/db_conventions.md``):

* ``device_commands`` — the outbound queue. The emission layer (a later,
  capture-gated increment) reads the oldest ``pending`` command for a device and
  returns its ``cmd_code`` + payload in the AIData response. **Nothing in this
  module touches the device yet** — it is plumbing behind
  ``BIOMAX_PROVISIONING_ENABLED``.
* ``device_users`` — a biometrics-free mirror of the device's user table, so we
  can reconcile "who is on the device vs the platform". Never stores a face /
  photo / template — identity fields only.

The captured command vocabulary and the ``SET_USER_INFO`` payload contract live
in ``docs/biomax-provisioning-implementation.md`` §0.6.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.base import BaseModel

# ── Command vocabulary (captured from SmartOffice's DeviceCommands queue) ──────
# Only SET_USER_INFO is ever emitted by this feature. The others are documented
# for completeness / future use; a delete command has NOT been captured yet and
# must be (§0.6) before any delete path is built.
CMD_SET_USER_INFO = "SET_USER_INFO"

# ── Command queue statuses ────────────────────────────────────────────────────
# Plain strings (matching day_status / attendance_status elsewhere), NOT a PG
# enum — keeps SQLite tests and PG in lockstep without an enum migration.
STATUS_PENDING = "pending"
STATUS_SENT = "sent"
STATUS_CONFIRMED = "confirmed"
STATUS_FAILED = "failed"
STATUS_CANCELLED = "cancelled"

# A command is "in flight" (occupying the device's attention) while pending or
# sent — the window in which a duplicate enqueue must be suppressed.
INFLIGHT_STATUSES = (STATUS_PENDING, STATUS_SENT)

# Validity window we stamp on every pushed user: wide enough that a user never
# silently expires on the device. YYYYMMDD (note the vendor's typo'd keys
# ``vaildStart`` / ``vaildEnd`` — see build_payload).
DEFAULT_VALID_START = "20200101"
DEFAULT_VALID_END = "20401231"

# A JSON column that is real JSONB on Postgres (prod/CI) and portable JSON on
# SQLite (fast unit tests).
_JSON = JSON().with_variant(JSONB(), "postgresql")


class DeviceCommand(BaseModel):
    """One queued server→device command (e.g. register a user).

    ``command_status`` is deliberately separate from ``BaseModel.status`` (the
    generic active/soft-status): this tracks the delivery lifecycle
    pending → sent → confirmed / failed / cancelled.
    """

    __tablename__ = "device_commands"
    __table_args__ = (
        # Fast dequeue of the next command for a device.
        Index(
            "ix_device_commands_pending",
            "dev_id",
            "command_status",
            postgresql_where=text("command_status = 'pending'"),
            sqlite_where=text("command_status = 'pending'"),
        ),
        # A re-run of a bulk push must not double-enqueue the same user while a
        # command for it is still in flight. Partial-unique on the idempotency
        # key over (pending, sent) only — a confirmed/failed row does not block a
        # fresh push later.
        Index(
            "uq_device_commands_idempotency",
            "idempotency_key",
            unique=True,
            postgresql_where=text("command_status IN ('pending', 'sent')"),
            sqlite_where=text("command_status IN ('pending', 'sent')"),
        ),
    )

    branch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("branch.id"), nullable=False
    )
    # Target terminal — the same Cloud ID the ingest allowlist uses.
    dev_id: Mapped[str] = mapped_column(String(100), nullable=False)
    # The captured cmd_code (currently always SET_USER_INFO).
    command: Mapped[str] = mapped_column(String(40), nullable=False)
    # The device userId this command targets (== Student.rfid_number); null for
    # commands that are not user-scoped. Denormalised out of the payload so
    # dedupe/reconcile queries don't need JSON extraction (differs per dialect).
    vendor_user_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Wire-ready payload, e.g. {"users": [{"userId": ..., "name": ...}]}. Never
    # contains a biometric blob — build_payload enforces this by construction.
    payload: Mapped[dict] = mapped_column(_JSON, nullable=False)
    # Provenance; null for non-student ops.
    student_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("students.id"), nullable=True
    )
    command_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=STATUS_PENDING
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Assigned when emitted, echoed back by the device to confirm the command.
    trans_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    # (dev_id, command, vendor_user_id) — the idempotency handle.
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)


class DeviceUser(BaseModel):
    """Biometrics-free mirror of one user on the device.

    Populated from the device's own ``realtime_enroll_data`` sync in a later
    increment; used to reconcile platform vs device. **Never** carries a face /
    photo / template — ``has_face`` is a boolean flag only.
    """

    __tablename__ = "device_users"
    __table_args__ = (
        UniqueConstraint(
            "dev_id", "vendor_user_id", name="uq_device_users_dev_user"
        ),
    )

    branch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("branch.id"), nullable=False
    )
    dev_id: Mapped[str] = mapped_column(String(100), nullable=False)
    # == Student.rfid_number.
    vendor_user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    privilege: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    valid_start: Mapped[str | None] = mapped_column(String(8), nullable=True)
    valid_end: Mapped[str | None] = mapped_column(String(8), nullable=True)
    # Flag only — True if the device's sync carried a face template. NEVER the blob.
    has_face: Mapped[bool] = mapped_column(default=False, nullable=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
