"""teacher_leave_balance_wof — leave types/quotas + WOF opening balance

Revision ID: 0071
Revises: 0070
Create Date: 2026-10-31

Teacher Portal Changes (Changes 3/4 + WOF accrual):
- ``teacher_leaves``: add ``leave_type`` (casual/sick/paid/lwp) and ``half_day``.
  Additive, defaulted, so existing rows are unaffected.
- ``leave_type_quotas``: per-branch, per-calendar-year quota per leave type.
- ``teacher_wof_openings``: a teacher's opening Weekly-Off balance as of a date
  (seeded from the client's 'WOF Till Sept 26' list). The live balance adds the
  extra days worked since (present − 24 per month).

Reversible.
"""

from alembic import op
import sqlalchemy as sa

revision = "0071"
down_revision = "0070"
branch_labels = None
depends_on = None


def _base_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(), server_default="active", nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default="false", nullable=False),
    ]


def upgrade() -> None:
    op.add_column(
        "teacher_leaves",
        sa.Column("leave_type", sa.String(length=20), server_default="casual", nullable=False),
    )
    op.add_column(
        "teacher_leaves",
        sa.Column("half_day", sa.Boolean(), server_default="false", nullable=False),
    )

    op.create_table(
        "leave_type_quotas",
        *_base_columns(),
        sa.Column("branch_id", sa.Uuid(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("leave_type", sa.String(length=20), nullable=False),
        sa.Column("quota_days", sa.Numeric(5, 1), nullable=False),
        sa.ForeignKeyConstraint(["branch_id"], ["branch.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("branch_id", "year", "leave_type", name="uq_leave_type_quota"),
    )

    op.create_table(
        "teacher_wof_openings",
        *_base_columns(),
        sa.Column("teacher_id", sa.Uuid(), nullable=False),
        sa.Column("branch_id", sa.Uuid(), nullable=False),
        sa.Column("opening_balance", sa.Numeric(6, 1), nullable=False),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.ForeignKeyConstraint(["teacher_id"], ["teachers.id"]),
        sa.ForeignKeyConstraint(["branch_id"], ["branch.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("teacher_id", name="uq_teacher_wof_opening"),
    )


def downgrade() -> None:
    op.drop_table("teacher_wof_openings")
    op.drop_table("leave_type_quotas")
    op.drop_column("teacher_leaves", "half_day")
    op.drop_column("teacher_leaves", "leave_type")
