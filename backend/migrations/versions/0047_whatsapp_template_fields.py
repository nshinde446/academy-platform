"""WhatsApp (Meta Cloud API) template mapping fields on notification_templates.

Meta's Cloud API cannot send free-form text on a business-initiated message; it
requires a *pre-approved named template* plus positional body parameters. A
``WHATSAPP`` NotificationTemplate therefore needs to carry:

* ``provider_template_name`` — the exact template name registered & approved in
  Meta (e.g. "attendance_absent_alert").
* ``provider_language``      — the template's language code (e.g. "en", "en_US",
  "mr" for Marathi).

Both are nullable: EMAIL / SMS / PUSH templates don't use them, and a WHATSAPP
row without a provider template name simply can't be sent (the sender skips it),
so this migration is safe to apply before any template is configured.

Revision ID: 0047
Revises: 0046
Create Date: 2026-08-03
"""

from alembic import op
import sqlalchemy as sa


revision = "0047"
down_revision = "0046"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "notification_templates",
        sa.Column("provider_template_name", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "notification_templates",
        sa.Column("provider_language", sa.String(length=15), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("notification_templates", "provider_language")
    op.drop_column("notification_templates", "provider_template_name")
