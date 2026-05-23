"""Add LectureSession + N-to-N joins for Plan-vs-Actual Tier 2.

Introduces three tables that decouple "what happened" (LectureSession)
from "what was planned" (Lecture). A session can be linked to 0 plans
(ad_hoc / makeup), 1 plan (normal), or 2+ plans (merged batches). Batch
membership is tracked on its own join so ad_hoc sessions still record
who attended.

Revision ID: 0020
Revises: 0019
Create Date: 2026-05-23
"""

from alembic import op
import sqlalchemy as sa

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def _base_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="active"),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
    ]


def upgrade() -> None:
    op.create_table(
        "lecture_sessions",
        *_base_columns(),
        sa.Column("teacher_id", sa.Uuid(), sa.ForeignKey("teachers.id"), nullable=False),
        sa.Column("classroom_id", sa.Uuid(), sa.ForeignKey("classrooms.id"), nullable=True),
        sa.Column("subject_id", sa.Uuid(), sa.ForeignKey("subjects.id"), nullable=False),
        sa.Column("topic_id", sa.Uuid(), sa.ForeignKey("topics.id"), nullable=True),
        sa.Column("actual_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actual_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivery_mode", sa.String(20), nullable=False, server_default="offline"),
        sa.Column("session_status", sa.String(20), nullable=False, server_default="completed"),
        sa.Column("origin", sa.String(20), nullable=False, server_default="planned"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("branch_id", sa.Uuid(), sa.ForeignKey("branch.id"), nullable=False),
        sa.Column("academic_year_id", sa.Uuid(), sa.ForeignKey("academic_years.id"), nullable=False),
    )
    op.create_index(
        "ix_lecture_sessions_branch_start",
        "lecture_sessions",
        ["branch_id", "actual_start"],
    )

    op.create_table(
        "lecture_session_plans",
        *_base_columns(),
        sa.Column("session_id", sa.Uuid(), sa.ForeignKey("lecture_sessions.id"), nullable=False),
        sa.Column("lecture_id", sa.Uuid(), sa.ForeignKey("lectures.id"), nullable=False),
        sa.Column("branch_id", sa.Uuid(), sa.ForeignKey("branch.id"), nullable=False),
        sa.UniqueConstraint("session_id", "lecture_id", name="uq_session_plan"),
    )
    op.create_index(
        "ix_lecture_session_plans_lecture",
        "lecture_session_plans",
        ["lecture_id"],
    )

    op.create_table(
        "lecture_session_batches",
        *_base_columns(),
        sa.Column("session_id", sa.Uuid(), sa.ForeignKey("lecture_sessions.id"), nullable=False),
        sa.Column("batch_id", sa.Uuid(), sa.ForeignKey("batches.id"), nullable=False),
        sa.Column("branch_id", sa.Uuid(), sa.ForeignKey("branch.id"), nullable=False),
        sa.UniqueConstraint("session_id", "batch_id", name="uq_session_batch"),
    )
    op.create_index(
        "ix_lecture_session_batches_batch",
        "lecture_session_batches",
        ["batch_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_lecture_session_batches_batch", table_name="lecture_session_batches")
    op.drop_table("lecture_session_batches")
    op.drop_index("ix_lecture_session_plans_lecture", table_name="lecture_session_plans")
    op.drop_table("lecture_session_plans")
    op.drop_index("ix_lecture_sessions_branch_start", table_name="lecture_sessions")
    op.drop_table("lecture_sessions")
