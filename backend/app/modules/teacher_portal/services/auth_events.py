"""Append-only writer for the ``auth_events`` login/account-activity log
(migration 0067). Distinct from the business audit log — this is the security
trail (logins, lockouts, IDOR attempts, account lifecycle)."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models.auth_models import AUTH_EVENT_TYPES, AuthEvent


async def record(
    session: AsyncSession,
    *,
    event: str,
    user_id: uuid.UUID | None = None,
    username_attempted: str | None = None,
    actor_id: uuid.UUID | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
    detail: str | None = None,
) -> None:
    """Append one auth event. ``event`` must be a recognised type; unknown types
    raise so a typo can't silently drop a security record."""
    if event not in AUTH_EVENT_TYPES:
        raise ValueError(f"unknown auth event '{event}'")
    session.add(AuthEvent(
        event=event, user_id=user_id, username_attempted=username_attempted,
        actor_id=actor_id, ip=ip, user_agent=(user_agent or "")[:400], detail=detail,
    ))
    await session.flush()
