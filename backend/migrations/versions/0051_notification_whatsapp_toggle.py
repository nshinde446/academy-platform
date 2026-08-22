"""Per-branch WhatsApp master toggle on notification_settings.

Adds ``whatsapp_enabled`` (bool, default false) — the admin's UI on/off switch for
all WhatsApp sends, separate from the infra ``WHATSAPP_ENABLED`` env (credentials).
Both must be on to send; while off, WHATSAPP queue rows are skipped (left PENDING),
so shipping this cannot send a message or incur a Meta charge until an admin turns
it on. See docs/whatsapp-attendance-notifications.md.

Revision ID: 0051
Revises: 0050
Create Date: 2026-08-22
"""

import uuid

from alembic import op
import sqlalchemy as sa


revision = "0051"
down_revision = "0050"
branch_labels = None
depends_on = None


# Editable default templates (global — branch_id NULL — so every branch inherits
# them; an admin edits the wording in the Settings → Notification templates UI).
# These are starting points; WhatsApp sends still require Meta-approved provider
# templates matching provider_template_name before they go live.
_BRAND = "Matrix Science Academy"
_SEED_TEMPLATES = [
    {
        "name": "Attendance — absent alert",
        "event_type": "STUDENT_ABSENT",
        "body_template": (
            "Dear Parent, {student_name} was marked ABSENT on {attendance_date}. "
            f"Please contact us if unexpected. — {_BRAND}"
        ),
        "provider_template_name": "attendance_absent_alert",
    },
    {
        "name": "Attendance — daily status",
        "event_type": "DAILY_ATTENDANCE_DIGEST",
        "body_template": (
            "Attendance update: {student_name} was {status} on {attendance_date}. "
            f"— {_BRAND}"
        ),
        "provider_template_name": "attendance_daily_status",
    },
    {
        "name": "Lecture reminder — today's schedule",
        "event_type": "LECTURE_REMINDER",
        "body_template": (
            "Good morning! {student_name} has lectures today: {subjects}. "
            f"— {_BRAND}"
        ),
        "provider_template_name": "lecture_reminder",
    },
]


def upgrade() -> None:
    op.add_column(
        "notification_settings",
        sa.Column(
            "whatsapp_enabled",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )

    templates = sa.table(
        "notification_templates",
        sa.column("id", sa.Uuid()),
        sa.column("name", sa.String()),
        sa.column("event_type", sa.String()),
        sa.column("channel", sa.String()),
        sa.column("body_template", sa.Text()),
        sa.column("is_active", sa.Boolean()),
        sa.column("provider_template_name", sa.String()),
        sa.column("provider_language", sa.String()),
        sa.column("status", sa.String()),
        sa.column("is_deleted", sa.Boolean()),
    )
    op.bulk_insert(
        templates,
        [
            {
                "id": uuid.uuid4(),
                "name": t["name"],
                "event_type": t["event_type"],
                "channel": "WHATSAPP",
                "body_template": t["body_template"],
                "is_active": True,
                "provider_template_name": t["provider_template_name"],
                "provider_language": "en",
                "status": "active",
                "is_deleted": False,
            }
            for t in _SEED_TEMPLATES
        ],
    )


def downgrade() -> None:
    names = tuple(t["name"] for t in _SEED_TEMPLATES)
    op.execute(
        sa.text(
            "DELETE FROM notification_templates WHERE name IN :names"
        ).bindparams(sa.bindparam("names", value=names, expanding=True))
    )
    op.drop_column("notification_settings", "whatsapp_enabled")
