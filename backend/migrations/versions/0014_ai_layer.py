"""ai layer

Revision ID: 0014
Revises: 0013
Create Date: 2026-05-17
"""

from alembic import op
import sqlalchemy as sa

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_requests",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("request_type", sa.String(30), nullable=False),
        sa.Column("request_status", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("payload_json", sa.Text(), nullable=True),
        sa.Column("response_json", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("requested_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("branch_id", sa.Uuid(), sa.ForeignKey("branch.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(), server_default="active", nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default="false", nullable=False),
    )

    op.create_table(
        "ai_service_config",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("service_name", sa.String(50), nullable=False),
        sa.Column("config_key", sa.String(100), nullable=False),
        sa.Column("config_value", sa.Text(), nullable=False),
        sa.Column("is_secret", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("branch_id", sa.Uuid(), sa.ForeignKey("branch.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(), server_default="active", nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default="false", nullable=False),
    )


def downgrade() -> None:
    op.drop_table("ai_service_config")
    op.drop_table("ai_requests")
