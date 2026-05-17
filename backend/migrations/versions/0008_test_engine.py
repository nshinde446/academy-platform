"""Create questions, question_topics, question_metadata, tests, test_questions, student_marks tables.

Revision ID: 0008
Revises: 0007
Create Date: 2026-05-17
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: Union[str, None] = "0007"
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
        "questions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("options", sa.Text(), nullable=True),
        sa.Column("correct_answer", sa.Text(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("subject_id", sa.Uuid(), sa.ForeignKey("subjects.id"), nullable=False),
        sa.Column("topic_id", sa.Uuid(), sa.ForeignKey("topics.id"), nullable=True),
        sa.Column("difficulty", sa.String(20), nullable=False, server_default="MEDIUM"),
        sa.Column("blooms_taxonomy", sa.String(20), nullable=False, server_default="REMEMBER"),
        sa.Column("concept_tags", sa.Text(), nullable=True),
        sa.Column("branch_id", sa.Uuid(), sa.ForeignKey("branch.id"), nullable=False),
        sa.Column("academic_year_id", sa.Uuid(), sa.ForeignKey("academic_years.id"), nullable=False),
        *_base_columns(),
    )

    op.create_table(
        "question_topics",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("question_id", sa.Uuid(), sa.ForeignKey("questions.id"), nullable=False),
        sa.Column("topic_id", sa.Uuid(), sa.ForeignKey("topics.id"), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False, server_default="1.0"),
        *_base_columns(),
    )

    op.create_table(
        "question_metadata",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("question_id", sa.Uuid(), sa.ForeignKey("questions.id"), nullable=False),
        sa.Column("key", sa.String(100), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        *_base_columns(),
    )

    op.create_table(
        "tests",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("batch_id", sa.Uuid(), sa.ForeignKey("batches.id"), nullable=False),
        sa.Column("subject_id", sa.Uuid(), sa.ForeignKey("subjects.id"), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_minutes", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("total_marks", sa.Float(), nullable=False, server_default="100.0"),
        sa.Column("test_status", sa.String(20), nullable=False, server_default="DRAFT"),
        sa.Column("branch_id", sa.Uuid(), sa.ForeignKey("branch.id"), nullable=False),
        sa.Column("academic_year_id", sa.Uuid(), sa.ForeignKey("academic_years.id"), nullable=False),
        *_base_columns(),
    )

    op.create_table(
        "test_questions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("test_id", sa.Uuid(), sa.ForeignKey("tests.id"), nullable=False),
        sa.Column("question_id", sa.Uuid(), sa.ForeignKey("questions.id"), nullable=False),
        sa.Column("marks_allocated", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("order", sa.Integer(), nullable=False, server_default="0"),
        *_base_columns(),
    )

    op.create_table(
        "student_marks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("student_id", sa.Uuid(), sa.ForeignKey("students.id"), nullable=False),
        sa.Column("test_id", sa.Uuid(), sa.ForeignKey("tests.id"), nullable=False),
        sa.Column("marks_obtained", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("max_marks", sa.Float(), nullable=False, server_default="100.0"),
        sa.Column("percentage", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("grade", sa.String(10), nullable=True),
        sa.Column("is_absent", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("marked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("marked_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("branch_id", sa.Uuid(), sa.ForeignKey("branch.id"), nullable=False),
        sa.Column("academic_year_id", sa.Uuid(), sa.ForeignKey("academic_years.id"), nullable=False),
        *_base_columns(),
    )


def downgrade() -> None:
    op.drop_table("student_marks")
    op.drop_table("test_questions")
    op.drop_table("tests")
    op.drop_table("question_metadata")
    op.drop_table("question_topics")
    op.drop_table("questions")
