"""Late-start flag + actual duration on lectures.

The Schedule module's end-of-day actuals flow (PDF §3) needs two derived,
queryable fields so the teacher-productivity report aggregates without
recomputing the formula per row:

  - late_flag           BOOLEAN  — actual_start > scheduled_start + 10 min
  - actual_duration_min INTEGER  — actual_end - actual_start, in minutes

Both nullable (only set once actuals exist). Pure additive change.

Revision ID: 0037
Revises: 0036
Create Date: 2026-06-25
"""

from alembic import op
import sqlalchemy as sa


revision = "0037"
down_revision = "0036"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "lectures",
        sa.Column("late_flag", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "lectures",
        sa.Column("actual_duration_min", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("lectures", "actual_duration_min")
    op.drop_column("lectures", "late_flag")
