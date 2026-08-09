"""BioMax biometric backup — encrypted face/photo/fingerprint templates.

A branch-isolated table holding each enrolled user's biometric templates,
captured in real time from the device's ``realtime_enroll_data`` push and stored
Fernet-encrypted (key in the env only), so a lost/reset terminal can be restored
without re-enrolling every student. Dormant unless ``BIOMAX_BIOMETRIC_KEY`` is
set (with no key the receiver drops the blobs as before); this only creates the
table.

Revision ID: 0049
Revises: 0048
Create Date: 2026-08-09
"""

from alembic import op
import sqlalchemy as sa


revision = "0049"
down_revision = "0048"
branch_labels = None
depends_on = None


def _base_columns() -> list:
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
        "device_user_biometrics",
        *_base_columns(),
        sa.Column("branch_id", sa.Uuid(), nullable=False),
        sa.Column("dev_id", sa.String(length=100), nullable=False),
        sa.Column("vendor_user_id", sa.String(length=64), nullable=False),
        sa.Column("student_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(length=64), nullable=True),
        sa.Column("face_enc", sa.LargeBinary(), nullable=True),
        sa.Column("photo_enc", sa.LargeBinary(), nullable=True),
        sa.Column("fps_enc", sa.LargeBinary(), nullable=True),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["branch_id"], ["branch.id"]),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dev_id", "vendor_user_id", name="uq_device_biometrics_dev_user"),
    )
    op.create_index(
        "ix_device_user_biometrics_branch_id", "device_user_biometrics", ["branch_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_device_user_biometrics_branch_id", table_name="device_user_biometrics")
    op.drop_table("device_user_biometrics")
