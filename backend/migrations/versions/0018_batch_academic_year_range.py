"""Replace batches.academic_year_id with start_academic_year_id + end_academic_year_id.

Backfill sets both edges to the previous academic_year_id (single-year batches).
Multi-year support added going forward.

Revision ID: 0018
Revises: 0017
Create Date: 2026-05-18
"""

from alembic import op
import sqlalchemy as sa

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "batches",
        sa.Column(
            "start_academic_year_id",
            sa.Uuid(),
            sa.ForeignKey("academic_years.id"),
            nullable=True,
        ),
    )
    op.add_column(
        "batches",
        sa.Column(
            "end_academic_year_id",
            sa.Uuid(),
            sa.ForeignKey("academic_years.id"),
            nullable=True,
        ),
    )
    op.execute(
        "UPDATE batches SET start_academic_year_id = academic_year_id, "
        "end_academic_year_id = academic_year_id"
    )
    op.alter_column("batches", "start_academic_year_id", nullable=False)
    op.alter_column("batches", "end_academic_year_id", nullable=False)
    op.drop_column("batches", "academic_year_id")


def downgrade() -> None:
    op.add_column(
        "batches",
        sa.Column(
            "academic_year_id",
            sa.Uuid(),
            sa.ForeignKey("academic_years.id"),
            nullable=True,
        ),
    )
    op.execute("UPDATE batches SET academic_year_id = start_academic_year_id")
    op.alter_column("batches", "academic_year_id", nullable=False)
    op.drop_column("batches", "end_academic_year_id")
    op.drop_column("batches", "start_academic_year_id")
