"""Payroll module HTTP routes (Slice 1: settings only).

Month setup, the monthly report, the staff ledger and the extra-day request flow
land in later slices. Everything here is dormant behind ``payroll_enabled`` until
rollout, but the settings endpoints must work so the switch can be flipped.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.modules.audit.services import audit_service
from app.modules.auth.permissions.rbac import get_current_user, require_roles
from app.modules.payroll.schemas.config_schemas import PayrollConfigUpdate
from app.modules.payroll.schemas.payroll_schemas import (
    HolidayCreate,
    LedgerResponse,
    LifecycleAction,
    MonthSettingsResponse,
    MonthSettingsUpsert,
    ReportResponse,
)
from app.modules.payroll.services import (
    config_service,
    month_service,
    report_service,
)

router = APIRouter(prefix="/payroll", tags=["payroll"])

# §9 role gates. super_admin is always allowed by require_roles.
_REPORT_ROLES = ["super_admin", "accounts", "branch_admin", "manager"]
_LEDGER_ROLES = ["super_admin", "accounts"]


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


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
    current_user: dict = Depends(require_roles(["super_admin"])),
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
    current_user: dict = Depends(require_roles(["super_admin"])),
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
    current_user: dict = Depends(require_roles(["super_admin"])),
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
    current_user: dict = Depends(require_roles(["super_admin"])),
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
    current_user: dict = Depends(require_roles(["super_admin"])),
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
