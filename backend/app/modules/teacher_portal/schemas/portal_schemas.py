import uuid

from pydantic import BaseModel


class TeacherProfile(BaseModel):
    name: str
    employee_code: str
    department: str | None = None


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
