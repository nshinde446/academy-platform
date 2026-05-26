"""Add fees_status to students + years_experience to teachers.

Phase A of the MSA_Design alignment. The new design surfaces a Fees
column on the students list (paid / due) and a Years column on the
teachers list — both data points the schema didn't have yet.

Both columns are nullable so existing rows continue to render. Admin
backfills via the edit dialogs (or via the seed for demo data).

Revision ID: 0025
Revises: 0024
Create Date: 2026-05-27
"""

from alembic import op
import sqlalchemy as sa

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "students",
        sa.Column("fees_status", sa.String(20), nullable=True),
    )
    op.add_column(
        "teachers",
        sa.Column("years_experience", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("teachers", "years_experience")
    op.drop_column("students", "fees_status")
