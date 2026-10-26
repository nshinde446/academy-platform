"""Payroll module HTTP routes (Slice 1: settings only).

Month setup, the monthly report, the staff ledger and the extra-day request flow
land in later slices. Everything here is dormant behind ``payroll_enabled`` until
rollout, but the settings endpoints must work so the switch can be flipped.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.modules.audit.services import audit_service
from app.modules.auth.permissions.rbac import get_current_user, require_roles
from app.modules.payroll.schemas.config_schemas import PayrollConfigUpdate
from app.modules.payroll.schemas.payroll_schemas import (
    ExtraDayRequestCreate,
    ExtraDayRequestResponse,
    HolidayCreate,
    LedgerResponse,
    LifecycleAction,
    MonthSettingsResponse,
    MonthSettingsUpsert,
    RequestDecision,
    RequestHistoryRow,
    ReportResponse,
)
from app.modules.payroll.services import (
    config_service,
    export_service,
    month_service,
    report_service,
    request_service,
)

router = APIRouter(prefix="/payroll", tags=["payroll"])

# §9 role gates. super_admin is always allowed by require_roles.
# `payroll_admin` is the dedicated role that owns payroll (migration 0070) — the
# super-admin-equivalent *within* this module, allowed on every payroll action.
_ADMIN_ROLES = ["super_admin", "payroll_admin"]
_REPORT_ROLES = ["super_admin", "payroll_admin", "accounts", "branch_admin", "manager"]
# §9 "View staff ledger": Super Admin + Accounts/Branch Admin (not Manager/Teacher).
_LEDGER_ROLES = ["super_admin", "payroll_admin", "accounts", "branch_admin"]


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _download(filename: str, data: bytes, media_type: str) -> Response:
    return Response(
        content=data,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


async def _log_export(session, current_user, request, what: str, detail: dict) -> None:
    branch_raw = current_user.get("branch_id")
    await audit_service.log_action(
        session, user_id=current_user["user_id"], action=f"Export {what}",
        table_name="payroll", record_id=current_user["user_id"],
        new_values=detail, ip_address=_ip(request),
        branch_id=uuid.UUID(branch_raw) if branch_raw else None,
    )
    await session.commit()


@router.get("/config")
async def get_payroll_config(
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    """The effective payroll settings (DB values over spec defaults). Any
    authenticated user may view them; only the Super Admin may change them (§9)."""
    return await config_service.get_config(session)


@router.put("/config")
async def update_payroll_config(
    body: PayrollConfigUpdate,
    request: Request,
    current_user: dict = Depends(require_roles(_ADMIN_ROLES)),
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    """Change payroll settings (Super Admin only, §9). The before/after is written
    to the audit log."""
    changes = body.changes()
    before = await config_service.get_config(session)
    after = await config_service.set_values(
        session, changes, user_id=current_user["user_id"]
    )
    if changes:
        branch_raw = current_user.get("branch_id")
        await audit_service.log_action(
            session,
            user_id=current_user["user_id"],
            action="Update Payroll Settings",
            table_name="payroll_config",
            record_id=current_user["user_id"],
            old_values={k: before.get(k) for k in changes},
            new_values={k: after.get(k) for k in changes},
            ip_address=_ip(request),
            branch_id=uuid.UUID(branch_raw) if branch_raw else None,
        )
    await session.commit()
    return after


# ── Month setup + lifecycle (§1/§6) — Super Admin writes, all view ───────────

@router.get("/months", response_model=list[MonthSettingsResponse])
async def list_months(
    branch_id: uuid.UUID = Query(...),
    year: int | None = Query(default=None),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    return await month_service.list_months(session, branch_id, year)


@router.get("/months/{year}/{month}", response_model=MonthSettingsResponse)
async def get_month(
    year: int,
    month: int,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    return await month_service.get_month(session, branch_id, year, month)


@router.put("/months/{year}/{month}", response_model=MonthSettingsResponse)
async def upsert_month(
    year: int,
    month: int,
    body: MonthSettingsUpsert,
    request: Request,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(_ADMIN_ROLES)),
    session: AsyncSession = Depends(get_db),
):
    out = await month_service.upsert_month(
        session, branch_id=branch_id, year=year, month=month,
        required_days=body.required_days, notes=body.notes, reason=body.reason,
        user_id=current_user["user_id"], ip=_ip(request),
    )
    await session.commit()
    return out


@router.post("/months/{year}/{month}/holidays", response_model=MonthSettingsResponse)
async def add_holiday(
    year: int,
    month: int,
    body: HolidayCreate,
    request: Request,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(_ADMIN_ROLES)),
    session: AsyncSession = Depends(get_db),
):
    out = await month_service.add_holiday(
        session, branch_id=branch_id, year=year, month=month,
        holiday_date=body.holiday_date, title=body.title, kind=body.kind,
        credit_days=body.credit_days, user_id=current_user["user_id"], ip=_ip(request),
    )
    await session.commit()
    return out


@router.delete("/months/{year}/{month}/holidays/{holiday_id}", response_model=MonthSettingsResponse)
async def remove_holiday(
    year: int,
    month: int,
    holiday_id: uuid.UUID,
    request: Request,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(_ADMIN_ROLES)),
    session: AsyncSession = Depends(get_db),
):
    out = await month_service.remove_holiday(
        session, branch_id=branch_id, holiday_id=holiday_id,
        user_id=current_user["user_id"], ip=_ip(request),
    )
    await session.commit()
    return out


@router.post("/months/{year}/{month}/{verb}", response_model=MonthSettingsResponse)
async def change_lifecycle(
    year: int,
    month: int,
    verb: str,
    body: LifecycleAction,
    request: Request,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(_ADMIN_ROLES)),
    session: AsyncSession = Depends(get_db),
):
    """Close, lock or reopen a month (§6). Super Admin only; reopen needs a
    reason. Everything is audited and later months recomputed where needed."""
    from fastapi import HTTPException

    if verb not in ("close", "lock", "reopen"):
        raise HTTPException(status_code=404, detail="Unknown month action")
    out = await month_service.change_lifecycle(
        session, branch_id=branch_id, year=year, month=month, verb=verb,
        reason=body.reason, user_id=current_user["user_id"], ip=_ip(request),
    )
    await session.commit()
    return out


# ── Monthly report + staff ledger (§7/§4) ────────────────────────────────────

@router.get("/report", response_model=ReportResponse)
async def monthly_report(
    year: int = Query(...),
    month: int = Query(..., ge=1, le=12),
    branch_id: uuid.UUID = Query(...),
    department_id: uuid.UUID | None = Query(default=None),
    staff_id: uuid.UUID | None = Query(default=None),
    current_user: dict = Depends(require_roles(_REPORT_ROLES)),
    session: AsyncSession = Depends(get_db),
):
    return await report_service.monthly_report(
        session, branch_id=branch_id, year=year, month=month,
        department_id=department_id, staff_id=staff_id,
    )


@router.get("/report/export")
async def export_report(
    request: Request,
    year: int = Query(...),
    month: int = Query(..., ge=1, le=12),
    branch_id: uuid.UUID = Query(...),
    fmt: str = Query("pdf"),
    department_id: uuid.UUID | None = Query(default=None),
    staff_id: uuid.UUID | None = Query(default=None),
    current_user: dict = Depends(require_roles(_REPORT_ROLES)),
    session: AsyncSession = Depends(get_db),
):
    """Monthly report as PDF or Excel (§7). Access-checked and logged."""
    name, data, media = await export_service.report(
        session, branch_id=branch_id, year=year, month=month, fmt=fmt,
        department_id=department_id, staff_id=staff_id,
    )
    await _log_export(
        session, current_user, request, "Payroll Report",
        {"year": year, "month": month, "fmt": fmt},
    )
    return _download(name, data, media)


@router.get("/staff/{staff_id}/ledger", response_model=LedgerResponse)
async def staff_ledger(
    staff_id: uuid.UUID,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(_LEDGER_ROLES)),
    session: AsyncSession = Depends(get_db),
):
    return await report_service.staff_ledger(
        session, branch_id=branch_id, staff_id=staff_id
    )


@router.get("/staff/{staff_id}/ledger/export")
async def export_ledger(
    staff_id: uuid.UUID,
    request: Request,
    branch_id: uuid.UUID = Query(...),
    fmt: str = Query("pdf"),
    current_user: dict = Depends(require_roles(_LEDGER_ROLES)),
    session: AsyncSession = Depends(get_db),
):
    """Staff carry-forward ledger as PDF or Excel (§4). Access-checked and logged."""
    name, data, media = await export_service.ledger(
        session, branch_id=branch_id, staff_id=staff_id, fmt=fmt
    )
    await _log_export(
        session, current_user, request, "Payroll Ledger",
        {"staff_id": str(staff_id), "fmt": fmt},
    )
    return _download(name, data, media)


# ── Extra-day requests (§5) ──────────────────────────────────────────────────
# Role checks are config-driven (payroll_config), so these use get_current_user
# and the service verifies the raiser/approver roles against settings.

@router.get("/requests", response_model=list[ExtraDayRequestResponse])
async def list_requests(
    branch_id: uuid.UUID = Query(...),
    status: str | None = Query(default=None),
    staff_id: uuid.UUID | None = Query(default=None),
    current_user: dict = Depends(require_roles(_REPORT_ROLES)),
    session: AsyncSession = Depends(get_db),
):
    return await request_service.list_requests(
        session, branch_id=branch_id, status=status, staff_id=staff_id
    )


@router.post("/requests", response_model=ExtraDayRequestResponse)
async def raise_request(
    body: ExtraDayRequestCreate,
    request: Request,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    out = await request_service.raise_request(
        session, branch_id=branch_id, staff_id=body.staff_id,
        source_year=body.source_year, source_month=body.source_month,
        shortfall_days=body.shortfall_days, note=body.note,
        roles=current_user.get("roles", []), user_id=current_user["user_id"],
        ip=_ip(request),
    )
    await session.commit()
    return out


@router.get("/requests/{request_id}/history", response_model=list[RequestHistoryRow])
async def request_history(
    request_id: uuid.UUID,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(_REPORT_ROLES)),
    session: AsyncSession = Depends(get_db),
):
    return await request_service.history(
        session, branch_id=branch_id, request_id=request_id
    )


@router.post("/requests/{request_id}/{verb}", response_model=ExtraDayRequestResponse)
async def decide_request(
    request_id: uuid.UUID,
    verb: str,
    body: RequestDecision,
    request: Request,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Approve, reject or cancel a request (§5). Approve/reject are gated by the
    configured approver role (Super Admin by default); cancel is the raiser's."""
    from fastapi import HTTPException

    common = dict(
        branch_id=branch_id, request_id=request_id,
        roles=current_user.get("roles", []), user_id=current_user["user_id"],
        note=body.note, ip=_ip(request),
    )
    if verb == "approve":
        out = await request_service.approve(session, **common)
    elif verb == "reject":
        out = await request_service.reject(session, **common)
    elif verb == "cancel":
        out = await request_service.cancel(
            session, branch_id=branch_id, request_id=request_id,
            user_id=current_user["user_id"], note=body.note, ip=_ip(request),
        )
    else:
        raise HTTPException(status_code=404, detail="Unknown request action")
    await session.commit()
    return out
