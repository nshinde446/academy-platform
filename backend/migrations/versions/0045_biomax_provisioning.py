"""BioMax device provisioning — command queue + user mirror.

Two branch-isolated tables for server→device provisioning:

* ``device_commands`` — outbound command queue (register users via SET_USER_INFO).
  Partial index for fast pending-dequeue; partial-unique idempotency key so a
  re-run of a bulk push can't double-enqueue a user still in flight.
* ``device_users`` — biometrics-free mirror of the device's user table, for
  reconciliation. Never stores a face/photo/template.

Feature is dormant behind BIOMAX_PROVISIONING_ENABLED (default off); this only
creates the tables. See docs/biomax-provisioning-implementation.md.

Revision ID: 0045
Revises: 0044
Create Date: 2026-07-28
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0045"
down_revision = "0044"
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
        "device_commands",
        *_base_columns(),
        sa.Column("branch_id", sa.Uuid(), nullable=False),
        sa.Column("dev_id", sa.String(length=100), nullable=False),
        sa.Column("command", sa.String(length=40), nullable=False),
        sa.Column("vendor_user_id", sa.String(length=64), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("student_id", sa.Uuid(), nullable=True),
        sa.Column("command_status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("trans_id", sa.String(length=64), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=200), nullable=False),
        sa.ForeignKeyConstraint(["branch_id"], ["branch.id"]),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_device_commands_pending",
        "device_commands",
        ["dev_id", "command_status"],
        postgresql_where=sa.text("command_status = 'pending'"),
    )
    op.create_index(
        "uq_device_commands_idempotency",
        "device_commands",
        ["idempotency_key"],
        unique=True,
        postgresql_where=sa.text("command_status IN ('pending', 'sent')"),
    )

    op.create_table(
        "device_users",
        *_base_columns(),
        sa.Column("branch_id", sa.Uuid(), nullable=False),
        sa.Column("dev_id", sa.String(length=100), nullable=False),
        sa.Column("vendor_user_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=True),
        sa.Column("privilege", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("valid_start", sa.String(length=8), nullable=True),
        sa.Column("valid_end", sa.String(length=8), nullable=True),
        sa.Column("has_face", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["branch_id"], ["branch.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dev_id", "vendor_user_id", name="uq_device_users_dev_user"),
    )


def downgrade() -> None:
    op.drop_table("device_users")
    op.drop_index("uq_device_commands_idempotency", table_name="device_commands")
    op.drop_index("ix_device_commands_pending", table_name="device_commands")
    op.drop_table("device_commands")
