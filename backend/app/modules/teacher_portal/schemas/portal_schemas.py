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


# ── Weekend work (Point 5) ───────────────────────────────────────────────────


class WeekendPreapprove(BaseModel):
    """Step 1 — pre-approve a weekend date for a set of staff."""

    work_date: date
    staff_ids: list[uuid.UUID]


class WeekendWorkContent(BaseModel):
    """Step 2 — the teacher's work content for the day."""

    content: str


class WeekendDecision(BaseModel):
    """Step 3 — approve/reject with an optional note (e.g. 'Approved by Ravi Sir')."""

    note: str | None = None


class WeekendAbsentOverride(BaseModel):
    """Management override (Rule 5) — force the day ABSENT (or clear it)."""

    absent: bool = True


# ── Weekend Plan (teacher-initiated, Weekend & Star-System SRD §5.1) ──────────

# SRD WP03 work types.
WEEKEND_WORK_TYPES = frozenset(
    {"Lecture", "Test Checking", "Doubt Solving", "Paper Setting", "Counselling", "Other"}
)


class WeekendPlanItemIn(BaseModel):
    """One work-breakdown line (WP03). Times are 15-minute-step dropdown values."""

    work_type: str
    batch_id: uuid.UUID | None = None
    task_description: str
    start_time: str
    end_time: str

    @field_validator("work_type")
    @classmethod
    def _work_type_known(cls, v: str) -> str:
        if v not in WEEKEND_WORK_TYPES:
            raise ValueError(f"work_type must be one of {sorted(WEEKEND_WORK_TYPES)}")
        return v

    @field_validator("task_description")
    @classmethod
    def _task_nonempty(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("task_description is required")
        return v


class WeekendPlanWrite(BaseModel):
    """Create or fully replace a teacher's Weekend Plan (draft or resubmit body).

    ``plan_date`` must be a Saturday, Sunday or academy holiday (BR-02, validated
    server-side). ``approver_id`` is optional — the system auto-assigns from the
    approver mapping when omitted (WP05)."""

    plan_date: date
    approver_id: uuid.UUID | None = None
    remarks: str | None = None
    items: list[WeekendPlanItemIn] = []

    @field_validator("items")
    @classmethod
    def _at_least_one_item_to_submit(cls, v: list[WeekendPlanItemIn]) -> list[WeekendPlanItemIn]:
        # A draft may have zero items; the submit path enforces >= 1 separately.
        return v


# ── Approver decisions (SRD §5.3) ────────────────────────────────────────────


class ApprovalDecision(BaseModel):
    """Approve / Reject / Mark ABSENT with a mandatory comment (AP03/AP04).

    The 10-char minimum is enforced server-side in the service so the rule holds
    for the API, not just the UI (the confirm button is also disabled client-side)."""

    action: str  # APPROVE | REJECT | MARK_ABSENT
    comment: str


# ── Teacher Star System: daily self-assessment (SRD §5.2) ────────────────────


class SelfAssessmentItemIn(BaseModel):
    """The option selected for one assessment item."""

    item_master_id: uuid.UUID
    selected_value: str


class SelfAssessmentStarIn(BaseModel):
    """A 1–5 star rating for one of the four main categories."""

    category_id: uuid.UUID
    stars: int


class SelfAssessmentWrite(BaseModel):
    """Save (draft) or submit a daily self-assessment. ``items`` are dropdown
    selections; ``stars`` are the per-category ratings; Miscellaneous is the only
    free text (SA-02). The Final Total Star is computed server-side (SA-05)."""

    assess_date: date
    approver_id: uuid.UUID | None = None
    miscellaneous_text: str | None = None
    items: list[SelfAssessmentItemIn] = []
    stars: list[SelfAssessmentStarIn] = []

    @field_validator("miscellaneous_text")
    @classmethod
    def _misc_len(cls, v: str | None) -> str | None:
        if v is not None and len(v) > 300:
            raise ValueError("Miscellaneous must be at most 300 characters.")
        return v
