import uuid

from pydantic import BaseModel


class DepartmentResponse(BaseModel):
    id: uuid.UUID
    branch_id: uuid.UUID
    name: str
    id_range_start: int
    id_range_end: int
    model_config = {"from_attributes": True}


class DepartmentWithAllocation(DepartmentResponse):
    """Department + how full its code range is — powers the roster's
    per-department 'next ID' preview in the create dialog."""

    used: int
    next_emp_code: str | None = None  # None when the range is exhausted


class StaffCreate(BaseModel):
    branch_id: uuid.UUID
    first_name: str
    last_name: str = ""
    title: str | None = None
    department_id: uuid.UUID
    designation: str | None = None
    linked_teacher_id: uuid.UUID | None = None
    email: str | None = None
    phone: str | None = None
    # Optional explicit code. When omitted, the next code in the department's
    # reserved range is allocated. When given out of range, is_legacy_code=true.
    emp_code: str | None = None
    shift_start: str | None = None
    shift_end: str | None = None
    weekly_off_days: str | None = None


class StaffUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    title: str | None = None
    department_id: uuid.UUID | None = None
    designation: str | None = None
    linked_teacher_id: uuid.UUID | None = None
    email: str | None = None
    phone: str | None = None
    emp_code: str | None = None
    shift_start: str | None = None
    shift_end: str | None = None
    weekly_off_days: str | None = None


class StaffResponse(BaseModel):
    id: uuid.UUID
    branch_id: uuid.UUID
    emp_code: str
    title: str | None = None
    first_name: str
    last_name: str
    department_id: uuid.UUID
    department_name: str | None = None
    designation: str | None = None
    linked_teacher_id: uuid.UUID | None = None
    email: str | None = None
    phone: str | None = None
    is_legacy_code: bool
    shift_start: str | None = None
    shift_end: str | None = None
    weekly_off_days: str | None = None
    status: str
    model_config = {"from_attributes": True}


class LinkTeacherRequest(BaseModel):
    # None unlinks.
    teacher_id: uuid.UUID | None = None


class BulkStaffDelete(BaseModel):
    staff_ids: list[uuid.UUID]


class BulkDeleteSummary(BaseModel):
    deleted: int


class ImportSummary(BaseModel):
    imported: int
    skipped: int
    errors: list[str] = []


class StaffDayRegisterRow(BaseModel):
    staff_id: uuid.UUID
    emp_code: str
    name: str
    department: str
    in_time: str | None = None
    out_time: str | None = None
    work_minutes: int = 0
    ot_minutes: int = 0
    status: str
    missed_signoff: bool = False


class ProductivitySummaryRow(BaseModel):
    emp_code: str
    initials: str
    teacher_name: str
    subject: str
    present_days: int
    total_lectures: int
    scheduled_minutes: int
    delivered_minutes: int


class ProductivityChartSlice(BaseModel):
    label: str
    lectures: int


class ProductivitySummaryResponse(BaseModel):
    start: str
    end: str
    rows: list[ProductivitySummaryRow]
    by_subject: list[ProductivityChartSlice]
    by_teacher: list[ProductivityChartSlice]
