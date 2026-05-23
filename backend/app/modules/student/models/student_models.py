import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.base import BaseModel


class Student(BaseModel):
    __tablename__ = "students"

    branch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("branch.id"), nullable=False
    )
    academic_year_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("academic_years.id"), nullable=False
    )
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    enrollment_number: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )
    parent_mobile: Mapped[str | None] = mapped_column(String(20), nullable=True)
    rfid_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    gender: Mapped[str | None] = mapped_column(String(10), nullable=True)
    district: Mapped[str | None] = mapped_column(String(100), nullable=True)
    caste: Mapped[str | None] = mapped_column(String(100), nullable=True)
    username: Mapped[str | None] = mapped_column(String(100), nullable=True)
    course_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("courses.id"), nullable=True
    )
    # Standard / class level the student is in.
    # Allowed: "9" | "10" | "11" | "12" | "Dropper"
    standard: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # Target exam track.
    # Allowed: NEET | JEE-Main | JEE-Advanced | Both | Foundation | Other
    target_exam: Mapped[str | None] = mapped_column(String(40), nullable=True)


class StudentIdentity(BaseModel):
    __tablename__ = "student_identities"

    student_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("students.id"), nullable=False
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("branch.id"), nullable=False
    )
    identity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    identity_value: Mapped[str] = mapped_column(String(255), nullable=False)


class Parent(BaseModel):
    __tablename__ = "parents"

    student_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("students.id"), nullable=False
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("branch.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    relation: Mapped[str] = mapped_column(String(50), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    occupation: Mapped[str | None] = mapped_column(String(100), nullable=True)


class StudentBatchMapping(BaseModel):
    __tablename__ = "student_batch_mappings"

    student_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("students.id"), nullable=False
    )
    batch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("batches.id"), nullable=False
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("branch.id"), nullable=False
    )
