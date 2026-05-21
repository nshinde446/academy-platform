"""Add substitute teacher tracking to lectures.

Tier 1 of the Plan-vs-Actual reconciliation feature. Records who actually
delivered a lecture when it differs from the scheduled teacher (substitute),
plus a reason and free-text notes. Future tiers will move to a separate
LectureSession table; for now we extend lectures in place.

Revision ID: 0019
Revises: 0018
Create Date: 2026-05-22
"""

from alembic import op
import sqlalchemy as sa

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "lectures",
        sa.Column(
            "actual_teacher_id",
            sa.Uuid(),
            sa.ForeignKey("teachers.id"),
            nullable=True,
        ),
    )
    op.add_column(
        "lectures",
        sa.Column("change_reason", sa.String(40), nullable=True),
    )
    op.add_column(
        "lectures",
        sa.Column("change_notes", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("lectures", "change_notes")
    op.drop_column("lectures", "change_reason")
    op.drop_column("lectures", "actual_teacher_id")
