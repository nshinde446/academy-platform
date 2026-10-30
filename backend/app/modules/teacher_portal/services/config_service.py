"""Teacher-portal settings, read from the ``teacher_portal_config`` key/value
table (migration 0067) with the spec defaults as fallback, so the portal works
even if a key was never seeded and the client can retune without a deploy."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models.auth_models import TeacherPortalConfig

# Spec section 0/2 defaults — the fallback when a key is missing from the table.
DEFAULTS: dict[str, object] = {
    "fine_visibility": "after_day_close",  # or "realtime"
    "day_close_time": "23:30",             # institute-local HH:MM
    "history_days": 90,
    "idle_timeout_minutes": 30,
    "max_session_hours": 8,
    "lockout_attempts": 5,
    "lockout_minutes": 15,
    "min_password_length": 8,
    "teacher_login_enabled": False,
    # Leave (Teacher Portal Changes §2/§3): how far back leave can be applied,
    # whether half-day leave is allowed, and the payroll present-days threshold
    # that the WOF balance accrues above.
    "leave_backdate_days": 7,
    "leave_half_day_allowed": True,
    "wof_required_days": 24,
}


async def get_config(session: AsyncSession) -> dict[str, object]:
    """All portal settings, DB values overriding the defaults."""
    rows = (await session.execute(select(TeacherPortalConfig))).scalars().all()
    cfg = dict(DEFAULTS)
    for r in rows:
        cfg[r.key] = r.value
    return cfg


async def get_value(session: AsyncSession, key: str) -> object:
    cfg = await get_config(session)
    return cfg.get(key, DEFAULTS.get(key))
