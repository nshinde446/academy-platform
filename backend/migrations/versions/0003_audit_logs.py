"""Create audit_logs table.

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-17
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("table_name", sa.String(100), nullable=False),
        sa.Column("record_id", sa.Uuid(), nullable=False),
        sa.Column("old_values", sa.Text(), nullable=True),
        sa.Column("new_values", sa.Text(), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("branch_id", sa.Uuid(), sa.ForeignKey("branch.id"), nullable=True),
    )
    op.create_index("ix_audit_logs_table_record", "audit_logs", ["table_name", "record_id"])
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])
    op.create_index("ix_audit_logs_timestamp", "audit_logs", ["timestamp"])


def downgrade() -> None:
    op.drop_index("ix_audit_logs_timestamp")
    op.drop_index("ix_audit_logs_user_id")
    op.drop_index("ix_audit_logs_table_record")
    op.drop_table("audit_logs")
