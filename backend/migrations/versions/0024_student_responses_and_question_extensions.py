"""Tier 11 + 11.5 — per-question student responses + question provenance.

Adds the `student_responses` table that closes the analytics loop:
without per-question correctness data, topic-mastery, item-analysis,
and student-weakness views can't be computed. The roll-up to
`student_marks` is recomputed by the service on every bulk-submit.

Also extends `questions` with provenance/quality columns so the
ingest pipeline (PYQs, study-material PDFs, AI generation later) can
track where each row came from and whether it's approved for use.

Revision ID: 0024
Revises: 0023
Create Date: 2026-05-24
"""

from alembic import op
import sqlalchemy as sa

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "student_responses",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="active"),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("student_id", sa.Uuid(), sa.ForeignKey("students.id"), nullable=False),
        sa.Column("test_id", sa.Uuid(), sa.ForeignKey("tests.id"), nullable=False),
        sa.Column("question_id", sa.Uuid(), sa.ForeignKey("questions.id"), nullable=False),
        # Option letter ("A" | "B" | "C" | "D") or free text for integer/short-answer types.
        sa.Column("selected_answer", sa.String(255), nullable=True),
        sa.Column("is_correct", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("marks_obtained", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("branch_id", sa.Uuid(), sa.ForeignKey("branch.id"), nullable=False),
        sa.Column("academic_year_id", sa.Uuid(), sa.ForeignKey("academic_years.id"), nullable=False),
    )
    op.create_index(
        "ix_student_responses_test",
        "student_responses",
        ["test_id"],
    )
    op.create_index(
        "ix_student_responses_student",
        "student_responses",
        ["student_id"],
    )
    op.create_unique_constraint(
        "uq_student_response_per_student_test_question",
        "student_responses",
        ["student_id", "test_id", "question_id"],
    )

    # Question provenance + quality fields. Default review_status='approved'
    # so existing seed/manual rows continue to behave the same way.
    op.add_column(
        "questions",
        sa.Column("source", sa.String(100), nullable=True),
    )
    op.add_column(
        "questions",
        sa.Column("source_ref", sa.String(255), nullable=True),
    )
    op.add_column(
        "questions",
        sa.Column("diagram_ref", sa.String(500), nullable=True),
    )
    op.add_column(
        "questions",
        sa.Column(
            "review_status",
            sa.String(20),
            nullable=False,
            server_default="approved",
        ),
    )
    op.add_column(
        "questions",
        sa.Column("quality_score", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("questions", "quality_score")
    op.drop_column("questions", "review_status")
    op.drop_column("questions", "diagram_ref")
    op.drop_column("questions", "source_ref")
    op.drop_column("questions", "source")
    op.drop_constraint(
        "uq_student_response_per_student_test_question",
        "student_responses",
        type_="unique",
    )
    op.drop_index("ix_student_responses_student", table_name="student_responses")
    op.drop_index("ix_student_responses_test", table_name="student_responses")
    op.drop_table("student_responses")
