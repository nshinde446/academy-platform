"""Promote batch_schedules to a real weekly timetable template.

The dormant batch_schedules table held only (day_of_week, start_time,
end_time). To generate concrete lectures from a batch's recurring weekly
pattern (S3), each slot also needs to know what is taught and by whom:

  - subject_id    UUID FK subjects     nullable
  - teacher_id    UUID FK teachers     nullable
  - classroom_id  UUID FK classrooms   nullable
  - delivery_mode VARCHAR(20)          NOT NULL default 'offline'

All nullable/defaulted so existing rows (if any) remain valid. Pure additive.

Revision ID: 0038
Revises: 0037
Create Date: 2026-06-26
"""

from alembic import op
import sqlalchemy as sa


revision = "0038"
down_revision = "0037"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "batch_schedules",
        sa.Column("subject_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "batch_schedules",
        sa.Column("teacher_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "batch_schedules",
        sa.Column("classroom_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "batch_schedules",
        sa.Column(
            "delivery_mode",
            sa.String(length=20),
            nullable=False,
            server_default="offline",
        ),
    )
    op.create_foreign_key(
        "fk_batch_schedules_subject_id",
        "batch_schedules",
        "subjects",
        ["subject_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_batch_schedules_teacher_id",
        "batch_schedules",
        "teachers",
        ["teacher_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_batch_schedules_classroom_id",
        "batch_schedules",
        "classrooms",
        ["classroom_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_batch_schedules_classroom_id", "batch_schedules", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_batch_schedules_teacher_id", "batch_schedules", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_batch_schedules_subject_id", "batch_schedules", type_="foreignkey"
    )
    op.drop_column("batch_schedules", "delivery_mode")
    op.drop_column("batch_schedules", "classroom_id")
    op.drop_column("batch_schedules", "teacher_id")
    op.drop_column("batch_schedules", "subject_id")
