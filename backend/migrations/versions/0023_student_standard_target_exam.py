"""Add standard and target_exam to students.

Data-quality fix before Tier 11. Without these, /students/[id] analytics
and any per-cohort segmentation (Class 11 NEET vs Class 12 NEET vs JEE
Droppers) can't be expressed properly.

Both columns are nullable in the database so existing rows don't break,
but the create-time API validation enforces them for new enrolments.

Revision ID: 0023
Revises: 0022
Create Date: 2026-05-24
"""

from alembic import op
import sqlalchemy as sa

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "students",
        sa.Column("standard", sa.String(20), nullable=True),
    )
    op.add_column(
        "students",
        sa.Column("target_exam", sa.String(40), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("students", "target_exam")
    op.drop_column("students", "standard")
