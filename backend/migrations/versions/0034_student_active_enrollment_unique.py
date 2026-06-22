"""Partial unique index on a student's active enrollment number.

App-level dedup (enrollment number, per branch, case-insensitive) was the only
guard against a re-upload doubling every student. This adds the DB-level guard:
a UNIQUE index on (branch_id, lower(enrollment_number)) restricted to live rows
with a non-null enrollment number (partial), so soft-deleted rows and the many
students without an enrollment number never collide.

Before creating it we soft-delete any pre-existing active duplicates (keeping the
earliest of each group) so the index can be built on real data without failing.

Revision ID: 0034
Revises: 0033
Create Date: 2026-06-23
"""

from alembic import op
import sqlalchemy as sa


revision = "0034"
down_revision = "0033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    if bind.dialect.name == "postgresql":
        # Keep the earliest active row per (branch, lower(enrollment)); soft-delete
        # the rest so the unique index below can be created on existing prod data.
        op.execute(
            sa.text(
                """
                UPDATE students s
                SET is_deleted = true, updated_at = now()
                WHERE s.is_deleted = false
                  AND s.enrollment_number IS NOT NULL
                  AND EXISTS (
                    SELECT 1 FROM students o
                    WHERE o.branch_id = s.branch_id
                      AND lower(o.enrollment_number) = lower(s.enrollment_number)
                      AND o.is_deleted = false
                      AND o.enrollment_number IS NOT NULL
                      AND (o.created_at < s.created_at
                           OR (o.created_at = s.created_at AND o.id < s.id))
                  )
                """
            )
        )
        op.execute(
            sa.text(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS uq_students_active_enrollment
                ON students (branch_id, lower(enrollment_number))
                WHERE is_deleted = false AND enrollment_number IS NOT NULL
                """
            )
        )
    else:
        # SQLite stores booleans as 0/1.
        op.execute(
            sa.text(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS uq_students_active_enrollment
                ON students (branch_id, lower(enrollment_number))
                WHERE is_deleted = 0 AND enrollment_number IS NOT NULL
                """
            )
        )


def downgrade() -> None:
    op.execute(sa.text("DROP INDEX IF EXISTS uq_students_active_enrollment"))
