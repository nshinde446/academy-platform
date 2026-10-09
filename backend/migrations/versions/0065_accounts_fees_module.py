"""Accounts / Fees module — course fee config, fee profiles, installments, payments, remarks

Revision ID: 0065
Revises: 0064
Create Date: 2026-10-09

Five tables for the Accounts / Fees module (spec Section 10): per-course standard
fees, a per-student fee profile created at admission, its installment schedule,
the payments received, and the call-log remarks.
"""

from alembic import op
import sqlalchemy as sa

revision = "0065"
down_revision = "0064"
branch_labels = None
depends_on = None


def _base_cols() -> list:
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
    op.create_table(
        "course_fee_configs",
        *_base_cols(),
        sa.Column("course_name", sa.String(length=50), nullable=False),
        sa.Column("standard_fee", sa.Float(), nullable=False),
        sa.Column("branch_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["branch_id"], ["branch.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_course_fee_branch", "course_fee_configs", ["branch_id", "course_name"],
        unique=True,
        postgresql_where=sa.text("is_deleted = false"),
        sqlite_where=sa.text("is_deleted = 0"),
    )

    op.create_table(
        "student_fee_profiles",
        *_base_cols(),
        sa.Column("student_id", sa.Uuid(), nullable=False),
        sa.Column("branch_id", sa.Uuid(), nullable=False),
        sa.Column("batch_id", sa.Uuid(), nullable=False),
        sa.Column("actual_fee", sa.Float(), nullable=False),
        sa.Column("agreed_fee", sa.Float(), nullable=False),
        sa.Column("discount_amount", sa.Float(), nullable=False),
        sa.Column("payment_mode", sa.String(length=20), nullable=False),
        sa.Column("total_paid", sa.Float(), nullable=False),
        sa.Column("total_pending", sa.Float(), nullable=False),
        sa.Column("admission_date", sa.Date(), nullable=False),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"]),
        sa.ForeignKeyConstraint(["branch_id"], ["branch.id"]),
        sa.ForeignKeyConstraint(["batch_id"], ["batches.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_fee_profile_student", "student_fee_profiles", ["student_id"],
        unique=True,
        postgresql_where=sa.text("is_deleted = false"),
        sqlite_where=sa.text("is_deleted = 0"),
    )

    op.create_table(
        "fee_installments",
        *_base_cols(),
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("student_id", sa.Uuid(), nullable=False),
        sa.Column("branch_id", sa.Uuid(), nullable=False),
        sa.Column("installment_number", sa.Integer(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("installment_status", sa.String(length=20), server_default="PENDING", nullable=False),
        sa.Column("paid_amount", sa.Float(), nullable=False, server_default="0"),
        sa.Column("paid_date", sa.Date(), nullable=True),
        sa.Column("payment_mode", sa.String(length=20), nullable=True),
        sa.ForeignKeyConstraint(["profile_id"], ["student_fee_profiles.id"]),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"]),
        sa.ForeignKeyConstraint(["branch_id"], ["branch.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_fee_installments_profile", "fee_installments", ["profile_id"])
    op.create_index("ix_fee_installments_due_date", "fee_installments", ["due_date"])

    op.create_table(
        "fee_payment_records",
        *_base_cols(),
        sa.Column("student_id", sa.Uuid(), nullable=False),
        sa.Column("installment_id", sa.Uuid(), nullable=False),
        sa.Column("branch_id", sa.Uuid(), nullable=False),
        sa.Column("amount_paid", sa.Float(), nullable=False),
        sa.Column("payment_date", sa.Date(), nullable=False),
        sa.Column("payment_mode", sa.String(length=20), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"]),
        sa.ForeignKeyConstraint(["installment_id"], ["fee_installments.id"]),
        sa.ForeignKeyConstraint(["branch_id"], ["branch.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_fee_payments_installment", "fee_payment_records", ["installment_id"])

    op.create_table(
        "fee_remarks",
        *_base_cols(),
        sa.Column("student_id", sa.Uuid(), nullable=False),
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("branch_id", sa.Uuid(), nullable=False),
        sa.Column("remark_text", sa.Text(), nullable=False),
        sa.Column("call_date", sa.Date(), nullable=False),
        sa.Column("next_followup_date", sa.Date(), nullable=True),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"]),
        sa.ForeignKeyConstraint(["profile_id"], ["student_fee_profiles.id"]),
        sa.ForeignKeyConstraint(["branch_id"], ["branch.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_fee_remarks_followup", "fee_remarks", ["next_followup_date"])


def downgrade() -> None:
    op.drop_index("ix_fee_remarks_followup", table_name="fee_remarks")
    op.drop_table("fee_remarks")
    op.drop_index("ix_fee_payments_installment", table_name="fee_payment_records")
    op.drop_table("fee_payment_records")
    op.drop_index("ix_fee_installments_due_date", table_name="fee_installments")
    op.drop_index("ix_fee_installments_profile", table_name="fee_installments")
    op.drop_table("fee_installments")
    op.drop_index("uq_fee_profile_student", table_name="student_fee_profiles")
    op.drop_table("student_fee_profiles")
    op.drop_index("uq_course_fee_branch", table_name="course_fee_configs")
    op.drop_table("course_fee_configs")
