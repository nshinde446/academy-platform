"""Create Lecture, LectureTopicMapping, LectureAttendanceMapping tables.

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-17
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
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
        "lectures",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("teacher_id", sa.Uuid(), sa.ForeignKey("teachers.id"), nullable=False),
        sa.Column("batch_id", sa.Uuid(), sa.ForeignKey("batches.id"), nullable=False),
        sa.Column("classroom_id", sa.Uuid(), sa.ForeignKey("classrooms.id"), nullable=True),
        sa.Column("subject_id", sa.Uuid(), sa.ForeignKey("subjects.id"), nullable=False),
        sa.Column("topic_id", sa.Uuid(), sa.ForeignKey("topics.id"), nullable=True),
        sa.Column("scheduled_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("scheduled_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actual_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actual_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivery_mode", sa.String(20), nullable=False, server_default="offline"),
        sa.Column("lecture_status", sa.String(20), nullable=False, server_default="scheduled"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("branch_id", sa.Uuid(), sa.ForeignKey("branch.id"), nullable=False),
        sa.Column("academic_year_id", sa.Uuid(), sa.ForeignKey("academic_years.id"), nullable=False),
        *_base_columns(),
    )

    op.create_table(
        "lecture_topic_mappings",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("lecture_id", sa.Uuid(), sa.ForeignKey("lectures.id"), nullable=False),
        sa.Column("topic_id", sa.Uuid(), sa.ForeignKey("topics.id"), nullable=False),
        sa.Column("order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("branch_id", sa.Uuid(), sa.ForeignKey("branch.id"), nullable=False),
        *_base_columns(),
    )

    op.create_table(
        "lecture_attendance_mappings",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("lecture_id", sa.Uuid(), sa.ForeignKey("lectures.id"), nullable=False),
        sa.Column("student_id", sa.Uuid(), sa.ForeignKey("students.id"), nullable=False),
        sa.Column("attendance_status", sa.String(20), nullable=False, server_default="PRESENT"),
        sa.Column("marked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("branch_id", sa.Uuid(), sa.ForeignKey("branch.id"), nullable=False),
        *_base_columns(),
    )


def downgrade() -> None:
    op.drop_table("lecture_attendance_mappings")
    op.drop_table("lecture_topic_mappings")
    op.drop_table("lectures")
