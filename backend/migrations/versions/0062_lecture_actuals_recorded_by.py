"""lectures.actuals_recorded_by / actuals_recorded_at

Revision ID: 0062
Revises: 0061
Create Date: 2026-09-29

Adds "who recorded the end-of-day actuals, and when" to ``lectures``. Distinct
from the generic ``updated_by`` / ``updated_at`` (overwritten by any later edit
to the row), these are written only by the actuals-recording paths — the
end-of-day backfill (``PATCH /lectures/{id}/actuals``) and the live Complete —
so the Lecture Report's "Attendance Updated By" / "Timestamp" columns name the
person who signed off the lecture and the moment they did.

Both nullable: historical lectures (recorded before this column existed) stay
NULL, and the Lecture Report falls back to ``updated_by`` / ``updated_at`` for
those rows.
"""

from alembic import op
import sqlalchemy as sa

revision = "0062"
down_revision = "0061"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "lectures",
        sa.Column("actuals_recorded_by", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "lectures",
        sa.Column("actuals_recorded_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("lectures", "actuals_recorded_at")
    op.drop_column("lectures", "actuals_recorded_by")
