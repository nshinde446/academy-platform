"""Curriculum import traceability (student import auto-populates chapters/topics).

Adds chapters.import_id and topics.import_id so the curriculum a student import
auto-creates for a new course's subject skeleton can be reclaimed by that
import's "undo" (a subject is only kept if some chapter it didn't create has
since been loaded on top). Nullable; curriculum created via the syllabus import
or the academic UI stays NULL.

Revision ID: 0031
Revises: 0030
Create Date: 2026-06-18
"""

from alembic import op
import sqlalchemy as sa


revision = "0031"
down_revision = "0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("chapters", sa.Column("import_id", sa.Uuid(), nullable=True))
    op.create_index("ix_chapters_import_id", "chapters", ["import_id"])
    op.add_column("topics", sa.Column("import_id", sa.Uuid(), nullable=True))
    op.create_index("ix_topics_import_id", "topics", ["import_id"])


def downgrade() -> None:
    op.drop_index("ix_topics_import_id", table_name="topics")
    op.drop_column("topics", "import_id")
    op.drop_index("ix_chapters_import_id", table_name="chapters")
    op.drop_column("chapters", "import_id")
