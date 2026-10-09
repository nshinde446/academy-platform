"""Fees Celery tasks — the daily auto-overdue sweep (spec §8 / note #7).

Early each morning (per branch-local date) any PENDING installment whose due date
has passed is flipped to OVERDUE, so the follow-up lists read correctly when the
accounts team logs in. The sweep is idempotent — re-running it is a no-op.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import async_session_factory
from app.core.jobs.celery_app import celery_app
from app.core.jobs.run import run_task
from app.modules.attendance.time_utils import get_tz
from app.modules.auth.models.auth_models import Branch
from app.modules.fees.services import followup_service

logger = logging.getLogger(__name__)

# The sweep runs during this local hour (nominal 06:00). Beat fires hourly; the
# firing that lands in this local hour triggers it, and it is idempotent.
SWEEP_LOCAL_HOUR = 6


async def sweep_overdue(
    session: AsyncSession, now_utc: datetime
) -> list[tuple[uuid.UUID, date, int]]:
    """Flip past-due PENDING installments to OVERDUE for every branch currently in
    its local sweep hour. Returns (branch_id, local_date, count) per branch."""
    branches = (await session.execute(
        select(Branch.id, Branch.timezone).where(Branch.is_deleted == False)  # noqa: E712
    )).all()
    swept: list[tuple[uuid.UUID, date, int]] = []
    for branch_id, tz_name in branches:
        local = now_utc.astimezone(get_tz(tz_name))
        if local.hour != SWEEP_LOCAL_HOUR:
            continue
        n = await followup_service.mark_overdue(session, branch_id, local.date())
        swept.append((branch_id, local.date(), n))
    return swept


async def _run_overdue_sweep(now_utc: datetime | None = None):
    now = now_utc or datetime.now(timezone.utc)
    async with async_session_factory() as session:
        result = await sweep_overdue(session, now)
        await session.commit()
    return [(str(b), d.isoformat(), n) for b, d, n in result]


@celery_app.task(name="fees.mark_overdue")
def mark_overdue():
    """Beat entrypoint — mark past-due installments OVERDUE for branches at 06:00 local."""
    return run_task(_run_overdue_sweep)
