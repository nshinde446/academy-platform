"""Add per-branch timezone for day-attendance local bucketing.

All biometric day-attendance logic (sign-in/out day bucketing, the nightly
absent sweep) runs in the branch's local time. Stored per branch so branches
can differ; defaults to Asia/Kolkata.

See docs/biometric-attendance-design.md §2.3.

Revision ID: 0042
Revises: 0041
Create Date: 2026-06-28
"""

from alembic import op
import sqlalchemy as sa


revision = "0042"
down_revision = "0041"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "branch",
        sa.Column(
            "timezone",
            sa.String(length=64),
            nullable=False,
            server_default="Asia/Kolkata",
        ),
    )


def downgrade() -> None:
    op.drop_column("branch", "timezone")
