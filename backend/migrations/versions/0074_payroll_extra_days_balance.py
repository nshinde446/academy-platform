"""payroll_extra_days_balance — adopt the off-day balance model (client Point 1)

Revision ID: 0074
Revises: 0073
Create Date: 2026-11-14

Client change request (Point 1 "Extra Days / Off-Day Balance"): the carry-forward
balance is now an *off-day balance* that accrues uncapped, can go negative, and
carries forward month to month. Two settings rows seeded by 0069 are switched to
that model:

- ``carry_forward_cap`` → ``0`` (0 = no cap; the balance accrues without trimming)
- ``allow_negative_balance`` → ``true`` (a shortfall drives the balance negative
  and carries forward, instead of raising an uncovered shortfall)

Data-only: it updates two ``payroll_config`` values and adds no schema. Both
remain editable from the Payroll Settings screen. Safe because no payroll month
has been finalised in production yet (module is on hold pending first-month
validation); nothing to recompute.
"""

from alembic import op
import sqlalchemy as sa

revision = "0074"
down_revision = "0073"
branch_labels = None
depends_on = None


def _set_config(key: str, json_value: str) -> None:
    # payroll_config.value is JSON; write a valid JSON literal for each backend.
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            sa.text(
                "UPDATE payroll_config SET value = CAST(:v AS json) WHERE key = :k"
            ).bindparams(v=json_value, k=key)
        )
    else:
        op.execute(
            sa.text("UPDATE payroll_config SET value = :v WHERE key = :k").bindparams(
                v=json_value, k=key
            )
        )


def upgrade() -> None:
    _set_config("carry_forward_cap", "0")
    _set_config("allow_negative_balance", "true")


def downgrade() -> None:
    _set_config("carry_forward_cap", "5")
    _set_config("allow_negative_balance", "false")
