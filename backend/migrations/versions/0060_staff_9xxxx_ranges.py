"""Re-range staff departments into the 9xxxx block

Staff employee codes move into a dedicated 9xxxx series so they never collide
with student device ids: all staff codes start with 9, the 2nd digit marks the
department. Updates the seeded department ranges in place (idempotent by name);
existing staff rows keep their codes (any now outside the new range read as
legacy, which is fine).

New ranges: Teachers 91000-91999, Admin 92000-92999, Accounts 93000-93999,
Security 94000-94999, Cleaning 95000-95999, Marketing 96000-96999.

Revision ID: 0060
Revises: 0059
Create Date: 2026-09-13
"""

from alembic import op
import sqlalchemy as sa


revision = "0060"
down_revision = "0059"
branch_labels = None
depends_on = None


# (name, new_start, new_end, old_start, old_end)
_RANGES = [
    ("MSA-Teachers", 91000, 91999, 1, 50),
    ("MSA-Administration", 92000, 92999, 51, 70),
    ("MSA-Accounts", 93000, 93999, 71, 80),
    ("Security", 94000, 94999, 81, 90),
    ("Cleaning Unit", 95000, 95999, 91, 100),
    ("MSA-Marketing", 96000, 96999, 101, 110),
]


def _apply(pairs: list[tuple[str, int, int]]) -> None:
    conn = op.get_bind()
    stmt = sa.text(
        "UPDATE departments SET id_range_start=:s, id_range_end=:e "
        "WHERE name=:n AND is_deleted = false"
    )
    for name, start, end in pairs:
        conn.execute(stmt, {"n": name, "s": start, "e": end})


def upgrade() -> None:
    _apply([(n, s, e) for (n, s, e, _os, _oe) in _RANGES])


def downgrade() -> None:
    _apply([(n, os, oe) for (n, _s, _e, os, oe) in _RANGES])
