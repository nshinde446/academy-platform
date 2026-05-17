"""Create raw_punch_logs, attendance_records, attendance_exceptions tables.

Revision ID: 0007
Revises: 0006
Create Date: 2026-05-17
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
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
        "raw_punch_logs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("device_id", sa.String(100), nullable=False),
        sa.Column("sync_batch_id", sa.String(100), nullable=True),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("student_id", sa.Uuid(), sa.ForeignKey("students.id"), nullable=False),
        sa.Column("punch_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("branch_id", sa.Uuid(), sa.ForeignKey("branch.id"), nullable=False),
        *_base_columns(),
    )

    op.create_table(
        "attendance_records",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("student_id", sa.Uuid(), sa.ForeignKey("students.id"), nullable=False),
        sa.Column("lecture_id", sa.Uuid(), sa.ForeignKey("lectures.id"), nullable=False),
        sa.Column("attendance_status", sa.String(20), nullable=False, server_default="ABSENT"),
        sa.Column("marked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("marked_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("source", sa.String(20), nullable=False, server_default="MANUAL"),
        sa.Column("branch_id", sa.Uuid(), sa.ForeignKey("branch.id"), nullable=False),
        *_base_columns(),
    )

    op.create_table(
        "attendance_exceptions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("student_id", sa.Uuid(), sa.ForeignKey("students.id"), nullable=False),
        sa.Column("lecture_id", sa.Uuid(), sa.ForeignKey("lectures.id"), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("resolved", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("resolution_notes", sa.Text(), nullable=True),
        sa.Column("branch_id", sa.Uuid(), sa.ForeignKey("branch.id"), nullable=False),
        *_base_columns(),
    )


def downgrade() -> None:
    op.drop_table("attendance_exceptions")
    op.drop_table("attendance_records")
    op.drop_table("raw_punch_logs")
