"""teacher_leave_approval — approval workflow on teacher_leaves

Revision ID: 0068
Revises: 0067
Create Date: 2026-10-26

Adds a request→approval lifecycle to ``teacher_leaves`` so teachers can apply
for leave from the self-service portal and an academic head / branch admin
approves it. Only ``approved`` leaves block scheduling + feed the substitute
suggester (the repository's ``teacher_on_leave`` now filters on status).

Additive only. ``status`` defaults to ``approved`` so every pre-0068 row (all
admin-created today) keeps blocking exactly as before — no behaviour change for
existing data.
"""

from alembic import op
import sqlalchemy as sa

revision = "0068"
down_revision = "0067"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "teacher_leaves",
        sa.Column(
            "status", sa.String(length=20), nullable=False, server_default="approved"
        ),
    )
    op.add_column("teacher_leaves", sa.Column("requested_by", sa.Uuid(), nullable=True))
    op.add_column("teacher_leaves", sa.Column("decided_by", sa.Uuid(), nullable=True))
    op.add_column(
        "teacher_leaves",
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "teacher_leaves",
        sa.Column("decision_note", sa.String(length=255), nullable=True),
    )
    op.create_index(
        "ix_teacher_leaves_status", "teacher_leaves", ["status"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_teacher_leaves_status", table_name="teacher_leaves")
    op.drop_column("teacher_leaves", "decision_note")
    op.drop_column("teacher_leaves", "decided_at")
    op.drop_column("teacher_leaves", "decided_by")
    op.drop_column("teacher_leaves", "requested_by")
    op.drop_column("teacher_leaves", "status")
