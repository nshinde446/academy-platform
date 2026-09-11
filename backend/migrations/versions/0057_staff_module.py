"""Staff module — departments + staff roster with per-department ID ranges

Adds the staff domain that mirrors students as a first-class attendance subject:

* ``departments`` — six client-confirmed departments, each with a reserved
  emp-code range, seeded per existing branch.
* ``staff`` — teaching + non-teaching staff. ``emp_code`` is the device userId
  (matched against punches like ``Student.rfid_number``); ``linked_teacher_id``
  ties teaching staff to their ``teachers`` row for the Faculty Activity Report.

Both carry a partial-unique index (branch + name / branch + emp_code) scoped to
live rows — PG-only behaviour, exercised against real Postgres in CI.

Revision ID: 0057
Revises: 0055
Create Date: 2026-09-11
"""

from alembic import op
import sqlalchemy as sa


revision = "0057"
down_revision = "0055"
branch_labels = None
depends_on = None


DEPARTMENT_SEED = [
    ("MSA-Teachers", 1, 50),
    ("MSA-Administration", 51, 70),
    ("MSA-Accounts", 71, 80),
    ("Security", 81, 90),
    ("Cleaning Unit", 91, 100),
    ("MSA-Marketing", 101, 110),
]


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
        "departments",
        *_base_columns(),
        sa.Column("branch_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("id_range_start", sa.Integer(), nullable=False),
        sa.Column("id_range_end", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["branch_id"], ["branch.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_departments_branch_name",
        "departments",
        ["branch_id", "name"],
        unique=True,
        postgresql_where=sa.text("is_deleted = false"),
        sqlite_where=sa.text("is_deleted = 0"),
    )

    op.create_table(
        "staff",
        *_base_columns(),
        sa.Column("branch_id", sa.Uuid(), nullable=False),
        sa.Column("emp_code", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=10), nullable=True),
        sa.Column("first_name", sa.String(length=100), nullable=False),
        sa.Column("last_name", sa.String(length=100), nullable=False, server_default=""),
        sa.Column("department_id", sa.Uuid(), nullable=False),
        sa.Column("designation", sa.String(length=100), nullable=True),
        sa.Column("linked_teacher_id", sa.Uuid(), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=20), nullable=True),
        sa.Column("is_legacy_code", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("shift_start", sa.String(length=5), nullable=True),
        sa.Column("shift_end", sa.String(length=5), nullable=True),
        sa.Column("weekly_off_days", sa.String(length=20), nullable=True),
        sa.ForeignKeyConstraint(["branch_id"], ["branch.id"]),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"]),
        sa.ForeignKeyConstraint(["linked_teacher_id"], ["teachers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_staff_emp_code", "staff", ["emp_code"])
    op.create_index(
        "uq_staff_branch_empcode",
        "staff",
        ["branch_id", "emp_code"],
        unique=True,
        postgresql_where=sa.text("is_deleted = false"),
        sqlite_where=sa.text("is_deleted = 0"),
    )

    # Seed the six departments for every branch present at upgrade time. New
    # branches are seeded lazily (staff_service.ensure_departments).
    conn = op.get_bind()
    branch_ids = [r[0] for r in conn.execute(sa.text("SELECT id FROM branch")).fetchall()]
    if branch_ids:
        dept_tbl = sa.table(
            "departments",
            sa.column("id", sa.Uuid()),
            sa.column("branch_id", sa.Uuid()),
            sa.column("name", sa.String()),
            sa.column("id_range_start", sa.Integer()),
            sa.column("id_range_end", sa.Integer()),
            sa.column("status", sa.String()),
            sa.column("is_deleted", sa.Boolean()),
        )
        import uuid as _uuid

        rows = [
            {
                "id": _uuid.uuid4(),
                "branch_id": bid,
                "name": name,
                "id_range_start": start,
                "id_range_end": end,
                "status": "active",
                "is_deleted": False,
            }
            for bid in branch_ids
            for (name, start, end) in DEPARTMENT_SEED
        ]
        op.bulk_insert(dept_tbl, rows)


def downgrade() -> None:
    op.drop_index("uq_staff_branch_empcode", table_name="staff")
    op.drop_index("ix_staff_emp_code", table_name="staff")
    op.drop_table("staff")
    op.drop_index("uq_departments_branch_name", table_name="departments")
    op.drop_table("departments")
