"""Add gender, district, caste, username to students.

Revision ID: 0016
Revises: 0015
Create Date: 2026-05-18
"""

from alembic import op
import sqlalchemy as sa

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("students", sa.Column("gender", sa.String(10), nullable=True))
    op.add_column("students", sa.Column("district", sa.String(100), nullable=True))
    op.add_column("students", sa.Column("caste", sa.String(100), nullable=True))
    op.add_column("students", sa.Column("username", sa.String(100), nullable=True))


def downgrade() -> None:
    op.drop_column("students", "username")
    op.drop_column("students", "caste")
    op.drop_column("students", "district")
    op.drop_column("students", "gender")
