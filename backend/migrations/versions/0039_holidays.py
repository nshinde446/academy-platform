"""Holiday calendar (non-teaching days).

A branch-scoped list of dates the timetable generator and copy-to-next-day
must skip so a bulk plan never schedules classes on a holiday (S4).

Revision ID: 0039
Revises: 0038
Create Date: 2026-06-26
"""

from alembic import op
import sqlalchemy as sa


revision = "0039"
down_revision = "0038"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "holidays",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("branch_id", sa.Uuid(), nullable=False),
        sa.Column("holiday_date", sa.Date(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="active"),
        sa.Column(
            "is_deleted", sa.Boolean(), nullable=False, server_default="false"
        ),
        sa.ForeignKeyConstraint(["branch_id"], ["branch.id"]),
    )
    op.create_index(
        "ix_holidays_holiday_date", "holidays", ["holiday_date"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_holidays_holiday_date", table_name="holidays")
    op.drop_table("holidays")
