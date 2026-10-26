"""payroll_foundations — days-based payroll tables + config

Revision ID: 0069
Revises: 0068
Create Date: 2026-10-26

New tables only for the Payroll module (``Payroll_Module_Explained.pdf``). The
existing attendance, shift, late-fine and audit tables are reused and NOT
changed — payroll reads them and never writes them.

Creates:
- payroll_month_settings   — required days + lifecycle per branch-month (§1/§6)
- payroll_month_holidays   — paid holidays / leaves per month (§1)
- payroll_staff_month      — the computed per-staff monthly row (§2/§7)
- carry_forward_ledger     — append-only balance ledger (§4); a Postgres trigger
                             blocks UPDATE/DELETE so corrections must be reversal
                             rows
- extra_day_requests       — make-up request flow (§5)
- extra_day_request_history— append-only status history (§5)
- payroll_config           — key/value settings, seeded with §8 defaults

Reversible: downgrade drops the trigger, the seeded config and every table.
"""

import uuid

from alembic import op
import sqlalchemy as sa

revision = "0069"
down_revision = "0068"
branch_labels = None
depends_on = None

_DAYS = sa.Numeric(6, 1)
_MONEY = sa.Numeric(10, 2)

# payroll_config seed — keep in sync with
# app.modules.payroll.services.config_service.DEFAULTS.
_CONFIG_DEFAULTS: dict[str, object] = {
    "payroll_enabled": False,
    "holiday_treatment": "credited",
    "allow_half_day": True,
    "carry_forward_cap": 5,
    "carry_forward_expiry_months": 0,
    "allow_payout": False,
    "allow_negative_balance": False,
    "unapproved_shortfall": "unpaid",
    "request_raiser_roles": ["accounts", "branch_admin"],
    "request_approver_role": "super_admin",
    "allow_manager_approver": False,
    "prorate_on_join_leave": True,
    "prorate_rounding": 0.5,
}


def _base_columns() -> list[sa.Column]:
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
    # ── payroll_month_settings ──────────────────────────────────────────────
    op.create_table(
        "payroll_month_settings",
        *_base_columns(),
        sa.Column("branch_id", sa.Uuid(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("required_days", _DAYS, nullable=False),
        sa.Column("lifecycle", sa.String(length=10), server_default="OPEN", nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["branch_id"], ["branch.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_payroll_month_settings_branch_ym",
        "payroll_month_settings",
        ["branch_id", "year", "month"],
        unique=True,
        postgresql_where=sa.text("is_deleted = false"),
        sqlite_where=sa.text("is_deleted = 0"),
    )

    # ── payroll_month_holidays ──────────────────────────────────────────────
    op.create_table(
        "payroll_month_holidays",
        *_base_columns(),
        sa.Column("branch_id", sa.Uuid(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("holiday_date", sa.Date(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("kind", sa.String(length=20), server_default="HOLIDAY", nullable=False),
        sa.Column("credit_days", sa.Numeric(3, 1), server_default="1.0", nullable=False),
        sa.ForeignKeyConstraint(["branch_id"], ["branch.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_payroll_month_holidays_branch_ym",
        "payroll_month_holidays",
        ["branch_id", "year", "month"],
    )

    # ── payroll_staff_month ─────────────────────────────────────────────────
    op.create_table(
        "payroll_staff_month",
        *_base_columns(),
        sa.Column("branch_id", sa.Uuid(), nullable=False),
        sa.Column("staff_id", sa.Uuid(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("required_days", _DAYS, server_default="0", nullable=False),
        sa.Column("makeup_days", _DAYS, server_default="0", nullable=False),
        sa.Column("effective_required", _DAYS, server_default="0", nullable=False),
        sa.Column("present_days", _DAYS, server_default="0", nullable=False),
        sa.Column("half_days", sa.Integer(), server_default="0", nullable=False),
        sa.Column("paid_leave_days", _DAYS, server_default="0", nullable=False),
        sa.Column("credited_days", _DAYS, server_default="0", nullable=False),
        sa.Column("net_days", _DAYS, server_default="0", nullable=False),
        sa.Column("extra_days", _DAYS, server_default="0", nullable=False),
        sa.Column("shortfall_days", _DAYS, server_default="0", nullable=False),
        sa.Column("balance_in", _DAYS, server_default="0", nullable=False),
        sa.Column("balance_out", _DAYS, server_default="0", nullable=False),
        sa.Column("uncovered_days", _DAYS, server_default="0", nullable=False),
        sa.Column("deferred_days", _DAYS, server_default="0", nullable=False),
        sa.Column("late_fine_total", _MONEY, server_default="0", nullable=False),
        sa.Column("lifecycle", sa.String(length=10), server_default="OPEN", nullable=False),
        sa.ForeignKeyConstraint(["branch_id"], ["branch.id"]),
        sa.ForeignKeyConstraint(["staff_id"], ["staff.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("staff_id", "year", "month", name="uq_payroll_staff_month_staff_ym"),
    )
    op.create_index(
        "ix_payroll_staff_month_branch_ym",
        "payroll_staff_month",
        ["branch_id", "year", "month"],
    )

    # ── carry_forward_ledger (append-only) ──────────────────────────────────
    op.create_table(
        "carry_forward_ledger",
        *_base_columns(),
        sa.Column("branch_id", sa.Uuid(), nullable=False),
        sa.Column("staff_id", sa.Uuid(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("seq", sa.Integer(), server_default="0", nullable=False),
        sa.Column("entry_type", sa.String(length=30), nullable=False),
        sa.Column("days", _DAYS, nullable=False),
        sa.Column("running_balance", _DAYS, nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["branch_id"], ["branch.id"]),
        sa.ForeignKeyConstraint(["staff_id"], ["staff.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_carry_forward_ledger_staff",
        "carry_forward_ledger",
        ["branch_id", "staff_id", "year", "month"],
    )

    # ── extra_day_requests ──────────────────────────────────────────────────
    op.create_table(
        "extra_day_requests",
        *_base_columns(),
        sa.Column("branch_id", sa.Uuid(), nullable=False),
        sa.Column("staff_id", sa.Uuid(), nullable=False),
        sa.Column("source_year", sa.Integer(), nullable=False),
        sa.Column("source_month", sa.Integer(), nullable=False),
        sa.Column("target_year", sa.Integer(), nullable=False),
        sa.Column("target_month", sa.Integer(), nullable=False),
        sa.Column("shortfall_days", _DAYS, nullable=False),
        sa.Column("request_status", sa.String(length=12), server_default="PENDING", nullable=False),
        sa.Column("requested_by", sa.Uuid(), nullable=False),
        sa.Column("decided_by", sa.Uuid(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["branch_id"], ["branch.id"]),
        sa.ForeignKeyConstraint(["staff_id"], ["staff.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_extra_day_request_active",
        "extra_day_requests",
        ["branch_id", "staff_id", "source_year", "source_month"],
        unique=True,
        postgresql_where=sa.text("is_deleted = false AND request_status IN ('PENDING', 'APPROVED')"),
        sqlite_where=sa.text("is_deleted = 0 AND request_status IN ('PENDING', 'APPROVED')"),
    )

    # ── extra_day_request_history (append-only) ─────────────────────────────
    op.create_table(
        "extra_day_request_history",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("from_status", sa.String(length=12), nullable=True),
        sa.Column("to_status", sa.String(length=12), nullable=False),
        sa.Column("changed_by", sa.Uuid(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("changed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["request_id"], ["extra_day_requests.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_extra_day_request_history_request_id",
        "extra_day_request_history",
        ["request_id"],
    )

    # ── payroll_config (key/value) ──────────────────────────────────────────
    op.create_table(
        "payroll_config",
        sa.Column("key", sa.String(length=50), nullable=False),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )

    # Seed the §8 defaults. The sa.JSON() column type serialises the native
    # Python value on bind for both Postgres and SQLite, so pass it as-is.
    cfg_tbl = sa.table(
        "payroll_config",
        sa.column("key", sa.String()),
        sa.column("value", sa.JSON()),
    )
    bind = op.get_bind()
    op.bulk_insert(
        cfg_tbl,
        [{"key": k, "value": v} for k, v in _CONFIG_DEFAULTS.items()],
    )

    # ── Append-only guard on the ledger (Postgres only) ─────────────────────
    # SQLite (test DB) has no equivalent; the service never issues UPDATE/DELETE
    # on the ledger, and a dedicated test asserts append-only behaviour.
    if bind.dialect.name == "postgresql":
        op.execute(
            """
            CREATE OR REPLACE FUNCTION carry_forward_ledger_append_only()
            RETURNS trigger AS $$
            BEGIN
                RAISE EXCEPTION 'carry_forward_ledger is append-only: % blocked. '
                    'Record a reversal row instead.', TG_OP;
            END;
            $$ LANGUAGE plpgsql;
            """
        )
        op.execute(
            """
            CREATE TRIGGER trg_carry_forward_ledger_no_update
            BEFORE UPDATE OR DELETE ON carry_forward_ledger
            FOR EACH ROW EXECUTE FUNCTION carry_forward_ledger_append_only();
            """
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS trg_carry_forward_ledger_no_update ON carry_forward_ledger;")
        op.execute("DROP FUNCTION IF EXISTS carry_forward_ledger_append_only();")

    op.drop_table("payroll_config")
    op.drop_index("ix_extra_day_request_history_request_id", table_name="extra_day_request_history")
    op.drop_table("extra_day_request_history")
    op.drop_index("uq_extra_day_request_active", table_name="extra_day_requests")
    op.drop_table("extra_day_requests")
    op.drop_index("ix_carry_forward_ledger_staff", table_name="carry_forward_ledger")
    op.drop_table("carry_forward_ledger")
    op.drop_index("ix_payroll_staff_month_branch_ym", table_name="payroll_staff_month")
    op.drop_table("payroll_staff_month")
    op.drop_index("ix_payroll_month_holidays_branch_ym", table_name="payroll_month_holidays")
    op.drop_table("payroll_month_holidays")
    op.drop_index("uq_payroll_month_settings_branch_ym", table_name="payroll_month_settings")
    op.drop_table("payroll_month_settings")
