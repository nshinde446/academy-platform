"""Test Portal per-subject manual flow — multi-batch, per-subject marks, question_type

Revision ID: 0064
Revises: 0063
Create Date: 2026-10-08

Adds the schema for the per-subject manual-marks flow (Test Portal spec) alongside
the existing ZipGrade/OMR single-score flow:

- ``tests.question_type`` (MCQ_ONLY | MCQ_NUMERICAL | NA) — JEE question style, NA otherwise.
- ``test_subjects.total_marks`` — per-subject total for the new flow (NULL for OMR).
- ``test_batches`` — a test scheduled for one or many batches (``tests.batch_id`` stays
  the primary batch for backward compatibility).
- ``test_subject_marks`` — per-student, per-subject marks; summed into the aggregate
  ``student_marks`` so the existing rank list/history keep working.
"""

from alembic import op
import sqlalchemy as sa

revision = "0064"
down_revision = "0063"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tests",
        sa.Column("question_type", sa.String(length=20), server_default="NA", nullable=False),
    )
    op.add_column(
        "test_subjects",
        sa.Column("total_marks", sa.Float(), nullable=True),
    )

    op.create_table(
        "test_batches",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(), server_default="active", nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("test_id", sa.Uuid(), nullable=False),
        sa.Column("batch_id", sa.Uuid(), nullable=False),
        sa.Column("branch_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["test_id"], ["tests.id"]),
        sa.ForeignKeyConstraint(["batch_id"], ["batches.id"]),
        sa.ForeignKeyConstraint(["branch_id"], ["branch.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_test_batch",
        "test_batches",
        ["test_id", "batch_id"],
        unique=True,
        postgresql_where=sa.text("is_deleted = false"),
        sqlite_where=sa.text("is_deleted = 0"),
    )

    op.create_table(
        "test_subject_marks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(), server_default="active", nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("test_id", sa.Uuid(), nullable=False),
        sa.Column("student_id", sa.Uuid(), nullable=False),
        sa.Column("batch_id", sa.Uuid(), nullable=True),
        sa.Column("subject_id", sa.Uuid(), nullable=False),
        sa.Column("marks_obtained", sa.Float(), nullable=True),
        sa.Column("absent", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("branch_id", sa.Uuid(), nullable=False),
        sa.Column("academic_year_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["test_id"], ["tests.id"]),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"]),
        sa.ForeignKeyConstraint(["batch_id"], ["batches.id"]),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.id"]),
        sa.ForeignKeyConstraint(["branch_id"], ["branch.id"]),
        sa.ForeignKeyConstraint(["academic_year_id"], ["academic_years.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_test_subject_mark",
        "test_subject_marks",
        ["test_id", "student_id", "subject_id"],
        unique=True,
        postgresql_where=sa.text("is_deleted = false"),
        sqlite_where=sa.text("is_deleted = 0"),
    )


def downgrade() -> None:
    op.drop_index("uq_test_subject_mark", table_name="test_subject_marks")
    op.drop_table("test_subject_marks")
    op.drop_index("uq_test_batch", table_name="test_batches")
    op.drop_table("test_batches")
    op.drop_column("test_subjects", "total_marks")
    op.drop_column("tests", "question_type")
