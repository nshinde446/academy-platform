"""Population day-attendance table (Layer 1).

One row per student per LOCAL day, derived from raw punches. Canonical for the
daily attendance %; per-lecture attendance_records project from this.

See docs/biometric-attendance-design.md.

Revision ID: 0044
Revises: 0043
Create Date: 2026-06-28
"""

from alembic import op
import sqlalchemy as sa


revision = "0044"
down_revision = "0043"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "daily_attendance",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(), server_default="active", nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("student_id", sa.Uuid(), nullable=False),
        sa.Column("branch_id", sa.Uuid(), nullable=False),
        sa.Column("attendance_date", sa.Date(), nullable=False),
        sa.Column("first_in", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_out", sa.DateTime(timezone=True), nullable=True),
        sa.Column("day_status", sa.String(length=20), nullable=False),
        sa.Column("signoff", sa.String(length=20), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("override_by", sa.Uuid(), nullable=True),
        sa.Column("override_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"]),
        sa.ForeignKeyConstraint(["branch_id"], ["branch.id"]),
        sa.ForeignKeyConstraint(["override_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("student_id", "attendance_date", name="uq_daily_attendance_student_date"),
    )
    op.create_index(
        "ix_daily_attendance_attendance_date", "daily_attendance", ["attendance_date"]
    )
    op.create_index(
        "ix_daily_attendance_branch_date", "daily_attendance", ["branch_id", "attendance_date"]
    )


def downgrade() -> None:
    op.drop_index("ix_daily_attendance_branch_date", table_name="daily_attendance")
    op.drop_index("ix_daily_attendance_attendance_date", table_name="daily_attendance")
    op.drop_table("daily_attendance")
