"""Add parent_mobile and rfid_number to students.

Revision ID: 0015
Revises: 0014
Create Date: 2026-05-18
"""

from alembic import op
import sqlalchemy as sa

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "students",
        sa.Column("parent_mobile", sa.String(20), nullable=True),
    )
    op.add_column(
        "students",
        sa.Column("rfid_number", sa.String(50), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("students", "rfid_number")
    op.drop_column("students", "parent_mobile")
