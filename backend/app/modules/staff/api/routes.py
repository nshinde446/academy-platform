import uuid
from datetime import date

from fastapi import APIRouter, Depends, File, Query, Request, Response, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.modules.attendance.services import staff_faculty_service, staff_report_service
from app.modules.auth.permissions.rbac import (
    get_current_user,
    require_manager_or_audit,
    require_roles,
)
from app.modules.staff.schemas.staff_schemas import (
    BulkDeleteSummary,
    BulkStaffDelete,
    DepartmentWithAllocation,
    ImportSummary,
    LinkTeacherRequest,
    StaffCreate,
    StaffResponse,
    StaffUpdate,
)
from app.modules.staff.services import import_service, staff_service

router = APIRouter(prefix="/staff", tags=["staff"])


def _download(filename: str, data: bytes, media_type: str) -> Response:
    return Response(
        content=data,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/departments", response_model=list[DepartmentWithAllocation])
async def list_departments(
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Departments + code-range fill (powers the create dialog's next-ID preview)."""
    return await staff_service.list_departments(session, branch_id)


@router.post("", response_model=StaffResponse)
async def create_staff(
    body: StaffCreate,
    request: Request,
    current_user: dict = Depends(
        require_roles(["super_admin", "branch_admin", "floor_coordinator"])
    ),
    session: AsyncSession = Depends(get_db),
):
    return await staff_service.create_staff(
        session, body, current_user["user_id"],
        request.client.host if request.client else None,
    )


@router.get("", response_model=list[StaffResponse])
async def list_staff(
    branch_id: uuid.UUID = Query(...),
    department_id: uuid.UUID | None = Query(None),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    return await staff_service.list_staff(session, branch_id, department_id)


@router.post("/bulk-delete", response_model=BulkDeleteSummary)
async def bulk_delete_staff(
    body: BulkStaffDelete,
    request: Request,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_manager_or_audit("Delete", "staff")),
    session: AsyncSession = Depends(get_db),
):
    """Soft-delete a selected set of staff. Literal path — before ``/{staff_id}``."""
    return await staff_service.bulk_delete_staff(
        session, branch_id, body.staff_ids, current_user["user_id"],
        request.client.host if request.client else None,
    )


@router.post("/sync-teachers")
async def sync_teachers(
    request: Request,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin"])),
    session: AsyncSession = Depends(get_db),
):
    """Backfill/refresh linked Staff rows for every teacher (MSA-Teachers).
    Idempotent — already-linked teachers are skipped. Literal path."""
    return await staff_service.sync_teachers_to_staff(
        session, branch_id, current_user["user_id"],
        request.client.host if request.client else None,
    )


@router.post("/import", response_model=ImportSummary)
async def import_staff(
    request: Request,
    file: UploadFile = File(...),
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin"])),
    session: AsyncSession = Depends(get_db),
):
    return await import_service.import_staff(
        session, file, branch_id, current_user["user_id"],
        request.client.host if request.client else None,
    )


@router.get("/reports")
async def download_staff_report(
    branch_id: uuid.UUID = Query(...),
    kind: str = Query(..., description="performance | present | absent | late_in | early_out | early_in | over_time | half_day | mis_punch | in_out | short_performance | gps_*"),
    frequency: str = Query("monthly", description="daily | weekly | monthly"),
    start: date = Query(...),
    end: date = Query(...),
    fmt: str = Query("pdf", description="pdf | xlsx"),
    department_ids: list[uuid.UUID] | None = Query(None),
    staff_ids: list[uuid.UUID] | None = Query(None),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Staff attendance report — the parameterized TeamOffice-style grid + typed
    list reports, department-wise or single-staff, as PDF or Excel. Literal path,
    before ``/{staff_id}``."""
    filename, data, mime = await staff_report_service.generate(
        session, branch_id=branch_id, kind=kind, frequency=frequency,
        department_ids=department_ids, staff_ids=staff_ids,
        start=start, end=end, fmt=fmt,
    )
    return _download(filename, data, mime)


@router.get("/faculty-activity")
async def download_faculty_activity(
    branch_id: uuid.UUID = Query(...),
    teacher_id: uuid.UUID = Query(...),
    day: date = Query(...),
    fmt: str = Query("pdf", description="pdf | xlsx"),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Daily Faculty Activity Report — a teacher's biometric IN/OUT joined with
    the lectures they delivered that day (scheduled vs effective, delays)."""
    filename, data, mime = await staff_faculty_service.daily_report(
        session, branch_id=branch_id, teacher_id=teacher_id, day=day, fmt=fmt,
    )
    return _download(filename, data, mime)


@router.get("/faculty-activity/summary")
async def download_faculty_summary(
    branch_id: uuid.UUID = Query(...),
    start: date = Query(...),
    end: date = Query(...),
    fmt: str = Query("pdf", description="pdf | xlsx"),
    teacher_ids: list[uuid.UUID] | None = Query(None),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Cumulative per-teacher summary (present days, work, lectures, delayed)."""
    filename, data, mime = await staff_faculty_service.summary_report(
        session, branch_id=branch_id, start=start, end=end,
        teacher_ids=teacher_ids, fmt=fmt,
    )
    return _download(filename, data, mime)


@router.get("/{staff_id}", response_model=StaffResponse)
async def get_staff(
    staff_id: uuid.UUID,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    return await staff_service.get_staff(session, staff_id, branch_id)


@router.get("/{staff_id}/photo")
async def staff_face_photo(
    staff_id: uuid.UUID,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """The staff member's enrolled face photo (JPEG) from the biometric backup,
    for the roster/profile avatar. Any signed-in user may view it (cookie auth, so
    an ``<img>`` works). 404 when we have no photo for this staff."""
    from fastapi import HTTPException, status

    from app.modules.attendance.services import provisioning_service
    from app.modules.staff.repositories import staff_repository

    staff = await staff_repository.get_by_id(session, staff_id)
    jpeg = (
        await provisioning_service.face_photo_by_uid(
            session, branch_id, staff.emp_code or ""
        )
        if staff is not None and staff.branch_id == branch_id
        else None
    )
    if jpeg is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No face photo.")
    return Response(
        content=jpeg,
        media_type="image/jpeg",
        headers={"Cache-Control": "private, max-age=300"},
    )


@router.patch("/{staff_id}", response_model=StaffResponse)
async def update_staff(
    staff_id: uuid.UUID,
    body: StaffUpdate,
    request: Request,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(
        require_roles(["super_admin", "branch_admin", "floor_coordinator"])
    ),
    session: AsyncSession = Depends(get_db),
):
    return await staff_service.update_staff(
        session, staff_id, body, branch_id, current_user["user_id"],
        request.client.host if request.client else None,
    )


@router.post("/{staff_id}/link-teacher", response_model=StaffResponse)
async def link_teacher(
    staff_id: uuid.UUID,
    body: LinkTeacherRequest,
    request: Request,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin"])),
    session: AsyncSession = Depends(get_db),
):
    return await staff_service.link_teacher(
        session, staff_id, body.teacher_id, branch_id, current_user["user_id"],
        request.client.host if request.client else None,
    )


@router.delete("/{staff_id}", status_code=204)
async def delete_staff(
    staff_id: uuid.UUID,
    request: Request,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_manager_or_audit("Delete", "staff")),
    session: AsyncSession = Depends(get_db),
):
    await staff_service.delete_staff(
        session, staff_id, branch_id, current_user["user_id"],
        request.client.host if request.client else None,
    )
