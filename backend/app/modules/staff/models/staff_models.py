import uuid

from sqlalchemy import ForeignKey, Index, Integer, String, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.base import BaseModel

# Canonical departments + reserved emp-code ranges (client-confirmed for Matrix
# Science Academy). Seeded per branch by migration 0056 and lazily for any
# branch that has none yet (staff_service.ensure_departments). (name, start, end)
DEPARTMENT_SEED: list[tuple[str, int, int]] = [
    ("MSA-Teachers", 1, 50),
    ("MSA-Administration", 51, 70),
    ("MSA-Accounts", 71, 80),
    ("Security", 81, 90),
    ("Cleaning Unit", 91, 100),
    ("MSA-Marketing", 101, 110),
]


class Department(BaseModel):
    """A staff department with a reserved employee-code range.

    Six are seeded for Matrix Science Academy (see migration 0056). Each staff
    member's ``emp_code`` is allocated from its department's
    ``[id_range_start, id_range_end]`` window so codes stay predictable and
    non-overlapping as more staff are added. Legacy codes (imported from the
    client's old sequential scheme) may fall outside the range — those rows
    carry ``Staff.is_legacy_code = true``.
    """

    __tablename__ = "departments"
    __table_args__ = (
        # One live department per name per branch.
        Index(
            "uq_departments_branch_name",
            "branch_id",
            "name",
            unique=True,
            postgresql_where=text("is_deleted = false"),
            sqlite_where=text("is_deleted = 0"),
        ),
    )

    branch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("branch.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    id_range_start: Mapped[int] = mapped_column(Integer, nullable=False)
    id_range_end: Mapped[int] = mapped_column(Integer, nullable=False)


class Staff(BaseModel):
    """A staff member — teaching or non-teaching — as the subject of staff
    attendance.

    ``emp_code`` is the device userId the biometric terminals report; it is
    matched against a punch's vendor id exactly the way ``Student.rfid_number``
    is, so enrolling a staff finger = setting this code on the device. Teaching
    staff link to their existing ``teachers`` row via ``linked_teacher_id`` so
    the Faculty Activity Report can join lectures delivered.
    """

    __tablename__ = "staff"
    __table_args__ = (
        # One live staff row per emp_code per branch (device userId is unique).
        Index(
            "uq_staff_branch_empcode",
            "branch_id",
            "emp_code",
            unique=True,
            postgresql_where=text("is_deleted = false"),
            sqlite_where=text("is_deleted = 0"),
        ),
    )

    branch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("branch.id"), nullable=False
    )
    # Device userId / employee code. Kept as a string so zero-padded legacy
    # codes ("0001") survive round-trips; allocation for new joiners is numeric.
    emp_code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    title: Mapped[str | None] = mapped_column(String(10), nullable=True)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    department_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("departments.id"), nullable=False
    )
    designation: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Set for teaching staff so lectures (teacher_id / actual_teacher_id) can be
    # joined to this person's attendance for the Faculty Activity Report.
    linked_teacher_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("teachers.id"), nullable=True
    )
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # True when emp_code falls outside its department's reserved range — the
    # legacy sequential codes imported from the client's old system.
    is_legacy_code: Mapped[bool] = mapped_column(
        nullable=False, server_default="false", default=False
    )
    # Per-staff shift, "HH:MM" local (mirrors Batch.class_start_time). NULL falls
    # back to the branch defaults. Drives Late-IN / Early-OUT / OT / Half-Day.
    shift_start: Mapped[str | None] = mapped_column(String(5), nullable=True)
    shift_end: Mapped[str | None] = mapped_column(String(5), nullable=True)
    # CSV of Python weekday ints that are weekly-offs (Mon=0 … Sun=6), e.g. "6".
    weekly_off_days: Mapped[str | None] = mapped_column(String(20), nullable=True)
