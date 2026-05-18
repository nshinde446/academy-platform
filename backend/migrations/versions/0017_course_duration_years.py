"""Add duration_years to courses; drop academic_year_id.

Revision ID: 0017
Revises: 0016
Create Date: 2026-05-18
"""

from alembic import op
import sqlalchemy as sa

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "courses",
        sa.Column("duration_years", sa.Integer(), nullable=True),
    )
    op.execute("UPDATE courses SET duration_years = 1 WHERE duration_years IS NULL")
    op.alter_column("courses", "duration_years", nullable=False)
    op.drop_column("courses", "academic_year_id")


def downgrade() -> None:
    op.add_column(
        "courses",
        sa.Column(
            "academic_year_id",
            sa.Uuid(),
            sa.ForeignKey("academic_years.id"),
            nullable=True,
        ),
    )
    op.drop_column("courses", "duration_years")
