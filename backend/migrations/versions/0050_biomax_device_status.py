"""BioMax device status — latest self-reported counts per device.

One row per device holding the status block it sends on every ``receive_cmd``
poll (userCount / faceCount / fpCount / …, firmware, time) plus a last-seen
timestamp, so the UI can show a live on-device count and a heartbeat without
touching the terminal. Counts only — no biometric data. This only creates the
table.

Revision ID: 0050
Revises: 0049
Create Date: 2026-08-11
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0050"
down_revision = "0049"
branch_labels = None
depends_on = None


def _base_columns() -> list:
    return [
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(), server_default="active", nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default="false", nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "device_status",
        *_base_columns(),
        sa.Column("branch_id", sa.Uuid(), nullable=False),
        sa.Column("dev_id", sa.String(length=100), nullable=False),
        sa.Column("snapshot", postgresql.JSONB().with_variant(sa.JSON(), "sqlite"), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["branch_id"], ["branch.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dev_id", name="uq_device_status_dev"),
    )


def downgrade() -> None:
    op.drop_table("device_status")
