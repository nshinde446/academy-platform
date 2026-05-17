"""Create analytics summary tables.

Revision ID: 0010
Revises: 0009
Create Date: 2026-05-17
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _base_columns():
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="active"),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
    ]


def upgrade() -> None:
    op.create_table(
        "analytics_student_summary",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("student_id", sa.Uuid(), sa.ForeignKey("students.id"), nullable=False),
        sa.Column("branch_id", sa.Uuid(), sa.ForeignKey("branch.id"), nullable=False),
        sa.Column("academic_year_id", sa.Uuid(), sa.ForeignKey("academic_years.id"), nullable=False),
        sa.Column("total_attendance", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("present_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("absent_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("late_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("attendance_percentage", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("total_tests", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("average_score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("weak_topics", sa.Text(), nullable=True),
        sa.Column("risk_score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("last_updated", sa.DateTime(timezone=True), nullable=False),
        *_base_columns(),
    )

    op.create_table(
        "analytics_teacher_summary",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("teacher_id", sa.Uuid(), sa.ForeignKey("teachers.id"), nullable=False),
        sa.Column("branch_id", sa.Uuid(), sa.ForeignKey("branch.id"), nullable=False),
        sa.Column("academic_year_id", sa.Uuid(), sa.ForeignKey("academic_years.id"), nullable=False),
        sa.Column("total_lectures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completed_lectures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completion_rate", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("avg_delay_minutes", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("avg_student_attendance", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("last_updated", sa.DateTime(timezone=True), nullable=False),
        *_base_columns(),
    )

    op.create_table(
        "analytics_batch_summary",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("batch_id", sa.Uuid(), sa.ForeignKey("batches.id"), nullable=False),
        sa.Column("branch_id", sa.Uuid(), sa.ForeignKey("branch.id"), nullable=False),
        sa.Column("academic_year_id", sa.Uuid(), sa.ForeignKey("academic_years.id"), nullable=False),
        sa.Column("total_students", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("avg_attendance", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("avg_score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("weak_subjects", sa.Text(), nullable=True),
        sa.Column("top_performers", sa.Text(), nullable=True),
        sa.Column("last_updated", sa.DateTime(timezone=True), nullable=False),
        *_base_columns(),
    )


def downgrade() -> None:
    op.drop_table("analytics_batch_summary")
    op.drop_table("analytics_teacher_summary")
    op.drop_table("analytics_student_summary")
