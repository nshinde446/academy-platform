"""Subject import traceability (student import auto-populates the skeleton).

Adds subjects.import_id so the subject skeleton a student import creates for a
new course can be reclaimed by that import's "undo" (only when no chapters have
been loaded on top). Nullable; subjects created via the syllabus import or the
academic UI stay NULL.

Revision ID: 0030
Revises: 0029
Create Date: 2026-06-18
"""

from alembic import op
import sqlalchemy as sa


revision = "0030"
down_revision = "0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "subjects", sa.Column("import_id", sa.Uuid(), nullable=True)
    )
    op.create_index("ix_subjects_import_id", "subjects", ["import_id"])


def downgrade() -> None:
    op.drop_index("ix_subjects_import_id", table_name="subjects")
    op.drop_column("subjects", "import_id")
