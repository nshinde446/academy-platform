"""Test Portal (Phase 1) — OMR result upload + multi-subject + review staging.

Extends the existing tests module for the ZipGrade CSV upload flow:

* ``tests.omr_type`` — OMR sheet layout the CSV was scanned against (50Q/100Q).
* ``tests.answer_key_file`` — uploaded answer key kept for reference (PR-B).
* ``test_subjects`` — subjects a test covers (full multi-subject); ``subject_id``
  still holds the primary for backward compatibility.
* ``student_marks.raw_csv_row`` — original CSV row for audit / re-processing.
* ``test_import_review`` — CSV rows whose PRN didn't match a batch student,
  flagged for admin resolution (PR-B).

Revision ID: 0054
Revises: 0053
Create Date: 2026-09-02
"""

from alembic import op
import sqlalchemy as sa


revision = "0054"
down_revision = "0053"
branch_labels = None
depends_on = None


def _base_columns() -> list:
    return [
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(), server_default="active", nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default="false", nullable=False),
    ]


def upgrade() -> None:
    op.add_column("tests", sa.Column("omr_type", sa.String(length=20), nullable=True))
    op.add_column("tests", sa.Column("answer_key_file", sa.String(length=500), nullable=True))
    op.add_column("student_marks", sa.Column("raw_csv_row", sa.JSON(), nullable=True))

    op.create_table(
        "test_subjects",
        *_base_columns(),
        sa.Column("test_id", sa.Uuid(), nullable=False),
        sa.Column("subject_id", sa.Uuid(), nullable=False),
        sa.Column("branch_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["test_id"], ["tests.id"]),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.id"]),
        sa.ForeignKeyConstraint(["branch_id"], ["branch.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_test_subjects_test", "test_subjects", ["test_id"])

    op.create_table(
        "test_import_review",
        *_base_columns(),
        sa.Column("test_id", sa.Uuid(), nullable=False),
        sa.Column("branch_id", sa.Uuid(), nullable=False),
        sa.Column("csv_prn", sa.String(length=100), nullable=True),
        sa.Column("csv_name", sa.String(length=255), nullable=True),
        sa.Column("raw_row", sa.JSON(), nullable=False),
        sa.Column("resolved", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("resolved_student_id", sa.Uuid(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["test_id"], ["tests.id"]),
        sa.ForeignKeyConstraint(["branch_id"], ["branch.id"]),
        sa.ForeignKeyConstraint(["resolved_student_id"], ["students.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_test_import_review_test", "test_import_review", ["test_id"])


def downgrade() -> None:
    op.drop_index("ix_test_import_review_test", table_name="test_import_review")
    op.drop_table("test_import_review")
    op.drop_index("ix_test_subjects_test", table_name="test_subjects")
    op.drop_table("test_subjects")
    op.drop_column("student_marks", "raw_csv_row")
    op.drop_column("tests", "answer_key_file")
    op.drop_column("tests", "omr_type")
