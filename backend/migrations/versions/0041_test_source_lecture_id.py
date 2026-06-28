"""Link a paper back to the lecture it was generated from.

Set when the paper composer is opened via the lectures "Generate DPP" flow.
Powers the DPP-coverage metric on the lectures dashboard (how many completed
lectures have a DPP). Nullable — most papers aren't lecture-anchored.

Revision ID: 0041
Revises: 0040
Create Date: 2026-06-28
"""

from alembic import op
import sqlalchemy as sa


revision = "0041"
down_revision = "0040"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tests",
        sa.Column("source_lecture_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_tests_source_lecture_id_lectures",
        "tests",
        "lectures",
        ["source_lecture_id"],
        ["id"],
    )
    op.create_index(
        "ix_tests_source_lecture_id", "tests", ["source_lecture_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_tests_source_lecture_id", table_name="tests")
    op.drop_constraint(
        "fk_tests_source_lecture_id_lectures", "tests", type_="foreignkey"
    )
    op.drop_column("tests", "source_lecture_id")
