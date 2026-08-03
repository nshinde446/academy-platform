"""Per-branch notification settings — the daily WhatsApp digest toggle.

One row per branch holds the operator's choice for the daily attendance digest:

* ``daily_digest_enabled`` — master on/off (opt-in; default off, so nothing is
  ever sent to parents until a branch explicitly turns it on).
* ``daily_digest_scope``   — ``ALL`` (message every parent their child's status)
  or ``ABSENT_ONLY`` (only absent students' parents). Default ``ABSENT_ONLY``,
  the cheaper, higher-signal option.

Branch-isolated and unique on ``branch_id`` so the settings service can upsert.

Revision ID: 0048
Revises: 0047
Create Date: 2026-08-03
"""

from alembic import op
import sqlalchemy as sa


revision = "0048"
down_revision = "0047"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notification_settings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(), server_default="active", nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("branch_id", sa.Uuid(), nullable=False),
        sa.Column("daily_digest_enabled", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("daily_digest_scope", sa.String(length=20), nullable=False, server_default="ABSENT_ONLY"),
        sa.ForeignKeyConstraint(["branch_id"], ["branch.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("branch_id", name="uq_notification_settings_branch"),
    )


def downgrade() -> None:
    op.drop_table("notification_settings")
