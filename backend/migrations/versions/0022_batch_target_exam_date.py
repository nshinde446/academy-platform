"""Add target_exam_date to batches.

Tier 7 — time-weighted syllabus pace. A batch's exam date is the
denominator for the "should be at X% by today" calculation. When not
set, the service falls back to the heuristic of mid-May of the end
academic year (Indian coaching default).

Revision ID: 0022
Revises: 0021
Create Date: 2026-05-24
"""

from alembic import op
import sqlalchemy as sa

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "batches",
        sa.Column("target_exam_date", sa.Date(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("batches", "target_exam_date")
