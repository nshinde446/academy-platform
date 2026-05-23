"""Add no_show_reason column to lectures.

Tier 4 of the Plan-vs-Actual feature. Distinguishes 'no_show'
(scheduled teacher / batch didn't show up) from 'cancelled' (admin
intentionally cancelled). The new lecture_status value 'no_show' is
validated at the application layer; no DB constraint change.

Revision ID: 0021
Revises: 0020
Create Date: 2026-05-23
"""

from alembic import op
import sqlalchemy as sa

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "lectures",
        sa.Column("no_show_reason", sa.String(40), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("lectures", "no_show_reason")
