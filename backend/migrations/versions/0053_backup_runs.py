"""backup_runs — record of each DB backup run for the dev monitoring dashboard.

Written by the on-box backup script; read by GET /dev/monitoring to show backup
freshness + off-box status. Global (not per-branch).

Revision ID: 0053
Revises: 0052
Create Date: 2026-08-30
"""

from alembic import op
import sqlalchemy as sa


revision = "0053"
down_revision = "0052"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "backup_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("offbox", sa.String(length=20), server_default="skipped", nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_backup_runs_created", "backup_runs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_backup_runs_created", table_name="backup_runs")
    op.drop_table("backup_runs")
