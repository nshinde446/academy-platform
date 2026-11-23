"""Shared helpers for the Weekend Plan + Star-System approval workflow.

Both record types (``WEEKEND_PLAN``, ``SELF_ASSESSMENT``) use the same approver
decision log, the same in-app notification inbox, the same approver resolution,
and the same weekend/holiday day-type rule. Keeping them here avoids drift
between the two flows. See docs/weekend-and-star-system-roadmap.md.
"""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models.auth_models import User
from app.modules.lectures.models.lecture_models import Holiday
from app.modules.staff.models.staff_models import Staff
from app.modules.teacher_portal.models.workflow_models import (
    ApproverLog,
    ApproverMapping,
    PortalNotification,
)

RECORD_WEEKEND_PLAN = "WEEKEND_PLAN"
RECORD_SELF_ASSESSMENT = "SELF_ASSESSMENT"

# Minimum approver comment length (SRD AP04).
MIN_COMMENT_LEN = 10


async def resolve_branch_id(session: AsyncSession, staff_id: uuid.UUID) -> uuid.UUID:
    """The signed-in teacher's own branch, read from their Staff row (never the
    request), so every write lands in the right branch (branch isolation)."""
    s = (await session.execute(
        select(Staff).where(Staff.id == staff_id)
    )).scalar_one_or_none()
    if s is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Staff not found")
    return s.branch_id


async def resolve_day_type(
    session: AsyncSession, *, branch_id: uuid.UUID, plan_date: date
) -> tuple[str, str | None]:
    """Return (day_type, holiday_name) for a date, or raise 400 if the date is a
    normal working day (BR-02 — only Saturdays, Sundays and academy holidays)."""
    holiday = (await session.execute(
        select(Holiday).where(
            Holiday.branch_id == branch_id,
            Holiday.holiday_date == plan_date,
            Holiday.is_deleted == False,  # noqa: E712
        )
    )).scalar_one_or_none()
    if holiday is not None:
        return "HOLIDAY", holiday.name
    wd = plan_date.weekday()
    if wd == 5:
        return "SATURDAY", None
    if wd == 6:
        return "SUNDAY", None
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="A weekend plan can only target a Saturday, Sunday or academy holiday.",
    )


async def resolve_approver(
    session: AsyncSession,
    *,
    staff_id: uuid.UUID,
    branch_id: uuid.UUID,
    chosen_approver_id: uuid.UUID | None,
) -> uuid.UUID | None:
    """Pick the approver for a submission (WP05, open-question 1 default).

    Precedence: the teacher's explicit choice (validated as a real user) → their
    default approver mapping → None. A None approver is fine: it stays visible to
    every approver in the branch inbox (Admin fallback)."""
    if chosen_approver_id is not None:
        exists = (await session.execute(
            select(User.id).where(User.id == chosen_approver_id)
        )).scalar_one_or_none()
        if exists is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown approver.")
        return chosen_approver_id

    mapping = (await session.execute(
        select(ApproverMapping).where(
            ApproverMapping.staff_id == staff_id,
            ApproverMapping.branch_id == branch_id,
            ApproverMapping.is_deleted == False,  # noqa: E712
        ).order_by(ApproverMapping.is_default.desc())
    )).scalars().first()
    return mapping.approver_user_id if mapping else None


async def log_action(
    session: AsyncSession,
    *,
    branch_id: uuid.UUID,
    record_type: str,
    record_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    action: str,
    comment: str | None = None,
) -> None:
    """Append one row to the permanent approver log (BR-06 — never deleted)."""
    session.add(ApproverLog(
        branch_id=branch_id,
        record_type=record_type,
        record_id=record_id,
        approver_user_id=actor_user_id,
        action=action,
        comment=(comment or None),
        created_by=actor_user_id,
    ))
    await session.flush()


async def notify(
    session: AsyncSession,
    *,
    branch_id: uuid.UUID,
    user_id: uuid.UUID | None,
    record_type: str,
    record_id: uuid.UUID,
    message: str,
    actor_user_id: uuid.UUID | None = None,
) -> None:
    """Queue an in-app notification (AP07; in-app only for v1). No-op if there's
    no recipient (e.g. an unassigned approver)."""
    if user_id is None:
        return
    session.add(PortalNotification(
        branch_id=branch_id,
        user_id=user_id,
        record_type=record_type,
        record_id=record_id,
        message=message,
        is_read=False,
        created_by=actor_user_id,
    ))
    await session.flush()


async def history_for(
    session: AsyncSession, *, record_type: str, record_id: uuid.UUID
) -> list[dict]:
    """The decision history for a submission (teacher History tab, AP-level).

    Resolves approver names for display."""
    logs = list((await session.execute(
        select(ApproverLog).where(
            ApproverLog.record_type == record_type,
            ApproverLog.record_id == record_id,
            ApproverLog.is_deleted == False,  # noqa: E712
        ).order_by(ApproverLog.created_at.asc())
    )).scalars().all())
    if not logs:
        return []
    user_ids = list({lg.approver_user_id for lg in logs})
    names = {
        u.id: f"{u.first_name} {u.last_name}".strip()
        for u in (await session.execute(
            select(User).where(User.id.in_(user_ids))
        )).scalars().all()
    }
    return [
        {
            "action": lg.action,
            "comment": lg.comment,
            "by": names.get(lg.approver_user_id),
            "at": lg.created_at,
        }
        for lg in logs
    ]
