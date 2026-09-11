"""per-batch class start/end time (Present/Late cutoff)

Revision ID: 0055
Revises: 0054
Create Date: 2026-09-11

Adds class_start_time / class_end_time ("HH:MM") to batches so the PRESENT vs
LATE cutoff is per batch (afternoon batches were judged against the morning
default). Nullable — null falls back to the global ATTENDANCE_CLASS_START.
"""

from alembic import op
import sqlalchemy as sa

revision = "0055"
down_revision = "0054"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("batches", sa.Column("class_start_time", sa.String(length=5), nullable=True))
    op.add_column("batches", sa.Column("class_end_time", sa.String(length=5), nullable=True))


def downgrade() -> None:
    op.drop_column("batches", "class_end_time")
    op.drop_column("batches", "class_start_time")
