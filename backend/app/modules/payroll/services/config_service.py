"""Payroll settings, read from the ``payroll_config`` key/value table (migration
0069) with the spec §8 defaults as fallback, so payroll works even if a key was
never seeded and the client can retune every decision without a deploy. Mirrors
``teacher_portal.services.config_service``."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.payroll.models.payroll_models import PayrollConfig

# Spec §8 "Decisions and proposed defaults" — the fallback when a key is missing.
# Each is overridable from the Payroll Settings screen (Slice 7).
DEFAULTS: dict[str, object] = {
    # Master kill-switch. Dormant until the rollout flips it (§14).
    "payroll_enabled": False,
    # Do paid leaves/holidays reduce required days or count as present?
    #   "credited" (default) | "reduce_required"
    "holiday_treatment": "credited",
    # Half days and fractions: allowed in 0.5 steps (default) or whole days only.
    "allow_half_day": True,
    # Carry-forward: no expiry, cap 5 days, no payout, never negative.
    "carry_forward_cap": 5,
    "carry_forward_expiry_months": 0,  # 0 = no expiry
    "allow_payout": False,
    "allow_negative_balance": False,
    # Shortfall when a request is not approved: "unpaid" (LWP) | "absent".
    "unapproved_shortfall": "unpaid",
    # Who raises / approves extra-day requests (super_admin is always allowed).
    "request_raiser_roles": ["accounts", "branch_admin"],
    "request_approver_role": "super_admin",
    "allow_manager_approver": False,
    # Staff joining / leaving mid-month: prorate required days, rounded to 0.5.
    "prorate_on_join_leave": True,
    "prorate_rounding": 0.5,
}


async def get_config(session: AsyncSession) -> dict[str, object]:
    """All payroll settings, DB values overriding the defaults."""
    rows = (await session.execute(select(PayrollConfig))).scalars().all()
    cfg = dict(DEFAULTS)
    for r in rows:
        cfg[r.key] = r.value
    return cfg


async def get_value(session: AsyncSession, key: str) -> object:
    cfg = await get_config(session)
    return cfg.get(key, DEFAULTS.get(key))


async def is_enabled(session: AsyncSession) -> bool:
    """The payroll master switch. False until rollout (§14)."""
    return bool(await get_value(session, "payroll_enabled"))


async def set_values(
    session: AsyncSession,
    values: dict[str, object],
    *,
    user_id: uuid.UUID | None,
) -> dict[str, object]:
    """Upsert the given keys (only recognised ones), stamping who/when. Returns
    the full effective config. Unknown keys are ignored so a stale client can't
    write arbitrary rows."""
    now = datetime.now(timezone.utc)
    existing = {
        r.key: r for r in (await session.execute(select(PayrollConfig))).scalars().all()
    }
    for key, value in values.items():
        if key not in DEFAULTS:
            continue
        row = existing.get(key)
        if row is None:
            session.add(
                PayrollConfig(key=key, value=value, updated_by=user_id, updated_at=now)
            )
        else:
            row.value = value
            row.updated_by = user_id
            row.updated_at = now
    await session.flush()
    return await get_config(session)
