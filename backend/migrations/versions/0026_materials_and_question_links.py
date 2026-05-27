"""M1.1 — Materials library + many-to-many to batches, link questions.

Adds the content-management layer beneath the question bank:

- ``materials``: one row per uploaded file (PDF/Word/image/text).
  Tagged with class, subject, topic, category, exam_types so the
  question bank can be filtered by these facets and the test composer
  can pick from a properly scoped pool.
- ``material_batches``: M2M join. Same NCERT PDF feeds multiple
  batches without re-uploading.
- ``questions.material_id``: nullable FK back to the source material.
  Legacy 719 studymat rows stay valid; backfill script will populate
  this for existing rows in a separate step.
- ``questions.exam_types``: TEXT[] inherited from the parent material
  at ingest time; individual questions can override later.

Locked design calls in docs/study-material-and-question-bank.md:
- Local FS storage (S3 swap later via interface)
- Shared library + M2M to batches (not per-batch silos)
- Fixed category enum (NCERT/DPP/CPP/TopicWise/PYQ/Notes/Other)

Revision ID: 0026
Revises: 0025
Create Date: 2026-05-28
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "materials",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="active"),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),

        sa.Column("filename", sa.String(500), nullable=False),
        sa.Column("storage_key", sa.String(800), nullable=False, unique=True),
        sa.Column("mime_type", sa.String(120), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        # SHA-256 hex digest, 64 chars. Used for dedup on upload.
        sa.Column("sha256", sa.String(64), nullable=False),

        sa.Column("academic_year_id", sa.Uuid(),
                  sa.ForeignKey("academic_years.id"), nullable=False),
        # "10" | "11" | "12" | "drop" — kept as string for forward compat
        # (e.g. "9" if board prep expands downward).
        sa.Column("class_label", sa.String(8), nullable=False),
        sa.Column("subject_id", sa.Uuid(),
                  sa.ForeignKey("subjects.id"), nullable=False),
        sa.Column("topic", sa.String(120), nullable=True),
        # MaterialCategory enum: ncert|dpp|cpp|topic_wise|pyq|notes|other.
        sa.Column("category", sa.String(20), nullable=False),
        sa.Column("exam_types", postgresql.ARRAY(sa.Text()),
                  nullable=False, server_default="{}"),
        sa.Column("description", sa.Text(), nullable=True),

        # ingest pipeline state. Separate from BaseModel.status which is
        # the standard "active|inactive|..." column.
        sa.Column("ingest_status", sa.String(20),
                  nullable=False, server_default="uploaded"),
        sa.Column("ingest_error", sa.Text(), nullable=True),
        # Denormalized counter so the materials list page is cheap.
        # Updated by the ingest pipeline + backfill script.
        sa.Column("question_count", sa.Integer(),
                  nullable=False, server_default="0"),

        sa.Column("branch_id", sa.Uuid(),
                  sa.ForeignKey("branch.id"), nullable=False),
    )

    op.create_index(
        "ix_materials_browse",
        "materials",
        ["academic_year_id", "class_label", "subject_id", "category"],
        postgresql_where=sa.text("is_deleted = false"),
    )
    op.create_index("ix_materials_sha256", "materials", ["sha256"])

    op.create_table(
        "material_batches",
        sa.Column("material_id", sa.Uuid(),
                  sa.ForeignKey("materials.id", ondelete="CASCADE"),
                  primary_key=True),
        sa.Column("batch_id", sa.Uuid(),
                  sa.ForeignKey("batches.id", ondelete="CASCADE"),
                  primary_key=True),
        sa.Column("linked_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("linked_by", sa.Uuid(),
                  sa.ForeignKey("users.id"), nullable=False),
    )
    op.create_index("ix_material_batches_batch", "material_batches", ["batch_id"])

    op.add_column(
        "questions",
        sa.Column("material_id", sa.Uuid(),
                  sa.ForeignKey("materials.id"), nullable=True),
    )
    op.add_column(
        "questions",
        sa.Column("exam_types", postgresql.ARRAY(sa.Text()),
                  nullable=False, server_default="{}"),
    )
    op.create_index("ix_questions_material", "questions", ["material_id"])
    op.create_index(
        "ix_questions_exam_types",
        "questions",
        ["exam_types"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index("ix_questions_exam_types", table_name="questions")
    op.drop_index("ix_questions_material", table_name="questions")
    op.drop_column("questions", "exam_types")
    op.drop_column("questions", "material_id")

    op.drop_index("ix_material_batches_batch", table_name="material_batches")
    op.drop_table("material_batches")

    op.drop_index("ix_materials_sha256", table_name="materials")
    op.drop_index("ix_materials_browse", table_name="materials")
    op.drop_table("materials")
