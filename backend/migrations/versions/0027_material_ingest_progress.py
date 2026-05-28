"""Add ingest progress counters to materials.

So the UI can show a "page X of N" progress bar while a material's PDF
is being extracted (the ingest BackgroundTask updates these per page).

Both nullable — null means "no ingest has run / not applicable".

Revision ID: 0027
Revises: 0026
Create Date: 2026-05-29
"""

from alembic import op
import sqlalchemy as sa


revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "materials",
        sa.Column("ingest_pages_total", sa.Integer(), nullable=True),
    )
    op.add_column(
        "materials",
        sa.Column("ingest_pages_done", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("materials", "ingest_pages_done")
    op.drop_column("materials", "ingest_pages_total")
