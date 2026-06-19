"""Add stream to students (PCM / PCB / PCMB).

The stream a student opts into for their target exam decides which subjects they
actually sit: Physics + Chemistry are common; Maths is PCM-only; Biology is
PCB-only. Distinct from any board syllabus. Nullable; the importer defaults it
from Target (NEET->PCB, JEE->PCM, Both->PCMB, MHT-CET->PCB fallback) and admins
can override it per student.

Revision ID: 0032
Revises: 0031
Create Date: 2026-06-19
"""

from alembic import op
import sqlalchemy as sa


revision = "0032"
down_revision = "0031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "students", sa.Column("stream", sa.String(length=10), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("students", "stream")
