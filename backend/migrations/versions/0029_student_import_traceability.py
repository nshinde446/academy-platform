"""Student/batch import traceability + undo handle.

Adds the columns from the students master-import design §9:
- students.import_id          — groups every student from one upload
- students.import_source_file — original filename, for audit
- students.aspiration_target  — reserved for the class-remap rule (§3)
- batches.import_id           — so an "undo import" can reclaim the batches
                                that import auto-created

All nullable; legacy rows (and single-student / manual-batch creates) stay
valid with NULLs. Indexed on import_id since undo/audit look up by it.

Revision ID: 0029
Revises: 0028
Create Date: 2026-06-18
"""

from alembic import op
import sqlalchemy as sa


revision = "0029"
down_revision = "0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "students", sa.Column("import_id", sa.Uuid(), nullable=True)
    )
    op.add_column(
        "students",
        sa.Column("import_source_file", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "students",
        sa.Column("aspiration_target", sa.String(length=40), nullable=True),
    )
    op.create_index(
        "ix_students_import_id", "students", ["import_id"]
    )

    op.add_column(
        "batches", sa.Column("import_id", sa.Uuid(), nullable=True)
    )
    op.create_index(
        "ix_batches_import_id", "batches", ["import_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_batches_import_id", table_name="batches")
    op.drop_column("batches", "import_id")
    op.drop_index("ix_students_import_id", table_name="students")
    op.drop_column("students", "aspiration_target")
    op.drop_column("students", "import_source_file")
    op.drop_column("students", "import_id")
