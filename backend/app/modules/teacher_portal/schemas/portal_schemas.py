import uuid
from datetime import date

from pydantic import BaseModel, EmailStr, field_validator


class TeacherProfile(BaseModel):
    name: str
    employee_code: str
    department: str | None = None
    # Read-only employment details (admin-managed; shown but never self-edited).
    title: str | None = None
    designation: str | None = None
    shift_start: str | None = None
    shift_end: str | None = None
    # Self-editable contact details.
    phone: str | None = None
    email: str | None = None


class ProfileContactUpdate(BaseModel):
    """The ONLY fields a teacher may change about themselves — contact details.
    Identity/employment (name, employee code, department, shift) stay admin-only.
    Both optional so the client can patch one field; at least one is required."""

    phone: str | None = None
    email: EmailStr | None = None

    @field_validator("phone")
    @classmethod
    def _phone_len(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if v and not (6 <= len(v) <= 20):
            raise ValueError("phone must be 6–20 characters")
        return v or None


class DayAttendance(BaseModel):
    in_: str | None = None
    out: str | None = None
    status: str

    model_config = {"populate_by_name": True}


class DayLecture(BaseModel):
    batch: str
    subject: str
    scheduled_start: str | None = None
    scheduled_end: str | None = None
    actual_start: str | None = None
    actual_end: str | None = None
    status: str


class DayFine(BaseModel):
    amount: float | None = None
    visible: bool


class DayResponse(BaseModel):
    date: str
    attendance: dict
    first_lecture_start: str | None = None
    late_minutes: int | None = None
    fine: DayFine
    lectures: list[DayLecture]


class MonthSummary(BaseModel):
    year: int
    month: int
    present_days: int
    half_days: int
    absent_days: int
    late_count: int
    total_late_minutes: int
    total_fine: float


class TeacherSession(BaseModel):
    user_id: uuid.UUID
    staff_id: uuid.UUID
    branch_id: uuid.UUID | None = None


class LeaveApply(BaseModel):
    """A teacher's leave request. Dates inclusive; reason optional."""

    start_date: date
    end_date: date
    leave_type: str = "casual"
    half_day: bool = False
    reason: str | None = None


class LeaveDecision(BaseModel):
    """Admin approve/reject note (optional)."""

    note: str | None = None
