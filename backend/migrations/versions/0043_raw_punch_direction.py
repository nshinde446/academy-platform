"""Persist device-reported punch direction on raw_punch_logs.

PunchEvent.direction was parsed but dropped on write. Store it (nullable) so the
day aggregator can use IN/OUT when the device reports it, and infer otherwise.

Revision ID: 0043
Revises: 0042
Create Date: 2026-06-28
"""

from alembic import op
import sqlalchemy as sa


revision = "0043"
down_revision = "0042"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "raw_punch_logs",
        sa.Column("direction", sa.String(length=10), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("raw_punch_logs", "direction")
