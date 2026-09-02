import uuid
from datetime import date, datetime

from pydantic import BaseModel


class LectureCreate(BaseModel):
    teacher_id: uuid.UUID
    batch_id: uuid.UUID
    classroom_id: uuid.UUID | None = None
    subject_id: uuid.UUID
    topic_id: uuid.UUID | None = None
    scheduled_start: datetime
    scheduled_end: datetime
    delivery_mode: str = "offline"
    notes: str | None = None


class ImportScheduleSummary(BaseModel):
    imported: int
    skipped: int
    errors: list[str] = []


class ImportPreviewRow(BaseModel):
    """One row's dry-run validation result for the schedule importer."""

    row_number: int
    date: str
    start_time: str
    end_time: str
    teacher: str
    batch: str
    subject: str
    status: str  # "ok" | "error"
    message: str


class ImportSchedulePreview(BaseModel):
    rows: list[ImportPreviewRow] = []
    ok_count: int
    error_count: int


class LectureUpdate(BaseModel):
    topic_id: uuid.UUID | None = None
    notes: str | None = None


class LectureActuals(BaseModel):
    """End-of-day actuals entry (PDF §3): admin backfills what actually
    happened. Setting actual_end marks the lecture completed; late_flag and
    actual_duration_min are derived server-side. Any field omitted is left
    unchanged (topic_id can be cleared via the dedicated update path)."""

    actual_start: datetime | None = None
    actual_end: datetime | None = None
    topic_id: uuid.UUID | None = None
    notes: str | None = None


class CopyScheduleSummary(BaseModel):
    """Result of copying a day's lecture plan to another date."""

    source_date: str
    target_date: str
    copied: int
    skipped: int
    errors: list[str] = []


class CopySelectedRequest(BaseModel):
    """Copy a hand-picked set of lectures (not a whole date) onto target_date."""

    lecture_ids: list[uuid.UUID]
    target_date: date


class CopySelectedSummary(BaseModel):
    target_date: str
    copied: int
    skipped: int
    errors: list[str] = []


class TimetableSlot(BaseModel):
    """One recurring weekly class in a batch's timetable.

    day_of_week follows Python's date.weekday(): Monday=0 … Sunday=6.
    start_time/end_time are 'HH:MM' (24h). subject_id + teacher_id are needed
    before a slot can generate lectures, but may be omitted while drafting.
    """

    day_of_week: int
    start_time: str
    end_time: str
    subject_id: uuid.UUID | None = None
    teacher_id: uuid.UUID | None = None
    classroom_id: uuid.UUID | None = None
    delivery_mode: str = "offline"


class TimetableSlotResponse(TimetableSlot):
    id: uuid.UUID
    batch_id: uuid.UUID


class BatchTimetableUpdate(BaseModel):
    """Replace a batch's entire weekly pattern with these slots."""

    slots: list[TimetableSlot] = []


class GenerateScheduleSummary(BaseModel):
    """Result of generating lectures from a weekly timetable over a date range."""

    from_date: str
    to_date: str
    generated: int
    skipped: int
    errors: list[str] = []


class HolidayCreate(BaseModel):
    """A non-teaching day the scheduler must skip."""

    holiday_date: date
    name: str


class HolidayResponse(BaseModel):
    id: uuid.UUID
    branch_id: uuid.UUID
    holiday_date: date
    name: str


class EligibleSubstitute(BaseModel):
    """A teacher who can actually cover a lecture (free, not on leave).

    ``same_subject`` is True when the teacher is assigned to the lecture's
    subject (the default, safe pick); False rows only appear when the caller opts
    into cross-subject cover. ``subjects`` are the teacher's own subject names, so
    the picker can show "Chemistry" next to a cross-subject candidate."""

    teacher_id: uuid.UUID
    first_name: str
    last_name: str
    same_subject: bool = True
    subjects: list[str] = []


class TeacherLeaveCreate(BaseModel):
    """A teacher's planned unavailability (inclusive date range)."""

    teacher_id: uuid.UUID
    start_date: date
    end_date: date
    reason: str | None = None


class TeacherLeaveResponse(BaseModel):
    id: uuid.UUID
    teacher_id: uuid.UUID
    branch_id: uuid.UUID
    start_date: date
    end_date: date
    reason: str | None = None


class LectureReschedule(BaseModel):
    scheduled_start: datetime
    scheduled_end: datetime
    classroom_id: uuid.UUID | None = None


class LectureNoShow(BaseModel):
    """Mark a lecture as no-show (didn't happen — distinct from cancel).

    Reason buckets: TEACHER_NO_SHOW | STUDENT_NO_SHOW | EXTERNAL | OTHER.
    """

    no_show_reason: str = "TEACHER_NO_SHOW"
    notes: str | None = None


class LectureSubstitute(BaseModel):
    """Mark a lecture as taught by someone other than the scheduled teacher.
    Set actual_teacher_id to null to clear the substitution.

    ``allow_cross_subject`` opts out of the Subject→Teacher lock for THIS
    assignment: when True, a teacher not assigned to the lecture's subject may
    cover it (e.g. a Physics teacher takes a Maths class). Default False keeps the
    lock as the guarantee; the override is deliberate and per-assignment."""

    actual_teacher_id: uuid.UUID | None
    change_reason: str | None = "SUBSTITUTE"
    change_notes: str | None = None
    allow_cross_subject: bool = False


class LectureResponse(BaseModel):
    id: uuid.UUID
    teacher_id: uuid.UUID
    batch_id: uuid.UUID
    classroom_id: uuid.UUID | None = None
    subject_id: uuid.UUID
    topic_id: uuid.UUID | None = None
    scheduled_start: datetime
    scheduled_end: datetime
    actual_start: datetime | None = None
    actual_end: datetime | None = None
    late_flag: bool | None = None
    actual_duration_min: int | None = None
    delivery_mode: str
    lecture_status: str
    notes: str | None = None
    actual_teacher_id: uuid.UUID | None = None
    change_reason: str | None = None
    change_notes: str | None = None
    no_show_reason: str | None = None
    branch_id: uuid.UUID
    academic_year_id: uuid.UUID
    status: str
    model_config = {"from_attributes": True}


class LectureSessionCreate(BaseModel):
    """Create an ad-hoc / makeup / planned-completion teaching session.

    batch_ids: 1+ batches that attended (use multiple for merged batches).
    lecture_ids: 0+ scheduled lectures fulfilled by this session.
        - 0 = pure ad-hoc, no plan existed
        - 1 = normal completion / single-plan makeup
        - 2+ = merged batches taught together
    origin: planned | makeup | ad_hoc — defaults to ad_hoc for this endpoint.
    """

    teacher_id: uuid.UUID
    subject_id: uuid.UUID
    batch_ids: list[uuid.UUID]
    lecture_ids: list[uuid.UUID] = []
    classroom_id: uuid.UUID | None = None
    topic_id: uuid.UUID | None = None
    actual_start: datetime
    actual_end: datetime | None = None
    delivery_mode: str = "offline"
    origin: str = "ad_hoc"
    notes: str | None = None


class LectureSessionResponse(BaseModel):
    id: uuid.UUID
    teacher_id: uuid.UUID
    subject_id: uuid.UUID
    topic_id: uuid.UUID | None = None
    classroom_id: uuid.UUID | None = None
    actual_start: datetime
    actual_end: datetime | None = None
    delivery_mode: str
    session_status: str
    origin: str
    notes: str | None = None
    branch_id: uuid.UUID
    academic_year_id: uuid.UUID
    batch_ids: list[uuid.UUID] = []
    lecture_ids: list[uuid.UUID] = []
    status: str
    model_config = {"from_attributes": True}


class AdherenceTotals(BaseModel):
    planned: int
    completed_as_planned: int
    substituted: int
    cancelled: int
    no_show: int
    rescheduled: int


class AdherenceSessions(BaseModel):
    planned: int
    makeup: int
    ad_hoc: int
    merged: int


class AdherenceRates(BaseModel):
    adherence_pct: float
    substitute_pct: float
    cancellation_pct: float
    no_show_pct: float
    # Teacher-attributable no-shows only — the reliability KPI.
    teacher_no_show_pct: float


class AdherenceNoShowBreakdown(BaseModel):
    teacher: int
    student: int
    external: int
    other: int


class AdherenceTeacherRow(BaseModel):
    teacher_id: uuid.UUID
    first_name: str
    last_name: str
    planned: int
    substituted_out: int
    substituted_in: int
    cancelled: int
    substitute_rate_pct: float


class SyllabusBatchRow(BaseModel):
    batch_id: uuid.UUID
    batch_name: str
    batch_code: str
    course_id: uuid.UUID
    total_topics: int
    delivered_topics: int
    coverage_pct: float
    # Time-weighted pace fields (Tier 7).
    target_exam_date: date | None = None
    expected_coverage_pct: float = 0.0
    pace_delta_pct: float = 0.0
    # ahead | on_pace | behind | critically_behind | no_data
    pace_status: str = "no_data"


class AdherenceResponse(BaseModel):
    from_date: datetime | None = None
    to_date: datetime | None = None
    totals: AdherenceTotals
    sessions: AdherenceSessions
    rates: AdherenceRates
    no_show_breakdown: AdherenceNoShowBreakdown
    by_teacher: list[AdherenceTeacherRow]
    by_batch_syllabus: list[SyllabusBatchRow] = []


class RosterSnapshot(BaseModel):
    planned: int
    completed: int
    in_progress: int
    pending: int
    no_show_teacher: int
    no_show_other: int
    cancelled: int
    off_plan_makeup: int
    off_plan_ad_hoc: int
    off_plan_merged: int


class RosterEvent(BaseModel):
    """A lecture or session pre-rendered for the roster timeline.

    The frontend stays presentation-only — status_label / status_tone /
    status_sub are derived here using the same rules as the lectures-table
    deriveStatus() helper.
    """

    kind: str  # "lecture" | "session"
    id: uuid.UUID
    start: datetime
    end: datetime | None = None
    status_label: str
    status_tone: str  # "default" | "secondary" | "success" | "destructive"
    status_sub: str | None = None
    batch_name: str | None = None
    batch_names: list[str] = []  # session can span multiple batches
    subject_name: str | None = None
    topic_name: str | None = None
    classroom_name: str | None = None
    actual_teacher_id: uuid.UUID | None = None
    actual_teacher_name: str | None = None
    no_show_reason: str | None = None
    is_covered: bool = False
    origin: str | None = None  # for sessions only


class RosterLiveNow(BaseModel):
    kind: str  # "live" | "overdue"
    lecture_id: uuid.UUID
    teacher_id: uuid.UUID
    teacher_name: str
    batch_name: str | None = None
    subject_name: str | None = None
    topic_name: str | None = None
    classroom_name: str | None = None
    scheduled_start: datetime
    scheduled_end: datetime
    minutes_overdue: int | None = None


class RosterTeacherSummary(BaseModel):
    planned: int
    completed: int
    in_progress: int
    no_show: int
    cancelled: int
    sub_in: int
    sub_out: int
    off_plan: int


class RosterTeacherRow(BaseModel):
    teacher_id: uuid.UUID
    first_name: str
    last_name: str
    summary: RosterTeacherSummary
    events: list[RosterEvent]


class RosterIdleTeacher(BaseModel):
    teacher_id: uuid.UUID
    first_name: str
    last_name: str


class RosterResponse(BaseModel):
    date: str
    now: datetime
    snapshot: RosterSnapshot
    live_now: list[RosterLiveNow]
    teachers: list[RosterTeacherRow]
    idle_teachers: list[RosterIdleTeacher]


class OutcomeSummary(BaseModel):
    tests_evaluated: int
    students_with_marks: int
    branch_avg_score: float


class OutcomeTeacherRow(BaseModel):
    teacher_id: uuid.UUID
    first_name: str
    last_name: str
    subject_id: uuid.UUID
    subject_name: str
    tests_count: int
    students_count: int
    avg_score_pct: float
    delta_vs_branch_pct: float


class OutcomeAttendanceBucket(BaseModel):
    bucket: str  # ">=80%" | "50-80%" | "<50%"
    students: int
    avg_score: float


class OutcomeResponse(BaseModel):
    from_date: datetime | None = None
    to_date: datetime | None = None
    summary: OutcomeSummary
    by_teacher: list[OutcomeTeacherRow]
    attendance_buckets: list[OutcomeAttendanceBucket]


class ProductivityTeacherRow(BaseModel):
    teacher_id: uuid.UUID
    first_name: str
    last_name: str
    lectures_taught: int
    hours_taught: float
    avg_lecture_min: float
    late_count: int
    on_time_count: int
    # Share of timed lectures that started on time (the punctuality KPI).
    # None when the teacher taught nothing timed in range.
    punctuality_pct: float | None
    distinct_topics: int
    # ── Attendance-aligned ──────────────────────────────────────────────
    # Avg student turnout across this teacher's completed lectures (Layer-1
    # present students / batch size). None when none of their lectures'
    # batches have students. Credited to the effective (delivering) teacher.
    student_turnout_pct: float | None = None
    turnout_lectures: int = 0
    # Delivery reliability of classes ASSIGNED to this teacher (lifecycle, not
    # biometric): taught_self / assigned. None when nothing was assigned.
    assigned: int = 0
    taught_self: int = 0
    teacher_no_show: int = 0
    substituted_out: int = 0
    reliability_pct: float | None = None


class ProductivitySummary(BaseModel):
    teachers: int
    total_lectures: int
    total_hours: float
    total_late: int
    branch_punctuality_pct: float
    # Attendance-aligned branch rollups (None when no data in range).
    branch_turnout_pct: float | None = None
    branch_reliability_pct: float | None = None
    total_teacher_no_show: int = 0


class ProductivityResponse(BaseModel):
    from_date: datetime | None = None
    to_date: datetime | None = None
    summary: ProductivitySummary
    by_teacher: list[ProductivityTeacherRow]


# ── Advanced Teacher Productivity report ─────────────────────────────────────


class ProductivityReportTeacherRow(BaseModel):
    teacher_id: uuid.UUID
    first_name: str
    last_name: str
    scheduled: int
    conducted: int
    completion_pct: float | None
    hours: float
    minutes: int
    on_time_count: int
    late_count: int
    punctuality_pct: float | None
    avg_delay_min: float
    topics_planned: int
    topics_covered: int


class ProductivityReportSubjectRow(BaseModel):
    subject_id: uuid.UUID
    subject_name: str
    scheduled: int
    conducted: int
    completion_pct: float | None
    hours: float
    minutes: int


class ProductivityReportBatchRow(BaseModel):
    batch_id: uuid.UUID
    batch_name: str
    scheduled: int
    conducted: int
    completion_pct: float | None
    hours: float
    minutes: int


class ProductivityReportTrendPoint(BaseModel):
    iso_year: int
    iso_week: int
    label: str
    scheduled: int
    conducted: int
    completion_pct: float | None
    punctuality_pct: float | None
    hours: float


class ProductivityReportSummary(BaseModel):
    teachers: int
    total_scheduled: int
    total_conducted: int
    total_hours: float
    completion_pct: float | None = None
    punctuality_pct: float | None = None


class ProductivityReportResponse(BaseModel):
    from_date: datetime | None = None
    to_date: datetime | None = None
    summary: ProductivityReportSummary
    by_teacher: list[ProductivityReportTeacherRow]
    by_subject: list[ProductivityReportSubjectRow]
    by_batch: list[ProductivityReportBatchRow]
    trend: list[ProductivityReportTrendPoint]


class AttendanceMark(BaseModel):
    student_id: uuid.UUID
    attendance_status: str = "PRESENT"


class AttendanceResponse(BaseModel):
    id: uuid.UUID
    lecture_id: uuid.UUID
    student_id: uuid.UUID
    attendance_status: str
    marked_at: datetime
    model_config = {"from_attributes": True}


class DppCoverageResponse(BaseModel):
    """Completed lectures vs. those with a DPP generated off them."""

    completed: int
    with_dpp: int
