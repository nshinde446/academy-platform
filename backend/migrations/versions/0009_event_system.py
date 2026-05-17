"""Create academic_events and processed_events tables.

Revision ID: 0009
Revises: 0008
Create Date: 2026-05-17
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: Union[str, None] = "0008"
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
        "academic_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("event_id", sa.Uuid(), unique=True, nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("student_id", sa.Uuid(), sa.ForeignKey("students.id"), nullable=True),
        sa.Column("teacher_id", sa.Uuid(), sa.ForeignKey("teachers.id"), nullable=True),
        sa.Column("batch_id", sa.Uuid(), sa.ForeignKey("batches.id"), nullable=True),
        sa.Column("subject_id", sa.Uuid(), sa.ForeignKey("subjects.id"), nullable=True),
        sa.Column("topic_id", sa.Uuid(), sa.ForeignKey("topics.id"), nullable=True),
        sa.Column("lecture_id", sa.Uuid(), sa.ForeignKey("lectures.id"), nullable=True),
        sa.Column("test_id", sa.Uuid(), sa.ForeignKey("tests.id"), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("processed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("branch_id", sa.Uuid(), sa.ForeignKey("branch.id"), nullable=True),
        *_base_columns(),
    )

    op.create_table(
        "processed_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("consumer_name", sa.String(100), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processing_status", sa.String(20), nullable=False, server_default="SUCCESS"),
        sa.Column("error_message", sa.Text(), nullable=True),
        *_base_columns(),
    )


def downgrade() -> None:
    op.drop_table("processed_events")
    op.drop_table("academic_events")
