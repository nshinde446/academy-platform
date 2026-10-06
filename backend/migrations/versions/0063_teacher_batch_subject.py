"""teacher_batch_subject_mappings — per-batch secondary teacher subjects

Revision ID: 0063
Revises: 0062
Create Date: 2026-10-06

Adds the table backing the flexible teacher-subject assignment: a teacher can
teach a SECONDARY subject for specific batches, without changing their core
subject(s) in ``teacher_subject_mappings``. One live row per
(teacher, subject, batch); the Subject→Teacher lock treats such a row like a
core qualification, scoped to that batch.
"""

from alembic import op
import sqlalchemy as sa

revision = "0063"
down_revision = "0062"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "teacher_batch_subject_mappings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(), server_default="active", nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("teacher_id", sa.Uuid(), nullable=False),
        sa.Column("subject_id", sa.Uuid(), nullable=False),
        sa.Column("batch_id", sa.Uuid(), nullable=False),
        sa.Column("branch_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["teacher_id"], ["teachers.id"]),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.id"]),
        sa.ForeignKeyConstraint(["batch_id"], ["batches.id"]),
        sa.ForeignKeyConstraint(["branch_id"], ["branch.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_teacher_batch_subject",
        "teacher_batch_subject_mappings",
        ["teacher_id", "subject_id", "batch_id"],
        unique=True,
        postgresql_where=sa.text("is_deleted = false"),
        sqlite_where=sa.text("is_deleted = 0"),
    )


def downgrade() -> None:
    op.drop_index("uq_teacher_batch_subject", table_name="teacher_batch_subject_mappings")
    op.drop_table("teacher_batch_subject_mappings")
