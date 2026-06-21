"""Background student-import jobs.

Large imports run in the background (FastAPI BackgroundTasks) so the request
returns immediately and the UI polls progress. The job row id IS the import_id,
so undo/traceability key off it.

Revision ID: 0033
Revises: 0032
Create Date: 2026-06-20
"""

from alembic import op
import sqlalchemy as sa


revision = "0033"
down_revision = "0032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "student_import_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(), server_default="active", nullable=False),
        sa.Column(
            "is_deleted", sa.Boolean(), server_default="false", nullable=False
        ),
        sa.Column("branch_id", sa.Uuid(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=True),
        sa.Column("job_status", sa.String(length=20), nullable=False),
        sa.Column(
            "create_missing_batches", sa.Boolean(), nullable=False
        ),
        sa.Column("total_rows", sa.Integer(), nullable=False),
        sa.Column("processed_rows", sa.Integer(), nullable=False),
        sa.Column("imported", sa.Integer(), nullable=False),
        sa.Column("skipped", sa.Integer(), nullable=False),
        sa.Column("subjects_created", sa.Integer(), nullable=False),
        sa.Column("errors", sa.JSON(), nullable=False),
        sa.Column("warnings", sa.JSON(), nullable=False),
        sa.Column("batches_created", sa.JSON(), nullable=False),
        sa.Column("academic_years_created", sa.JSON(), nullable=False),
        sa.Column("error_detail", sa.String(length=1000), nullable=True),
        sa.ForeignKeyConstraint(["branch_id"], ["branch.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_student_import_jobs_branch_id", "student_import_jobs", ["branch_id"]
    )


def downgrade() -> None:
    op.drop_index(
        "ix_student_import_jobs_branch_id", table_name="student_import_jobs"
    )
    op.drop_table("student_import_jobs")
