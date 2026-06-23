"""Add import_id to courses and academic_years (T10).

The student import already auto-creates Courses and Academic Years (get-or-create
on the way to a batch), but — unlike batches/subjects — they carried no import_id,
so "undo import" left them behind as orphans (design §7.2). Tag them so undo can
reclaim the ones an import created when nothing else references them.

Revision ID: 0036
Revises: 0035
Create Date: 2026-06-23
"""

from alembic import op
import sqlalchemy as sa


revision = "0036"
down_revision = "0035"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("courses", sa.Column("import_id", sa.Uuid(), nullable=True))
    op.create_index("ix_courses_import_id", "courses", ["import_id"], unique=False)
    op.add_column(
        "academic_years", sa.Column("import_id", sa.Uuid(), nullable=True)
    )
    op.create_index(
        "ix_academic_years_import_id",
        "academic_years",
        ["import_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_academic_years_import_id", table_name="academic_years")
    op.drop_column("academic_years", "import_id")
    op.drop_index("ix_courses_import_id", table_name="courses")
    op.drop_column("courses", "import_id")
