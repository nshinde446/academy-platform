"""Teacher leave calendar (planned unavailability).

Scheduling rejects a lecture landing on a teacher's leave, and the substitute
suggester excludes on-leave teachers (S5). Inclusive start_date … end_date.

Revision ID: 0040
Revises: 0039
Create Date: 2026-06-26
"""

from alembic import op
import sqlalchemy as sa


revision = "0040"
down_revision = "0039"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "teacher_leaves",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("teacher_id", sa.Uuid(), nullable=False),
        sa.Column("branch_id", sa.Uuid(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="active"),
        sa.Column(
            "is_deleted", sa.Boolean(), nullable=False, server_default="false"
        ),
        sa.ForeignKeyConstraint(["teacher_id"], ["teachers.id"]),
        sa.ForeignKeyConstraint(["branch_id"], ["branch.id"]),
    )
    op.create_index(
        "ix_teacher_leaves_start_date", "teacher_leaves", ["start_date"]
    )
    op.create_index(
        "ix_teacher_leaves_end_date", "teacher_leaves", ["end_date"]
    )


def downgrade() -> None:
    op.drop_index("ix_teacher_leaves_end_date", table_name="teacher_leaves")
    op.drop_index("ix_teacher_leaves_start_date", table_name="teacher_leaves")
    op.drop_table("teacher_leaves")
