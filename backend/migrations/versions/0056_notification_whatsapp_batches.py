"""per-batch WhatsApp notification enablement (pilot control)

Revision ID: 0056
Revises: 0055
Create Date: 2026-09-12

Adds ``notification_whatsapp_batches`` — one row per batch with WhatsApp parent
notifications switched ON. Presence (is_deleted = false) = enabled. This is the
per-batch selection under the branch master switch: a parent message is only
produced when the master switch is on AND the student's batch has a live row here.
Empty set for a branch => notify nobody (explicit opt-in per batch), so no branch
can accidentally message every parent. Gates absent alerts, daily digest, and
lecture reminders alike. See docs/whatsapp-attendance-notifications.md.
"""

from alembic import op
import sqlalchemy as sa

revision = "0056"
down_revision = "0055"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notification_whatsapp_batches",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(), server_default="active", nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("branch_id", sa.Uuid(), nullable=False),
        sa.Column("batch_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["branch_id"], ["branch.id"]),
        sa.ForeignKeyConstraint(["batch_id"], ["batches.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    # At most one live enablement row per (branch, batch); soft-deleted rows don't
    # count so toggling off then on again is clean.
    op.create_index(
        "uq_notif_wa_batch_live",
        "notification_whatsapp_batches",
        ["branch_id", "batch_id"],
        unique=True,
        postgresql_where=sa.text("is_deleted = false"),
        sqlite_where=sa.text("is_deleted = 0"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_notif_wa_batch_live", table_name="notification_whatsapp_batches"
    )
    op.drop_table("notification_whatsapp_batches")
