"""Payroll module HTTP routes (Slice 1: settings only).

Month setup, the monthly report, the staff ledger and the extra-day request flow
land in later slices. Everything here is dormant behind ``payroll_enabled`` until
rollout, but the settings endpoints must work so the switch can be flipped.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.modules.audit.services import audit_service
from app.modules.auth.permissions.rbac import get_current_user, require_roles
from app.modules.payroll.schemas.config_schemas import PayrollConfigUpdate
from app.modules.payroll.services import config_service

router = APIRouter(prefix="/payroll", tags=["payroll"])


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
        import uuid as _uuid

        await audit_service.log_action(
            session,
            user_id=current_user["user_id"],
            action="Update Payroll Settings",
            table_name="payroll_config",
            record_id=current_user["user_id"],
            old_values={k: before.get(k) for k in changes},
            new_values={k: after.get(k) for k in changes},
            ip_address=request.client.host if request.client else None,
            branch_id=_uuid.UUID(branch_raw) if branch_raw else None,
        )
    await session.commit()
    return after
