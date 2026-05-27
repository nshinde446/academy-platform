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
    ImportScheduleSummary,
    LectureCreate,
    LectureNoShow,
    LectureReschedule,
    LectureResponse,
    LectureSessionCreate,
    LectureSessionResponse,
    LectureSubstitute,
    OutcomeResponse,
    RosterResponse,
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
