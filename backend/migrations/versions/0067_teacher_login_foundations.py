"""teacher_login_foundations — accounts, auth events, portal config

Revision ID: 0067
Revises: 0066
Create Date: 2026-10-25

Additive foundations for the Teacher Login module (read-only teacher portal).

- `users`: add the account-lifecycle columns a teacher login needs — a
  username (employee code, unique case-insensitively), a link to the staff
  record the portal reads data for, the forced-first-change flag, and the
  lockout / last-login bookkeeping. All nullable / defaulted so existing
  email-login users are unaffected (``must_change_password`` defaults false;
  the existing ``status`` column already carries active/inactive).
- `auth_events`: append-only login/account activity log (separate from the
  business audit log).
- `teacher_portal_config`: key/value settings seeded with the spec defaults so
  they can change without a deploy.

Additive only — no existing column is altered or dropped.
"""

import uuid

from alembic import op
import sqlalchemy as sa

revision = "0067"
down_revision = "0066"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── users: account-lifecycle columns (all additive) ─────────────────────
    op.add_column("users", sa.Column("username", sa.String(length=50), nullable=True))
    op.add_column("users", sa.Column("staff_id", sa.Uuid(), nullable=True))
    op.add_column(
        "users",
        sa.Column(
            "must_change_password", sa.Boolean(), server_default="false", nullable=False
        ),
    )
    op.add_column(
        "users",
        sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("failed_attempts", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "users", sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "users", sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_foreign_key(
        "fk_users_staff_id", "users", "staff", ["staff_id"], ["id"]
    )
    # Username unique case-insensitively (teacher username = employee code); one
    # user per staff record. Partial so the many NULLs (email-login users) don't
    # collide.
    op.create_index(
        "uq_users_username_lower",
        "users",
        [sa.text("lower(username)")],
        unique=True,
        postgresql_where=sa.text("username IS NOT NULL"),
    )
    op.create_index(
        "uq_users_staff_id",
        "users",
        ["staff_id"],
        unique=True,
        postgresql_where=sa.text("staff_id IS NOT NULL"),
    )

    # ── auth_events: append-only login / account activity ───────────────────
    op.create_table(
        "auth_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("username_attempted", sa.String(length=50), nullable=True),
        sa.Column("event", sa.String(length=40), nullable=False),
        sa.Column("ip", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=400), nullable=True),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("detail", sa.String(length=500), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_auth_events_user_created", "auth_events", ["user_id", "created_at"])
    op.create_index("ix_auth_events_event_created", "auth_events", ["event", "created_at"])

    # ── teacher_portal_config: key/value settings, seeded ───────────────────
    op.create_table(
        "teacher_portal_config",
        sa.Column("key", sa.String(length=50), nullable=False),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("key"),
    )
    cfg = sa.table(
        "teacher_portal_config",
        sa.column("key", sa.String()),
        sa.column("value", sa.JSON()),
    )
    op.bulk_insert(
        cfg,
        [
            {"key": "fine_visibility", "value": "after_day_close"},  # or "realtime"
            {"key": "day_close_time", "value": "23:30"},             # institute-local HH:MM
            {"key": "history_days", "value": 90},
            {"key": "idle_timeout_minutes", "value": 30},
            {"key": "max_session_hours", "value": 8},
            {"key": "lockout_attempts", "value": 5},
            {"key": "lockout_minutes", "value": 15},
            {"key": "min_password_length", "value": 8},
            {"key": "teacher_login_enabled", "value": False},        # feature flag, default off
        ],
    )


def downgrade() -> None:
    op.drop_table("teacher_portal_config")
    op.drop_index("ix_auth_events_event_created", table_name="auth_events")
    op.drop_index("ix_auth_events_user_created", table_name="auth_events")
    op.drop_table("auth_events")
    op.drop_index("uq_users_staff_id", table_name="users")
    op.drop_index("uq_users_username_lower", table_name="users")
    op.drop_constraint("fk_users_staff_id", "users", type_="foreignkey")
    op.drop_column("users", "last_login_at")
    op.drop_column("users", "locked_until")
    op.drop_column("users", "failed_attempts")
    op.drop_column("users", "password_changed_at")
    op.drop_column("users", "must_change_password")
    op.drop_column("users", "staff_id")
    op.drop_column("users", "username")
