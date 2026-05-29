"""Add paper_type to tests.

Lets the composer distinguish DPP / CPP / TEST blueprints built on the
existing tests table (M4). Defaults to 'TEST' so legacy rows stay valid.

Revision ID: 0028
Revises: 0027
Create Date: 2026-05-29
"""

from alembic import op
import sqlalchemy as sa


revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tests",
        sa.Column(
            "paper_type",
            sa.String(length=10),
            nullable=False,
            server_default="TEST",
        ),
    )


def downgrade() -> None:
    op.drop_column("tests", "paper_type")
