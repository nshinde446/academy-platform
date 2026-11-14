"""student_cancel_admission — keep a cancelled student's record

Revision ID: 0072
Revises: 0071
Create Date: 2026-11-14

Client change request (Point 4): cancelling an admission must preserve the
record. A cancelled admission is a soft-delete (is_deleted=True) *marked* with
status='cancelled' so it drops out of every active list yet stays recoverable
and listable in the Cancelled Students tab. These two columns carry the when and
the optional why; child rows (marks, fees, rank lists) are untouched.

Additive and reversible.
"""

from alembic import op
import sqlalchemy as sa

revision = "0072"
down_revision = "0071"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "students",
        sa.Column("cancelled_at", sa.Date(), nullable=True),
    )
    op.add_column(
        "students",
        sa.Column("cancellation_reason", sa.String(length=500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("students", "cancellation_reason")
    op.drop_column("students", "cancelled_at")
