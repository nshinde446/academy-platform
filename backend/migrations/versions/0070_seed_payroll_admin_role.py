"""seed_payroll_admin_role — dedicated role that runs the payroll module

Revision ID: 0070
Revises: 0069
Create Date: 2026-10-27

Adds a ``payroll_admin`` role. It is the super-admin-equivalent *within payroll*:
it may set up months, close/lock/reopen them, change payroll settings, and view
every payroll screen — without granting broader super_admin powers. Mirrors the
dedicated ``teacher_portal`` role pattern. Idempotent; seeds the role only if a
``payroll_admin`` row isn't already present.
"""

import uuid

from alembic import op
import sqlalchemy as sa

revision = "0070"
down_revision = "0069"
branch_labels = None
depends_on = None

_roles_table = sa.table(
    "roles",
    sa.column("id", sa.Uuid),
    sa.column("name", sa.String),
    sa.column("display_name", sa.String),
    sa.column("description", sa.String),
    sa.column("status", sa.String),
    sa.column("is_deleted", sa.Boolean),
)

_NAME = "payroll_admin"
_DISPLAY = "Payroll Admin"
_DESC = "Runs the payroll module: month setup, close/lock/reopen, settings, and all payroll views."


def upgrade() -> None:
    bind = op.get_bind()
    existing = set(bind.execute(sa.select(_roles_table.c.name)).scalars().all())
    if _NAME not in existing:
        op.bulk_insert(
            _roles_table,
            [{
                "id": uuid.uuid4(),
                "name": _NAME,
                "display_name": _DISPLAY,
                "description": _DESC,
                "status": "active",
                "is_deleted": False,
            }],
        )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(_roles_table.delete().where(_roles_table.c.name == _NAME))
