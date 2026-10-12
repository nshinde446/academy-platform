"""late_fine_slabs — configurable fine bands for the Staff Late Fine Report

Revision ID: 0066
Revises: 0065
Create Date: 2026-10-12

Seeds the three fined bands from the requirement (1-5 -> 200 light blue,
6-10 -> 500 yellow, 11+ -> 1000 red). 0-or-less minutes carry no fine (no row).
"""

import uuid

from alembic import op
import sqlalchemy as sa

revision = "0066"
down_revision = "0065"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "late_fine_slabs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(), server_default="active", nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("min_minutes", sa.Integer(), nullable=False),
        sa.Column("max_minutes", sa.Integer(), nullable=True),
        sa.Column("fine_amount", sa.Float(), nullable=False),
        sa.Column("color_hex", sa.String(length=7), nullable=False),
        sa.Column("label", sa.String(length=50), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.bulk_insert(
        sa.table(
            "late_fine_slabs",
            sa.column("id", sa.Uuid()),
            sa.column("min_minutes", sa.Integer()),
            sa.column("max_minutes", sa.Integer()),
            sa.column("fine_amount", sa.Float()),
            sa.column("color_hex", sa.String()),
            sa.column("label", sa.String()),
            sa.column("status", sa.String()),
            sa.column("is_deleted", sa.Boolean()),
        ),
        [
            {"id": uuid.uuid4(), "min_minutes": 1, "max_minutes": 5, "fine_amount": 200.0,
             "color_hex": "#BDD7EE", "label": "1 to 5", "status": "active", "is_deleted": False},
            {"id": uuid.uuid4(), "min_minutes": 6, "max_minutes": 10, "fine_amount": 500.0,
             "color_hex": "#FFEB84", "label": "6 to 10", "status": "active", "is_deleted": False},
            {"id": uuid.uuid4(), "min_minutes": 11, "max_minutes": None, "fine_amount": 1000.0,
             "color_hex": "#FF6B6B", "label": "11 or more", "status": "active", "is_deleted": False},
        ],
    )


def downgrade() -> None:
    op.drop_table("late_fine_slabs")
