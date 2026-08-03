"""Seed the standard assignable roles.

Only ``super_admin`` was ever seeded, but the app authorizes against several
role names (branch_admin, academic_head, teacher, device_operator, student).
Admin-managed user creation can only assign roles that exist in the ``roles``
table, so seed the rest here. Idempotent: inserts only the names that are
missing, so it's safe on an environment that already has some of them.

Revision ID: 0046
Revises: 0045
Create Date: 2026-08-02
"""

import uuid

import sqlalchemy as sa
from alembic import op

revision = "0046"
down_revision = "0045"
branch_labels = None
depends_on = None

# name -> (display_name, description)
_ROLES = {
    "branch_admin": ("Branch Admin", "Manages a branch: staff, students, academics."),
    "academic_head": ("Academic Head", "Owns academics: courses, syllabus, lectures."),
    "teacher": ("Teacher", "Teaches lectures and marks attendance."),
    "device_operator": ("Device Operator", "Manages biometric devices and sync."),
    "student": ("Student", "Student portal access."),
}

_roles_table = sa.table(
    "roles",
    sa.column("id", sa.Uuid),
    sa.column("name", sa.String),
    sa.column("display_name", sa.String),
    sa.column("description", sa.String),
    sa.column("status", sa.String),
    sa.column("is_deleted", sa.Boolean),
)


def upgrade() -> None:
    bind = op.get_bind()
    existing = set(
        bind.execute(sa.select(_roles_table.c.name)).scalars().all()
    )
    rows = [
        {
            "id": uuid.uuid4(),
            "name": name,
            "display_name": display,
            "description": desc,
            "status": "active",
            "is_deleted": False,
        }
        for name, (display, desc) in _ROLES.items()
        if name not in existing
    ]
    if rows:
        op.bulk_insert(_roles_table, rows)


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        _roles_table.delete().where(_roles_table.c.name.in_(list(_ROLES.keys())))
    )
