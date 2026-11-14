"""weekend_work — Saturday/Sunday pre-approved work (Point 5)

Revision ID: 0073
Revises: 0072
Create Date: 2026-11-14

A new table for the weekend-work flow: pre-approval (date + staff), the teacher's
work content, and the approver's Work Approved Status. Time IN/OUT, day status
and worked hours are read live from staff_daily_attendance, so none are stored
here. Reversible.
"""

from alembic import op
import sqlalchemy as sa

revision = "0073"
down_revision = "0072"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "weekend_work",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(), server_default="active", nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("branch_id", sa.Uuid(), nullable=False),
        sa.Column("staff_id", sa.Uuid(), nullable=False),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column("pre_approved_by", sa.Uuid(), nullable=True),
        sa.Column("work_content", sa.Text(), nullable=True),
        sa.Column("work_content_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approval_status", sa.String(length=20), server_default="PENDING", nullable=False),
        sa.Column("approved_by", sa.Uuid(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approval_note", sa.String(length=255), nullable=True),
        sa.Column("marked_absent", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("credit_days", sa.Numeric(3, 1), server_default="0", nullable=False),
        sa.ForeignKeyConstraint(["branch_id"], ["branch.id"]),
        sa.ForeignKeyConstraint(["staff_id"], ["staff.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_weekend_work_work_date", "weekend_work", ["work_date"])
    op.create_index(
        "ix_weekend_work_branch_date", "weekend_work", ["branch_id", "work_date"]
    )
    op.create_index(
        "ix_weekend_work_approval_status", "weekend_work", ["approval_status"]
    )
    op.create_index(
        "uq_weekend_work_active",
        "weekend_work",
        ["branch_id", "staff_id", "work_date"],
        unique=True,
        postgresql_where=sa.text("is_deleted = false"),
        sqlite_where=sa.text("is_deleted = 0"),
    )


def downgrade() -> None:
    op.drop_index("uq_weekend_work_active", table_name="weekend_work")
    op.drop_index("ix_weekend_work_approval_status", table_name="weekend_work")
    op.drop_index("ix_weekend_work_branch_date", table_name="weekend_work")
    op.drop_index("ix_weekend_work_work_date", table_name="weekend_work")
    op.drop_table("weekend_work")
