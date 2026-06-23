"""Add students.enrollment_date and parents.import_id (T14).

``enrollment_date`` records when a student joined (pro-rata fees / attendance
start, design §5). ``parents.import_id`` mirrors the students/batches/subjects
traceability so a bulk import that creates Parent rows can be undone as a unit.
Both nullable.

Revision ID: 0035
Revises: 0034
Create Date: 2026-06-23
"""

from alembic import op
import sqlalchemy as sa


revision = "0035"
down_revision = "0034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "students", sa.Column("enrollment_date", sa.Date(), nullable=True)
    )
    op.add_column(
        "parents", sa.Column("import_id", sa.Uuid(), nullable=True)
    )
    op.create_index(
        "ix_parents_import_id", "parents", ["import_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_parents_import_id", table_name="parents")
    op.drop_column("parents", "import_id")
    op.drop_column("students", "enrollment_date")
