"""weekend plan + star-system foundations

Revision ID: 0075
Revises: 0074
Create Date: 2026-11-23

Reconciles the live senior-initiated weekend_work flow with the SRD's
teacher-initiated Weekend Plan, and adds the Teacher Star-System self-assessment,
the shared approver mapping / decision log, and the in-app notification inbox.

- Evolves ``weekend_work`` in place with the Weekend Plan fields (existing rows
  backfill to origin=SENIOR_PREAPPROVED via the column default, so the Point-5
  flow is unchanged).
- Adds: weekend_plan_items, approver_mappings, approver_logs,
  portal_notifications, assessment_categories, assessment_item_master,
  self_assessments, self_assessment_items, self_assessment_stars.

Structural only; default Star-System categories/items are seeded idempotently
per branch by the service (catalog.DEFAULT_CATALOG). Reversible.
"""

from alembic import op
import sqlalchemy as sa

revision = "0075"
down_revision = "0074"
branch_labels = None
depends_on = None


def _base_cols() -> list[sa.Column]:
    """The standard BaseModel columns (db_conventions.md)."""
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
    # ── 1. Evolve weekend_work in place ──────────────────────────────────────
    op.add_column("weekend_work", sa.Column(
        "origin", sa.String(length=20), server_default="SENIOR_PREAPPROVED", nullable=False))
    op.add_column("weekend_work", sa.Column("day_type", sa.String(length=10), nullable=True))
    op.add_column("weekend_work", sa.Column("holiday_name", sa.String(length=255), nullable=True))
    op.add_column("weekend_work", sa.Column("approver_id", sa.Uuid(), nullable=True))
    op.add_column("weekend_work", sa.Column(
        "total_planned_minutes", sa.Integer(), server_default="0", nullable=False))
    op.add_column("weekend_work", sa.Column("remarks", sa.String(length=500), nullable=True))
    op.add_column("weekend_work", sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_weekend_work_origin", "weekend_work", ["origin"])

    # ── 2. weekend_plan_items ────────────────────────────────────────────────
    op.create_table(
        "weekend_plan_items",
        *_base_cols(),
        sa.Column("weekend_work_id", sa.Uuid(), nullable=False),
        sa.Column("work_type", sa.String(length=40), nullable=False),
        sa.Column("batch_id", sa.Uuid(), nullable=True),
        sa.Column("task_description", sa.String(length=500), nullable=False),
        sa.Column("start_time", sa.String(length=5), nullable=False),
        sa.Column("end_time", sa.String(length=5), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("branch_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["weekend_work_id"], ["weekend_work.id"]),
        sa.ForeignKeyConstraint(["batch_id"], ["batches.id"]),
        sa.ForeignKeyConstraint(["branch_id"], ["branch.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_weekend_plan_items_work", "weekend_plan_items", ["weekend_work_id"])

    # ── 3. approver_mappings ─────────────────────────────────────────────────
    op.create_table(
        "approver_mappings",
        *_base_cols(),
        sa.Column("branch_id", sa.Uuid(), nullable=False),
        sa.Column("staff_id", sa.Uuid(), nullable=False),
        sa.Column("approver_user_id", sa.Uuid(), nullable=False),
        sa.Column("is_default", sa.Boolean(), server_default="true", nullable=False),
        sa.ForeignKeyConstraint(["branch_id"], ["branch.id"]),
        sa.ForeignKeyConstraint(["staff_id"], ["staff.id"]),
        sa.ForeignKeyConstraint(["approver_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_approver_mappings_staff", "approver_mappings", ["staff_id"])
    op.create_index(
        "uq_approver_mapping_active", "approver_mappings",
        ["branch_id", "staff_id", "approver_user_id"], unique=True,
        postgresql_where=sa.text("is_deleted = false"),
        sqlite_where=sa.text("is_deleted = 0"),
    )

    # ── 4. approver_logs ─────────────────────────────────────────────────────
    op.create_table(
        "approver_logs",
        *_base_cols(),
        sa.Column("branch_id", sa.Uuid(), nullable=False),
        sa.Column("record_type", sa.String(length=20), nullable=False),
        sa.Column("record_id", sa.Uuid(), nullable=False),
        sa.Column("approver_user_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["branch_id"], ["branch.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_approver_logs_record", "approver_logs", ["record_type", "record_id"])
    op.create_index("ix_approver_logs_branch", "approver_logs", ["branch_id", "created_at"])

    # ── 5. portal_notifications ──────────────────────────────────────────────
    op.create_table(
        "portal_notifications",
        *_base_cols(),
        sa.Column("branch_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("record_type", sa.String(length=20), nullable=True),
        sa.Column("record_id", sa.Uuid(), nullable=True),
        sa.Column("message", sa.String(length=500), nullable=False),
        sa.Column("is_read", sa.Boolean(), server_default="false", nullable=False),
        sa.ForeignKeyConstraint(["branch_id"], ["branch.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_portal_notifications_user", "portal_notifications",
        ["user_id", "is_read", "created_at"])

    # ── 6. assessment_categories ─────────────────────────────────────────────
    op.create_table(
        "assessment_categories",
        *_base_cols(),
        sa.Column("branch_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("is_deduction", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("active", sa.Boolean(), server_default="true", nullable=False),
        sa.ForeignKeyConstraint(["branch_id"], ["branch.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_assessment_categories_branch", "assessment_categories",
        ["branch_id", "sort_order"])

    # ── 7. assessment_item_master ────────────────────────────────────────────
    op.create_table(
        "assessment_item_master",
        *_base_cols(),
        sa.Column("branch_id", sa.Uuid(), nullable=False),
        sa.Column("category_id", sa.Uuid(), nullable=False),
        sa.Column("item_name", sa.String(length=80), nullable=False),
        sa.Column("input_type", sa.String(length=20), nullable=False),
        sa.Column("options", sa.JSON(), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("active", sa.Boolean(), server_default="true", nullable=False),
        sa.ForeignKeyConstraint(["branch_id"], ["branch.id"]),
        sa.ForeignKeyConstraint(["category_id"], ["assessment_categories.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_assessment_item_master_cat", "assessment_item_master",
        ["category_id", "sort_order"])

    # ── 8. self_assessments ──────────────────────────────────────────────────
    op.create_table(
        "self_assessments",
        *_base_cols(),
        sa.Column("branch_id", sa.Uuid(), nullable=False),
        sa.Column("staff_id", sa.Uuid(), nullable=False),
        sa.Column("assess_date", sa.Date(), nullable=False),
        sa.Column("miscellaneous_text", sa.String(length=300), nullable=True),
        sa.Column("final_total_star", sa.Numeric(4, 1), server_default="0", nullable=False),
        sa.Column("status_code", sa.String(length=20), server_default="DRAFT", nullable=False),
        sa.Column("approver_id", sa.Uuid(), nullable=True),
        sa.Column("approved_by", sa.Uuid(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("latest_approver_comment", sa.Text(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["branch_id"], ["branch.id"]),
        sa.ForeignKeyConstraint(["staff_id"], ["staff.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_self_assessments_staff", "self_assessments", ["staff_id"])
    op.create_index("ix_self_assessments_date", "self_assessments", ["assess_date"])
    op.create_index(
        "ix_self_assessments_status", "self_assessments", ["branch_id", "status_code"])
    op.create_index(
        "uq_self_assessment_active", "self_assessments",
        ["branch_id", "staff_id", "assess_date"], unique=True,
        postgresql_where=sa.text("is_deleted = false"),
        sqlite_where=sa.text("is_deleted = 0"),
    )

    # ── 9. self_assessment_items ─────────────────────────────────────────────
    op.create_table(
        "self_assessment_items",
        *_base_cols(),
        sa.Column("branch_id", sa.Uuid(), nullable=False),
        sa.Column("self_assessment_id", sa.Uuid(), nullable=False),
        sa.Column("item_master_id", sa.Uuid(), nullable=False),
        sa.Column("selected_value", sa.String(length=40), nullable=False),
        sa.ForeignKeyConstraint(["branch_id"], ["branch.id"]),
        sa.ForeignKeyConstraint(["self_assessment_id"], ["self_assessments.id"]),
        sa.ForeignKeyConstraint(["item_master_id"], ["assessment_item_master.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_self_assessment_items_assess", "self_assessment_items", ["self_assessment_id"])

    # ── 10. self_assessment_stars ────────────────────────────────────────────
    op.create_table(
        "self_assessment_stars",
        *_base_cols(),
        sa.Column("branch_id", sa.Uuid(), nullable=False),
        sa.Column("self_assessment_id", sa.Uuid(), nullable=False),
        sa.Column("category_id", sa.Uuid(), nullable=False),
        sa.Column("stars", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["branch_id"], ["branch.id"]),
        sa.ForeignKeyConstraint(["self_assessment_id"], ["self_assessments.id"]),
        sa.ForeignKeyConstraint(["category_id"], ["assessment_categories.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_self_assessment_stars_assess", "self_assessment_stars", ["self_assessment_id"])


def downgrade() -> None:
    op.drop_table("self_assessment_stars")
    op.drop_table("self_assessment_items")
    op.drop_table("self_assessments")
    op.drop_table("assessment_item_master")
    op.drop_table("assessment_categories")
    op.drop_table("portal_notifications")
    op.drop_table("approver_logs")
    op.drop_table("approver_mappings")
    op.drop_table("weekend_plan_items")

    op.drop_index("ix_weekend_work_origin", table_name="weekend_work")
    for col in (
        "submitted_at", "remarks", "total_planned_minutes", "approver_id",
        "holiday_name", "day_type", "origin",
    ):
        op.drop_column("weekend_work", col)
