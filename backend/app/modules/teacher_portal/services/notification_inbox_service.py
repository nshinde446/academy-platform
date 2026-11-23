"""In-app notification inbox for the logged-in user (SRD AP07, Notification entity).

Serves both teachers (decision results) and approvers (new submissions). In-app
only for v1 (open-question 8). Everything is scoped to the current user's own
``user_id`` — a notification is only ever read/marked by its owner.
"""

from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.teacher_portal.models.workflow_models import PortalNotification


async def list_notifications(
    session: AsyncSession, *, user_id: uuid.UUID, only_unread: bool = False, limit: int = 50,
) -> list[dict]:
    q = select(PortalNotification).where(
        PortalNotification.user_id == user_id,
        PortalNotification.is_deleted == False,  # noqa: E712
    )
    if only_unread:
        q = q.where(PortalNotification.is_read == False)  # noqa: E712
    q = q.order_by(PortalNotification.created_at.desc()).limit(limit)
    rows = list((await session.execute(q)).scalars().all())
    return [
        {
            "id": n.id,
            "record_type": n.record_type,
            "record_id": n.record_id,
            "message": n.message,
            "is_read": n.is_read,
            "created_at": n.created_at,
        }
        for n in rows
    ]


async def unread_count(session: AsyncSession, *, user_id: uuid.UUID) -> int:
    return int((await session.execute(
        select(func.count()).select_from(PortalNotification).where(
            PortalNotification.user_id == user_id,
            PortalNotification.is_read == False,  # noqa: E712
            PortalNotification.is_deleted == False,  # noqa: E712
        )
    )).scalar_one())


async def mark_read(
    session: AsyncSession, *, user_id: uuid.UUID, notification_id: uuid.UUID,
) -> None:
    n = (await session.execute(
        select(PortalNotification).where(
            PortalNotification.id == notification_id,
            PortalNotification.user_id == user_id,
            PortalNotification.is_deleted == False,  # noqa: E712
        )
    )).scalar_one_or_none()
    if n is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found.")
    n.is_read = True
    await session.flush()


async def mark_all_read(session: AsyncSession, *, user_id: uuid.UUID) -> int:
    res = await session.execute(
        update(PortalNotification)
        .where(
            PortalNotification.user_id == user_id,
            PortalNotification.is_read == False,  # noqa: E712
            PortalNotification.is_deleted == False,  # noqa: E712
        )
        .values(is_read=True)
    )
    await session.flush()
    return res.rowcount or 0
