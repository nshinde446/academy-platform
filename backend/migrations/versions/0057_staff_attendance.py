"""Staff attendance — raw punches + daily rollup (staff twin of the student path)

Staff badge on the same BioMax fleet as students; the ingest funnel now resolves
a device userId against ``Staff.emp_code`` and writes here instead of dropping it.

* ``staff_raw_punch_logs`` — raw punches, mirror of ``raw_punch_logs``.
* ``staff_daily_attendance`` — one row per staff per local day, extended with
  work / OT / break minutes for the TeamOffice-style reports; day_status adds
  HALF_DAY / WO / HOLIDAY on top of PRESENT/LATE/ABSENT.

Revision ID: 0057
Revises: 0056
Create Date: 2026-09-11
"""

from alembic import op
import sqlalchemy as sa


revision = "0057"
down_revision = "0056"
branch_labels = None
depends_on = None


def _base_columns() -> list:
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
    op.create_table(
        "staff_raw_punch_logs",
        *_base_columns(),
        sa.Column("device_id", sa.String(length=100), nullable=False),
        sa.Column("sync_batch_id", sa.String(length=100), nullable=True),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("staff_id", sa.Uuid(), nullable=False),
        sa.Column("punch_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("direction", sa.String(length=10), nullable=True),
        sa.Column("branch_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["staff_id"], ["staff.id"]),
        sa.ForeignKeyConstraint(["branch_id"], ["branch.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_staff_raw_punch_logs_staff_ts",
        "staff_raw_punch_logs",
        ["staff_id", "punch_timestamp"],
    )

    op.create_table(
        "staff_daily_attendance",
        *_base_columns(),
        sa.Column("staff_id", sa.Uuid(), nullable=False),
        sa.Column("branch_id", sa.Uuid(), nullable=False),
        sa.Column("attendance_date", sa.Date(), nullable=False),
        sa.Column("first_in", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_out", sa.DateTime(timezone=True), nullable=True),
        sa.Column("day_status", sa.String(length=20), nullable=False),
        sa.Column("signoff", sa.String(length=20), nullable=False, server_default="NA"),
        sa.Column("source", sa.String(length=20), nullable=False, server_default="BIOMETRIC"),
        sa.Column("work_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ot_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("break_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("override_by", sa.Uuid(), nullable=True),
        sa.Column("override_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["staff_id"], ["staff.id"]),
        sa.ForeignKeyConstraint(["branch_id"], ["branch.id"]),
        sa.ForeignKeyConstraint(["override_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("staff_id", "attendance_date", name="uq_staff_daily_attendance_staff_date"),
    )
    op.create_index(
        "ix_staff_daily_attendance_date", "staff_daily_attendance", ["attendance_date"]
    )


def downgrade() -> None:
    op.drop_index("ix_staff_daily_attendance_date", table_name="staff_daily_attendance")
    op.drop_table("staff_daily_attendance")
    op.drop_index("ix_staff_raw_punch_logs_staff_ts", table_name="staff_raw_punch_logs")
    op.drop_table("staff_raw_punch_logs")
