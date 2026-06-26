import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.modules.auth.permissions.rbac import get_current_user, require_roles
from app.modules.lectures.schemas.lecture_schemas import (
    AdherenceResponse,
    AttendanceMark,
    AttendanceResponse,
    BatchTimetableUpdate,
    CopyScheduleSummary,
    EligibleSubstitute,
    GenerateScheduleSummary,
    HolidayCreate,
    HolidayResponse,
    ImportSchedulePreview,
    ImportScheduleSummary,
    TeacherLeaveCreate,
    TeacherLeaveResponse,
    LectureActuals,
    LectureCreate,
    LectureNoShow,
    LectureReschedule,
    LectureResponse,
    LectureSessionCreate,
    LectureSessionResponse,
    LectureSubstitute,
    OutcomeResponse,
    ProductivityResponse,
    RosterResponse,
    TimetableSlotResponse,
)
from app.modules.lectures.services import import_service, lecture_service

router = APIRouter(prefix="/lectures", tags=["lectures"])


@router.post("", response_model=LectureResponse)
async def schedule_lecture(
    body: LectureCreate,
    request: Request,
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin", "academic_head"])),
    session: AsyncSession = Depends(get_db),
):
    return await lecture_service.schedule_lecture(
        session, body, current_user["user_id"],
        request.client.host if request.client else None,
    )


@router.post("/import", response_model=ImportScheduleSummary)
async def import_schedule(
    request: Request,
    file: UploadFile = File(...),
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(
        require_roles(["super_admin", "branch_admin", "academic_head"])
    ),
    session: AsyncSession = Depends(get_db),
):
    """Bulk-schedule lectures from a CSV/Excel file. Required columns:
    date, start_time, end_time, teacher_email, batch_code, subject_code.
    Optional: classroom_code, delivery_mode, notes, topic.

    Returns {imported, skipped, errors[]} so the UI can show per-row
    failures without the whole upload being lost."""
    return await import_service.import_schedule(
        session,
        file,
        branch_id,
        current_user["user_id"],
        request.client.host if request.client else None,
    )


@router.post("/import/preview", response_model=ImportSchedulePreview)
async def preview_import_schedule(
    file: UploadFile = File(...),
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(
        require_roles(["super_admin", "branch_admin", "academic_head"])
    ),
    session: AsyncSession = Depends(get_db),
):
    """Dry-run the schedule import: validate every row (codes, times, the
    Subject→Teacher lock, teacher leave, conflicts) and report per-row status
    WITHOUT creating anything. Lets the admin fix the sheet before committing."""
    return await import_service.preview_schedule(session, file, branch_id)


@router.get("", response_model=list[LectureResponse])
async def list_lectures(
    branch_id: uuid.UUID = Query(...),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    return await lecture_service.list_lectures(session, branch_id, offset, limit)


@router.post("/sessions", response_model=LectureSessionResponse)
async def create_lecture_session(
    body: LectureSessionCreate,
    request: Request,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin", "academic_head"])),
    session: AsyncSession = Depends(get_db),
):
    """Record a session that actually happened.

    Supports ad-hoc makeup classes (zero linked plans), normal completions
    (one linked plan), and merged-batch sessions (one plan per batch).
    """
    return await lecture_service.create_lecture_session(
        session, body, branch_id, current_user["user_id"],
        request.client.host if request.client else None,
    )


@router.get("/sessions", response_model=list[LectureSessionResponse])
async def list_lecture_sessions(
    branch_id: uuid.UUID = Query(...),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    return await lecture_service.list_lecture_sessions(session, branch_id, offset, limit)


@router.get("/roster", response_model=RosterResponse)
async def get_roster(
    branch_id: uuid.UUID = Query(...),
    date: str = Query(..., description="YYYY-MM-DD UTC date"),
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin", "academic_head"])),
    session: AsyncSession = Depends(get_db),
):
    """Today's Roster: per-teacher timeline of every lecture and off-plan
    session for a given date, plus snapshot KPIs and a Live Now strip
    (in-progress + overdue starts).
    """
    from datetime import datetime, timezone
    try:
        day = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        from fastapi import HTTPException, status as http_status
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="date must be YYYY-MM-DD",
        )
    return await lecture_service.get_roster(session, branch_id, day)


@router.get("/insights/outcomes", response_model=OutcomeResponse)
async def get_outcome_insights(
    branch_id: uuid.UUID = Query(...),
    from_date: datetime | None = Query(None),
    to_date: datetime | None = Query(None),
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin", "academic_head"])),
    session: AsyncSession = Depends(get_db),
):
    """Outcome correlation: lectures × tests.

    Per (teacher × subject) avg student score on tests for their batches,
    delta vs branch avg. Plus a branch-wide attendance × score breakdown
    answering 'do students who attend score better?'.
    """
    return await lecture_service.get_outcome_insights(
        session, branch_id, from_date, to_date
    )


@router.get("/insights/adherence", response_model=AdherenceResponse)
async def get_adherence_insights(
    branch_id: uuid.UUID = Query(...),
    from_date: datetime | None = Query(None),
    to_date: datetime | None = Query(None),
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin", "academic_head"])),
    session: AsyncSession = Depends(get_db),
):
    """Plan-vs-Actual adherence dashboard payload.

    Aggregates lectures + lecture_sessions in the given window into KPI
    totals, rates, session-origin breakdown, and a per-teacher leaderboard
    sorted by substitute_rate_pct desc.
    """
    return await lecture_service.get_adherence_insights(
        session, branch_id, from_date, to_date
    )


@router.get("/insights/productivity", response_model=ProductivityResponse)
async def get_productivity_insights(
    branch_id: uuid.UUID = Query(...),
    from_date: datetime | None = Query(None),
    to_date: datetime | None = Query(None),
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin", "academic_head"])),
    session: AsyncSession = Depends(get_db),
):
    """Teacher productivity: hours taught, punctuality (late-start rate), and
    topic coverage per teacher over the window, plus a branch summary. Derived
    from the actuals captured live or via the end-of-day backfill."""
    return await lecture_service.get_productivity_insights(
        session, branch_id, from_date, to_date
    )


@router.post("/copy-to-next-day", response_model=CopyScheduleSummary)
async def copy_to_next_day(
    request: Request,
    branch_id: uuid.UUID = Query(...),
    source_date: str = Query(..., description="YYYY-MM-DD day to copy from"),
    target_date: str | None = Query(
        None, description="YYYY-MM-DD destination; defaults to source + 1 day"
    ),
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin", "academic_head"])),
    session: AsyncSession = Depends(get_db),
):
    """Duplicate a day's lecture plan to another date (PDF §5).

    Idempotent + conflict-aware: clones the plan, resets actuals/topic/late, and
    skips (rather than fails) any row that would collide on the target day.
    """
    from datetime import date as _date
    from fastapi import HTTPException, status as http_status

    def _parse(label: str, value: str) -> _date:
        try:
            return _date.fromisoformat(value)
        except ValueError:
            raise HTTPException(
                status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"{label} must be YYYY-MM-DD",
            )

    src = _parse("source_date", source_date)
    tgt = _parse("target_date", target_date) if target_date else None
    return await lecture_service.copy_to_next_day(
        session, branch_id, src, tgt, current_user["user_id"],
        request.client.host if request.client else None,
    )


@router.get("/timetable", response_model=list[TimetableSlotResponse])
async def get_batch_timetable(
    branch_id: uuid.UUID = Query(...),
    batch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(
        require_roles(["super_admin", "branch_admin", "academic_head"])
    ),
    session: AsyncSession = Depends(get_db),
):
    """A batch's recurring weekly timetable (day_of_week: Mon=0 … Sun=6)."""
    return await lecture_service.get_batch_timetable(session, branch_id, batch_id)


@router.put("/timetable", response_model=list[TimetableSlotResponse])
async def set_batch_timetable(
    body: BatchTimetableUpdate,
    request: Request,
    branch_id: uuid.UUID = Query(...),
    batch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(
        require_roles(["super_admin", "branch_admin", "academic_head"])
    ),
    session: AsyncSession = Depends(get_db),
):
    """Replace a batch's whole weekly pattern. Validates the Subject→Teacher
    lock on every slot that pins both."""
    return await lecture_service.set_batch_timetable(
        session, branch_id, batch_id, body, current_user["user_id"],
        request.client.host if request.client else None,
    )


@router.post("/timetable/generate", response_model=GenerateScheduleSummary)
async def generate_from_timetable(
    request: Request,
    branch_id: uuid.UUID = Query(...),
    from_date: str = Query(..., description="YYYY-MM-DD inclusive start"),
    to_date: str = Query(..., description="YYYY-MM-DD inclusive end"),
    batch_id: uuid.UUID | None = Query(
        None, description="Limit to one batch; omit to generate for all batches"
    ),
    current_user: dict = Depends(
        require_roles(["super_admin", "branch_admin", "academic_head"])
    ),
    session: AsyncSession = Depends(get_db),
):
    """Generate scheduled lectures from the weekly timetable across a date range.
    Conflict-aware + idempotent: colliding or incomplete slots are skipped and
    reported, so re-running never double-books."""
    from datetime import date as _date
    from fastapi import HTTPException, status as http_status

    def _parse(label: str, value: str) -> _date:
        try:
            return _date.fromisoformat(value)
        except ValueError:
            raise HTTPException(
                status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"{label} must be YYYY-MM-DD",
            )

    return await lecture_service.generate_from_timetable(
        session,
        branch_id,
        batch_id,
        _parse("from_date", from_date),
        _parse("to_date", to_date),
        current_user["user_id"],
        request.client.host if request.client else None,
    )


@router.get("/holidays", response_model=list[HolidayResponse])
async def list_holidays(
    branch_id: uuid.UUID = Query(...),
    from_date: str | None = Query(None, description="YYYY-MM-DD"),
    to_date: str | None = Query(None, description="YYYY-MM-DD"),
    current_user: dict = Depends(
        require_roles(["super_admin", "branch_admin", "academic_head"])
    ),
    session: AsyncSession = Depends(get_db),
):
    """The branch's non-teaching days — the generator and copy skip these."""
    from datetime import date as _date
    from fastapi import HTTPException, status as http_status

    def _parse(label: str, value: str) -> _date:
        try:
            return _date.fromisoformat(value)
        except ValueError:
            raise HTTPException(
                status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"{label} must be YYYY-MM-DD",
            )

    return await lecture_service.list_holidays(
        session,
        branch_id,
        _parse("from_date", from_date) if from_date else None,
        _parse("to_date", to_date) if to_date else None,
    )


@router.post("/holidays", response_model=HolidayResponse)
async def add_holiday(
    body: HolidayCreate,
    request: Request,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(
        require_roles(["super_admin", "branch_admin", "academic_head"])
    ),
    session: AsyncSession = Depends(get_db),
):
    return await lecture_service.add_holiday(
        session, branch_id, body.holiday_date, body.name,
        current_user["user_id"],
        request.client.host if request.client else None,
    )


@router.delete("/holidays/{holiday_id}", status_code=204)
async def delete_holiday(
    holiday_id: uuid.UUID,
    request: Request,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(
        require_roles(["super_admin", "branch_admin", "academic_head"])
    ),
    session: AsyncSession = Depends(get_db),
):
    await lecture_service.delete_holiday(
        session, branch_id, holiday_id, current_user["user_id"],
        request.client.host if request.client else None,
    )


@router.get("/teacher-leaves", response_model=list[TeacherLeaveResponse])
async def list_teacher_leaves(
    branch_id: uuid.UUID = Query(...),
    teacher_id: uuid.UUID | None = Query(None),
    current_user: dict = Depends(
        require_roles(["super_admin", "branch_admin", "academic_head"])
    ),
    session: AsyncSession = Depends(get_db),
):
    """Planned teacher unavailability — scheduling skips/rejects these days."""
    return await lecture_service.list_teacher_leaves(session, branch_id, teacher_id)


@router.post("/teacher-leaves", response_model=TeacherLeaveResponse)
async def add_teacher_leave(
    body: TeacherLeaveCreate,
    request: Request,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(
        require_roles(["super_admin", "branch_admin", "academic_head"])
    ),
    session: AsyncSession = Depends(get_db),
):
    return await lecture_service.add_teacher_leave(
        session, branch_id, body.teacher_id, body.start_date, body.end_date,
        body.reason, current_user["user_id"],
        request.client.host if request.client else None,
    )


@router.delete("/teacher-leaves/{leave_id}", status_code=204)
async def delete_teacher_leave(
    leave_id: uuid.UUID,
    request: Request,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(
        require_roles(["super_admin", "branch_admin", "academic_head"])
    ),
    session: AsyncSession = Depends(get_db),
):
    await lecture_service.delete_teacher_leave(
        session, branch_id, leave_id, current_user["user_id"],
        request.client.host if request.client else None,
    )


@router.get(
    "/{lecture_id}/eligible-substitutes",
    response_model=list[EligibleSubstitute],
)
async def list_eligible_substitutes(
    lecture_id: uuid.UUID,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(
        require_roles(["super_admin", "branch_admin", "academic_head"])
    ),
    session: AsyncSession = Depends(get_db),
):
    """Teachers who can actually cover this lecture: qualified for the subject,
    free at its time, and not on leave. Powers the substitute picker."""
    return await lecture_service.list_eligible_substitutes(
        session, lecture_id, branch_id
    )


@router.get("/{lecture_id}", response_model=LectureResponse)
async def get_lecture(
    lecture_id: uuid.UUID,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    return await lecture_service.get_lecture(session, lecture_id, branch_id)


@router.patch("/{lecture_id}/start", response_model=LectureResponse)
async def start_lecture(
    lecture_id: uuid.UUID,
    request: Request,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(["super_admin", "teacher"])),
    session: AsyncSession = Depends(get_db),
):
    return await lecture_service.start_lecture(
        session, lecture_id, branch_id, current_user["user_id"],
        request.client.host if request.client else None,
    )


@router.patch("/{lecture_id}/complete", response_model=LectureResponse)
async def complete_lecture(
    lecture_id: uuid.UUID,
    request: Request,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(["super_admin", "teacher"])),
    session: AsyncSession = Depends(get_db),
):
    return await lecture_service.complete_lecture(
        session, lecture_id, branch_id, current_user["user_id"],
        request.client.host if request.client else None,
    )


@router.patch("/{lecture_id}/cancel", response_model=LectureResponse)
async def cancel_lecture(
    lecture_id: uuid.UUID,
    request: Request,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin"])),
    session: AsyncSession = Depends(get_db),
):
    return await lecture_service.cancel_lecture(
        session, lecture_id, branch_id, current_user["user_id"],
        request.client.host if request.client else None,
    )


@router.patch("/{lecture_id}/substitute", response_model=LectureResponse)
async def mark_substitute(
    lecture_id: uuid.UUID,
    body: LectureSubstitute,
    request: Request,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin", "academic_head"])),
    session: AsyncSession = Depends(get_db),
):
    return await lecture_service.mark_substitute(
        session, lecture_id, body, branch_id, current_user["user_id"],
        request.client.host if request.client else None,
    )


@router.patch("/{lecture_id}/no-show", response_model=LectureResponse)
async def mark_no_show(
    lecture_id: uuid.UUID,
    body: LectureNoShow,
    request: Request,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin", "academic_head"])),
    session: AsyncSession = Depends(get_db),
):
    """Mark a scheduled lecture as no-show (distinct from cancel).

    Captures teacher / student / external / other no-show reason. Only
    valid from 'scheduled' status. Cancel is for intentional, no-show is
    for unplanned absence.
    """
    return await lecture_service.mark_no_show(
        session, lecture_id, body, branch_id, current_user["user_id"],
        request.client.host if request.client else None,
    )


@router.patch("/{lecture_id}/actuals", response_model=LectureResponse)
async def update_actuals(
    lecture_id: uuid.UUID,
    body: LectureActuals,
    request: Request,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin", "academic_head", "teacher"])),
    session: AsyncSession = Depends(get_db),
):
    """End-of-day actuals entry (PDF §3): backfill actual_start / actual_end /
    topic without the live Start/Complete clicks. Recomputes late_flag +
    duration; setting actual_end completes the lecture."""
    return await lecture_service.update_actuals(
        session, lecture_id, body, branch_id, current_user["user_id"],
        request.client.host if request.client else None,
    )


@router.patch("/{lecture_id}/reschedule", response_model=LectureResponse)
async def reschedule_lecture(
    lecture_id: uuid.UUID,
    body: LectureReschedule,
    request: Request,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin", "academic_head"])),
    session: AsyncSession = Depends(get_db),
):
    return await lecture_service.reschedule_lecture(
        session, lecture_id, body, branch_id, current_user["user_id"],
        request.client.host if request.client else None,
    )


@router.post("/{lecture_id}/attendance", response_model=AttendanceResponse)
async def mark_attendance(
    lecture_id: uuid.UUID,
    body: AttendanceMark,
    request: Request,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(["super_admin", "teacher"])),
    session: AsyncSession = Depends(get_db),
):
    return await lecture_service.mark_attendance(
        session, lecture_id, body, branch_id, current_user["user_id"],
        request.client.host if request.client else None,
    )


@router.get("/{lecture_id}/attendance", response_model=list[AttendanceResponse])
async def get_attendance(
    lecture_id: uuid.UUID,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin", "academic_head", "teacher"])),
    session: AsyncSession = Depends(get_db),
):
    return await lecture_service.get_attendance(session, lecture_id, branch_id)


@router.delete("/{lecture_id}", status_code=204)
async def delete_lecture(
    lecture_id: uuid.UUID,
    request: Request,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin"])),
    session: AsyncSession = Depends(get_db),
):
    await lecture_service.delete_lecture(
        session, lecture_id, branch_id, current_user["user_id"],
        request.client.host if request.client else None,
    )
