import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.modules.auth.permissions.rbac import (
    get_current_user,
    require_manager_or_audit,
    require_roles,
)
from app.modules.auth.permissions.scope import (
    BatchScope,
    require_batch_scope,
    require_student_in_scope,
)
from app.modules.attendance.services import attendance_report_service
from app.modules.attendance.schemas.attendance_schemas import (
    AttendanceMarkRequest,
    AttendanceRecordResponse,
    AttendanceReportResponse,
    AttendanceSummaryResponse,
    BatchMatrixResponse,
    BranchSummaryRow,
    ClassroomRegisterRow,
    DailyAttendanceResponse,
    DayManualMarkRequest,
    DayNotifyRequest,
    DefaulterRow,
    ExceptionCreate,
    ExceptionResolve,
    ExceptionResponse,
    RawPunchBatchCreate,
    RawPunchResponse,
)
from app.modules.attendance.services import attendance_service, daily_service
from app.modules.student.models.student_models import Student
from sqlalchemy import select

router = APIRouter(prefix="/attendance", tags=["attendance"])


@router.post("/raw", response_model=list[RawPunchResponse])
async def receive_raw_punches(
    body: RawPunchBatchCreate,
    request: Request,
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin", "device_operator"])),
    session: AsyncSession = Depends(get_db),
):
    punch_dicts = []
    for p in body.punches:
        student_result = await session.execute(
            select(Student.branch_id).where(Student.id == p.student_id)
        )
        row = student_result.first()
        branch_id = row[0] if row else None
        if not branch_id:
            continue
        punch_dicts.append({
            "device_id": p.device_id,
            "student_id": p.student_id,
            "punch_timestamp": p.punch_timestamp,
            "sync_batch_id": p.sync_batch_id,
            "branch_id": branch_id,
        })

    if not punch_dicts:
        return []

    return await attendance_service.receive_raw_punches(
        session, punch_dicts, current_user["user_id"],
        request.client.host if request.client else None,
    )


@router.post("/process/{lecture_id}", response_model=list[AttendanceRecordResponse])
async def process_raw_punches(
    lecture_id: uuid.UUID,
    request: Request,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin", "teacher"])),
    session: AsyncSession = Depends(get_db),
):
    return await attendance_service.process_raw_punches(
        session, lecture_id, branch_id, current_user["user_id"],
        request.client.host if request.client else None,
    )


@router.post("/lecture/{lecture_id}/mark", response_model=AttendanceRecordResponse)
async def mark_attendance(
    lecture_id: uuid.UUID,
    body: AttendanceMarkRequest,
    request: Request,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin", "teacher"])),
    session: AsyncSession = Depends(get_db),
):
    return await attendance_service.mark_attendance(
        session, lecture_id, body.student_id, body.attendance_status, body.source,
        branch_id, current_user["user_id"],
        request.client.host if request.client else None,
    )


@router.get("/lecture/{lecture_id}", response_model=list[AttendanceRecordResponse])
async def get_lecture_attendance(
    lecture_id: uuid.UUID,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin", "academic_head", "teacher"])),
    session: AsyncSession = Depends(get_db),
):
    return await attendance_service.get_lecture_attendance(session, lecture_id, branch_id)


@router.get("/lecture/{lecture_id}/report", response_model=AttendanceReportResponse)
async def get_attendance_report(
    lecture_id: uuid.UUID,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin", "academic_head", "teacher"])),
    session: AsyncSession = Depends(get_db),
):
    return await attendance_service.generate_attendance_report(session, lecture_id, branch_id)


@router.get("/student/{student_id}", response_model=list[AttendanceRecordResponse])
async def get_student_attendance(
    student_id: uuid.UUID,
    branch_id: uuid.UUID = Query(...),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    return await attendance_service.get_student_attendance(
        session, student_id, branch_id, offset, limit
    )


_REPORT_ROLES = ["super_admin", "branch_admin", "academic_head", "teacher"]


@router.get("/daily/student/{student_id}", response_model=list[DailyAttendanceResponse])
async def get_student_day_timeline(
    student_id: uuid.UUID,
    branch_id: uuid.UUID = Query(...),
    start: date = Query(..., description="inclusive local start date"),
    end: date = Query(..., description="inclusive local end date"),
    scope: BatchScope = Depends(require_batch_scope("attendance")),
    session: AsyncSession = Depends(get_db),
):
    """Reference A — a student's IN/OUT/status timeline across days. A coordinator
    may only view students in their assigned batches."""
    await require_student_in_scope(session, scope, student_id)
    return await daily_service.student_timeline(
        session, student_id=student_id, branch_id=branch_id, start=start, end=end
    )


@router.get("/daily/register", response_model=list[ClassroomRegisterRow])
async def get_classroom_register(
    branch_id: uuid.UUID = Query(...),
    batch_id: uuid.UUID = Query(...),
    day: date = Query(..., description="local date"),
    scope: BatchScope = Depends(require_batch_scope("attendance")),
    session: AsyncSession = Depends(get_db),
):
    """Reference B — P/A roster for a batch on one day."""
    scope.require(batch_id)
    return await daily_service.classroom_register(
        session, branch_id=branch_id, batch_id=batch_id, day=day
    )


@router.get("/daily/summary/{student_id}", response_model=AttendanceSummaryResponse)
async def get_student_attendance_summary(
    student_id: uuid.UUID,
    branch_id: uuid.UUID = Query(...),
    start: date = Query(...),
    end: date = Query(...),
    scope: BatchScope = Depends(require_batch_scope("attendance")),
    session: AsyncSession = Depends(get_db),
):
    """Attendance % over a range (working_days = days with >=1 lecture). A
    coordinator may only view students in their assigned batches."""
    await require_student_in_scope(session, scope, student_id)
    return await daily_service.monthly_summary(
        session, student_id=student_id, branch_id=branch_id, start=start, end=end
    )


# ── Insights (on-screen aggregates) ────────────────────────────────────────


@router.get("/daily/matrix", response_model=BatchMatrixResponse)
async def get_batch_matrix(
    branch_id: uuid.UUID = Query(...),
    batch_id: uuid.UUID = Query(...),
    start: date = Query(...),
    end: date = Query(...),
    scope: BatchScope = Depends(require_batch_scope("attendance")),
    session: AsyncSession = Depends(get_db),
):
    """Batch register matrix — students × working-day columns (P/L/A cells)."""
    scope.require(batch_id)
    return await daily_service.batch_matrix(
        session, branch_id=branch_id, batch_id=batch_id, start=start, end=end
    )


@router.get("/daily/branch-summary", response_model=list[BranchSummaryRow])
async def get_branch_summary(
    branch_id: uuid.UUID = Query(...),
    start: date = Query(...),
    end: date = Query(...),
    scope: BatchScope = Depends(require_batch_scope("attendance")),
    session: AsyncSession = Depends(get_db),
):
    """One summary row per active batch — the institute overview. Scoped: a Floor
    Coordinator / Accounts user sees only their batches (all when unrestricted)."""
    rows = await daily_service.branch_summary(
        session, branch_id=branch_id, start=start, end=end
    )
    if scope.all:
        return rows
    # branch_summary returns dicts; filter by the scoped batch ids.
    return [r for r in rows if scope.allows(r["batch_id"])]


@router.get("/daily/defaulters", response_model=list[DefaulterRow])
async def get_defaulters(
    branch_id: uuid.UUID = Query(...),
    start: date = Query(...),
    end: date = Query(...),
    threshold: float = Query(75.0, ge=0, le=100),
    current_user: dict = Depends(require_roles(_REPORT_ROLES)),
    session: AsyncSession = Depends(get_db),
):
    """Students below ``threshold`` % over the range, worst-first."""
    return await daily_service.branch_defaulters(
        session, branch_id=branch_id, start=start, end=end, threshold=threshold
    )


# ── Downloadable reports (Excel / PDF) ─────────────────────────────────────


def _download(filename: str, data: bytes, media_type: str) -> Response:
    return Response(
        content=data,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/reports/student/{student_id}")
async def download_student_report(
    student_id: uuid.UUID,
    branch_id: uuid.UUID = Query(...),
    start: date = Query(...),
    end: date = Query(...),
    fmt: str = Query("xlsx", pattern="^(xlsx|pdf)$"),
    current_user: dict = Depends(require_roles(_REPORT_ROLES)),
    session: AsyncSession = Depends(get_db),
):
    """Individual student attendance report (timeline + %) as Excel or PDF."""
    filename, data, mime = await attendance_report_service.student_report(
        session, student_id=student_id, branch_id=branch_id, start=start, end=end, fmt=fmt,
    )
    return _download(filename, data, mime)


@router.get("/reports/batch/{batch_id}")
async def download_batch_report(
    batch_id: uuid.UUID,
    branch_id: uuid.UUID = Query(...),
    start: date = Query(...),
    end: date = Query(...),
    fmt: str = Query("xlsx", pattern="^(xlsx|pdf)$"),
    current_user: dict = Depends(require_roles(_REPORT_ROLES)),
    session: AsyncSession = Depends(get_db),
):
    """Single-batch attendance register (matrix) as Excel or PDF."""
    filename, data, mime = await attendance_report_service.batch_report(
        session, batch_id=batch_id, branch_id=branch_id, start=start, end=end, fmt=fmt,
    )
    return _download(filename, data, mime)


@router.get("/reports/all-batches")
async def download_all_batches_report(
    branch_id: uuid.UUID = Query(...),
    start: date = Query(...),
    end: date = Query(...),
    fmt: str = Query("xlsx", pattern="^(xlsx|pdf)$"),
    current_user: dict = Depends(require_roles(_REPORT_ROLES)),
    session: AsyncSession = Depends(get_db),
):
    """All-batches attendance summary (+ per-batch sheets in Excel)."""
    filename, data, mime = await attendance_report_service.all_batches_report(
        session, branch_id=branch_id, start=start, end=end, fmt=fmt,
    )
    return _download(filename, data, mime)


@router.get("/reports/daily-ledger")
async def download_daily_ledger_report(
    branch_id: uuid.UUID = Query(...),
    start: date = Query(...),
    end: date = Query(...),
    fmt: str = Query("xlsx", pattern="^(xlsx|pdf)$"),
    current_user: dict = Depends(require_roles(_REPORT_ROLES)),
    session: AsyncSession = Depends(get_db),
):
    """Immutable all-students daily ledger — every student's per-day record over
    the range, unaffected by later batch/subject/profile changes."""
    filename, data, mime = await attendance_report_service.daily_ledger_report(
        session, branch_id=branch_id, start=start, end=end, fmt=fmt,
    )
    return _download(filename, data, mime)


@router.get("/reports/day")
async def download_day_report(
    branch_id: uuid.UUID = Query(...),
    batch_id: uuid.UUID = Query(...),
    day: date = Query(..., description="local date"),
    fmt: str = Query("pdf", pattern="^(xlsx|pdf)$"),
    current_user: dict = Depends(require_roles(_REPORT_ROLES)),
    session: AsyncSession = Depends(get_db),
):
    """Single-day batch attendance snapshot (PRN · RFID · In · Out · Status)."""
    filename, data, mime = await attendance_report_service.day_report(
        session, batch_id=batch_id, branch_id=branch_id, day=day, fmt=fmt,
    )
    return _download(filename, data, mime)


@router.post("/daily/mark", response_model=DailyAttendanceResponse)
async def manual_mark_day(
    body: DayManualMarkRequest,
    request: Request,
    branch_id: uuid.UUID = Query(...),
    # The 'Manually Marked' override is Manager-only per the RBAC spec — Floor
    # Coordinators and Accounts cannot manual-mark; denied attempts are audited.
    current_user: dict = Depends(
        require_manager_or_audit("Manual Attendance", "attendance")
    ),
    session: AsyncSession = Depends(get_db),
):
    """Manager manual day mark for a student who forgot to scan. Writes a
    MANUAL day row (never overwritten by a later punch sync)."""
    return await daily_service.manual_mark_day(
        session,
        student_id=body.student_id,
        branch_id=branch_id,
        day=body.day,
        status=body.status,
        user_id=current_user["user_id"],
        ip_address=request.client.host if request.client else None,
    )


@router.post("/daily/notify")
async def notify_day_students(
    body: DayNotifyRequest,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin"])),
    session: AsyncSession = Depends(get_db),
):
    """Queue a parent WhatsApp notification for the selected students on a day
    (dormant charge-wise until WhatsApp is enabled)."""
    count = await daily_service.notify_selected_students(
        session,
        branch_id=branch_id,
        batch_id=body.batch_id,
        day=body.day,
        student_ids=body.student_ids,
    )
    return {"queued": count}


@router.post("/exceptions", response_model=ExceptionResponse)
async def create_exception(
    body: ExceptionCreate,
    request: Request,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin", "teacher"])),
    session: AsyncSession = Depends(get_db),
):
    return await attendance_service.create_exception(
        session, body.student_id, body.lecture_id, body.reason,
        branch_id, current_user["user_id"],
        request.client.host if request.client else None,
    )


@router.patch("/exceptions/{exception_id}/resolve", response_model=ExceptionResponse)
async def resolve_exception(
    exception_id: uuid.UUID,
    body: ExceptionResolve,
    request: Request,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin"])),
    session: AsyncSession = Depends(get_db),
):
    return await attendance_service.resolve_exception(
        session, exception_id, branch_id, current_user["user_id"],
        body.resolution_notes,
        request.client.host if request.client else None,
    )
