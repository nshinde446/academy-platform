import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.base import BaseModel


class NotificationTemplate(BaseModel):
    __tablename__ = "notification_templates"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    body_template: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    condition_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    # WhatsApp (Meta Cloud API) only: the pre-approved Meta template name and its
    # language code. NULL for EMAIL/SMS/PUSH, which send body_template directly.
    provider_template_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    provider_language: Mapped[str | None] = mapped_column(String(15), nullable=True)
    branch_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("branch.id"), nullable=True
    )


class NotificationQueue(BaseModel):
    __tablename__ = "notification_queue"

    template_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("notification_templates.id"), nullable=False
    )
    recipient: Mapped[str] = mapped_column(String(255), nullable=False)
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    # The student this message is about, denormalised from the event so the
    # delivery log can be filtered by batch (queue -> student_id -> batch
    # memberships). NULL for channel rows with no student (or older rows the
    # backfill couldn't parse). Indexed for the batch-filter join.
    student_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, index=True, nullable=True
    )
    delivery_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="PENDING"
    )
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    scheduled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    # "manual" (a coordinator sent it) or "auto" (cutoff-time job) — for the
    # WhatsApp delivery log. NULL for older rows.
    sent_by: Mapped[str | None] = mapped_column(String(20), nullable=True)
    branch_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("branch.id"), nullable=True
    )


class NotificationSettings(BaseModel):
    __tablename__ = "notification_settings"

    branch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("branch.id"), nullable=False, unique=True
    )
    # Master opt-in for the daily WhatsApp attendance digest. Default off — a
    # branch never messages parents until it deliberately turns this on.
    daily_digest_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    # "ALL" (every parent gets their child's status) or "ABSENT_ONLY" (only
    # absent students' parents). Default ABSENT_ONLY — cheaper, higher signal.
    daily_digest_scope: Mapped[str] = mapped_column(
        String(20), nullable=False, default="ABSENT_ONLY"
    )
    # Per-branch master switch for all WhatsApp sends — the admin's UI on/off,
    # separate from the infra WHATSAPP_ENABLED env (credentials). BOTH must be on
    # to actually send; while this is off, WHATSAPP queue rows are skipped (left
    # PENDING) so nothing goes out and no Meta charge is incurred.
    whatsapp_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )


class NotificationWhatsappBatch(BaseModel):
    """One row per batch that has WhatsApp parent notifications switched ON.

    Presence (with ``is_deleted = false``) = enabled. This is the per-batch
    selection under the branch master switch (``NotificationSettings.whatsapp_enabled``):
    a parent message is only produced when the master switch is on AND the
    student's batch has a live row here. An empty set for a branch means *notify
    nobody* — enablement is explicit opt-in per batch, so a branch can never
    accidentally message every parent. Gates all three parent-message producers
    (absent alert, daily digest, lecture reminder). See
    docs/whatsapp-attendance-notifications.md.
    """

    __tablename__ = "notification_whatsapp_batches"
    __table_args__ = (
        # At most one live enablement row per (branch, batch); soft-deleted rows
        # don't count, so toggling off then on again is clean.
        Index(
            "uq_notif_wa_batch_live",
            "branch_id",
            "batch_id",
            unique=True,
            postgresql_where=text("is_deleted = false"),
            sqlite_where=text("is_deleted = 0"),
        ),
    )

    branch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("branch.id"), nullable=False
    )
    batch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("batches.id"), nullable=False
    )


class NotificationEvent(BaseModel):
    __tablename__ = "notification_events"

    event_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    template_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("notification_templates.id"), nullable=False
    )
    queue_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("notification_queue.id"), nullable=False
    )
    triggered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
