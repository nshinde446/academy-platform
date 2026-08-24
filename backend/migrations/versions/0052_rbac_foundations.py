"""RBAC foundations: new roles, coordinator/accounts scoping tables, delivery sent_by.

Additive only (no enforcement yet):
- Seed roles ``floor_coordinator`` and ``accounts``; relabel ``super_admin``'s
  display name to "Manager" (it already is the full-access role the spec calls
  Manager).
- Create ``batch_coordinators`` (Floor Coordinator → batch scope) and
  ``accounts_attendance_grants`` (Manager-granted attendance visibility for
  Accounts, optionally time-limited).
- Add ``notification_queue.sent_by`` so the WhatsApp delivery log can show
  whether a message was a manual or an auto (cutoff) send.

Revision ID: 0052
Revises: 0051
Create Date: 2026-08-24
"""

import uuid

from alembic import op
import sqlalchemy as sa


revision = "0052"
down_revision = "0051"
branch_labels = None
depends_on = None


_NEW_ROLES = {
    "floor_coordinator": (
        "Floor Coordinator",
        "Attendance + lecture scheduling for their assigned batches only.",
    ),
    "accounts": ("Accounts", "Fees/accounts module; attendance only if granted."),
}


def _base_columns() -> list:
    return [
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(), server_default="active", nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default="false", nullable=False),
    ]


def upgrade() -> None:
    # ── new roles + Manager relabel ──────────────────────────────────────────
    roles = sa.table(
        "roles",
        sa.column("id", sa.Uuid),
        sa.column("name", sa.String),
        sa.column("display_name", sa.String),
        sa.column("description", sa.String),
        sa.column("status", sa.String),
        sa.column("is_deleted", sa.Boolean),
    )
    op.bulk_insert(
        roles,
        [
            {
                "id": uuid.uuid4(),
                "name": name,
                "display_name": display,
                "description": desc,
                "status": "active",
                "is_deleted": False,
            }
            for name, (display, desc) in _NEW_ROLES.items()
        ],
    )
    op.execute(
        "UPDATE roles SET display_name = 'Manager' WHERE name = 'super_admin'"
    )

    # ── batch_coordinators ───────────────────────────────────────────────────
    op.create_table(
        "batch_coordinators",
        *_base_columns(),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("batch_id", sa.Uuid(), nullable=False),
        sa.Column("branch_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["batch_id"], ["batches.id"]),
        sa.ForeignKeyConstraint(["branch_id"], ["branch.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "batch_id", name="uq_batch_coordinator"),
    )
    op.create_index(
        "ix_batch_coordinators_user", "batch_coordinators", ["user_id"]
    )

    # ── accounts_attendance_grants ───────────────────────────────────────────
    op.create_table(
        "accounts_attendance_grants",
        *_base_columns(),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("branch_id", sa.Uuid(), nullable=False),
        sa.Column("batch_id", sa.Uuid(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("granted_by", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["branch_id"], ["branch.id"]),
        sa.ForeignKeyConstraint(["batch_id"], ["batches.id"]),
        sa.ForeignKeyConstraint(["granted_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_accounts_grants_user", "accounts_attendance_grants", ["user_id"]
    )

    # ── delivery-log sent_by ─────────────────────────────────────────────────
    op.add_column(
        "notification_queue",
        sa.Column("sent_by", sa.String(length=20), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("notification_queue", "sent_by")
    op.drop_index("ix_accounts_grants_user", table_name="accounts_attendance_grants")
    op.drop_table("accounts_attendance_grants")
    op.drop_index("ix_batch_coordinators_user", table_name="batch_coordinators")
    op.drop_table("batch_coordinators")
    op.execute(
        "UPDATE roles SET display_name = 'Super Admin' WHERE name = 'super_admin'"
    )
    op.execute("DELETE FROM roles WHERE name IN ('floor_coordinator', 'accounts')")
