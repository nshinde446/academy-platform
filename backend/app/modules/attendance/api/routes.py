import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.modules.auth.permissions.rbac import get_current_user, require_roles
from app.modules.attendance.services import attendance_report_service
from app.modules.attendance.schemas.attendance_schemas import (
    AttendanceMarkRequest,
    AttendanceRecordResponse,
    AttendanceReportResponse,
    AttendanceSummaryResponse,
    ClassroomRegisterRow,
    DailyAttendanceResponse,
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
    current_user: dict = Depends(require_roles(_REPORT_ROLES)),
    session: AsyncSession = Depends(get_db),
):
    """Reference A — a student's IN/OUT/status timeline across days."""
    return await daily_service.student_timeline(
        session, student_id=student_id, branch_id=branch_id, start=start, end=end
    )


@router.get("/daily/register", response_model=list[ClassroomRegisterRow])
async def get_classroom_register(
    branch_id: uuid.UUID = Query(...),
    batch_id: uuid.UUID = Query(...),
    day: date = Query(..., description="local date"),
    current_user: dict = Depends(require_roles(_REPORT_ROLES)),
    session: AsyncSession = Depends(get_db),
):
    """Reference B — P/A roster for a batch on one day."""
    return await daily_service.classroom_register(
        session, branch_id=branch_id, batch_id=batch_id, day=day
    )


@router.get("/daily/summary/{student_id}", response_model=AttendanceSummaryResponse)
async def get_student_attendance_summary(
    student_id: uuid.UUID,
    branch_id: uuid.UUID = Query(...),
    start: date = Query(...),
    end: date = Query(...),
    current_user: dict = Depends(require_roles(_REPORT_ROLES)),
    session: AsyncSession = Depends(get_db),
):
    """Attendance % over a range (working_days = days with >=1 lecture)."""
    return await daily_service.monthly_summary(
        session, student_id=student_id, branch_id=branch_id, start=start, end=end
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
