"""Celery tasks for day-attendance.

The scheduling decision (which branches are 'due' for a sweep right now) is a
pure function so it's unit-testable without Celery or Redis. The async sweep
core takes an injected session so tests drive it against the test DB.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import async_session_factory
from app.core.jobs.celery_app import celery_app
from app.modules.attendance.services import daily_service
from app.modules.attendance.time_utils import get_tz
from app.modules.auth.models.auth_models import Branch
from app.modules.notifications.repositories import notification_repository

logger = logging.getLogger(__name__)

# The nightly sweep runs during this local hour (nominal 23:30). Beat fires
# every 15 min; whichever firing lands in 23:00–23:59 local triggers it, and the
# sweep is idempotent so extra firings in the window are no-ops.
SWEEP_LOCAL_HOUR = 23


def is_branch_due(now_utc: datetime, tz_name: str | None) -> tuple[bool, date]:
    """(is this branch in its sweep hour now?, the branch-local date to sweep)."""
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)
    local = now_utc.astimezone(get_tz(tz_name))
    return local.hour == SWEEP_LOCAL_HOUR, local.date()


async def sweep_due_branches(
    session: AsyncSession, now_utc: datetime
) -> list[tuple[uuid.UUID, date, int]]:
    """Run the absent sweep for every branch currently in its local sweep hour.

    Returns (branch_id, local_date, num_marked_absent) per swept branch.
    """
    branches = (await session.execute(
        select(Branch.id, Branch.timezone).where(Branch.is_deleted == False)
    )).all()

    swept: list[tuple[uuid.UUID, date, int]] = []
    for branch_id, tz_name in branches:
        due, local_date = is_branch_due(now_utc, tz_name)
        if not due:
            continue
        created = await daily_service.run_absent_sweep(
            session, branch_id=branch_id, day=local_date, tz_name=tz_name
        )
        # Daily parent digest, only for branches that switched it on. Runs after
        # the sweep so every student has a resolved day status. Side-effect of
        # the sweep run; kept out of the return tuple to preserve its contract.
        settings = await notification_repository.get_settings(session, branch_id)
        if settings and settings.daily_digest_enabled:
            events = await daily_service.run_daily_digest(
                session, branch_id=branch_id, day=local_date,
                scope=settings.daily_digest_scope, tz_name=tz_name,
            )
            logger.info(
                "daily digest emitted: branch=%s day=%s scope=%s count=%d",
                branch_id, local_date, settings.daily_digest_scope, len(events),
            )
        swept.append((branch_id, local_date, len(created)))
    return swept


async def _run_nightly_sweep(now_utc: datetime | None = None):
    now = now_utc or datetime.now(timezone.utc)
    async with async_session_factory() as session:
        result = await sweep_due_branches(session, now)
        await session.commit()
    return [(str(b), d.isoformat(), n) for b, d, n in result]


@celery_app.task(name="attendance.nightly_absent_sweep")
def nightly_absent_sweep():
    """Beat entrypoint — marks absent for branches at their local 23:30."""
    return asyncio.run(_run_nightly_sweep())


async def _rebuild_one(student_id: uuid.UUID, branch_id: uuid.UUID, day: date):
    async with async_session_factory() as session:
        await daily_service.rebuild_daily(
            session, student_id=student_id, branch_id=branch_id, day=day
        )
        await session.commit()


@celery_app.task(name="attendance.rebuild_student_day")
def rebuild_student_day(student_id: str, branch_id: str, day_iso: str):
    """Near-real-time: recompute one student's day after a punch ingest."""
    return asyncio.run(
        _rebuild_one(uuid.UUID(student_id), uuid.UUID(branch_id), date.fromisoformat(day_iso))
    )


# ── eTimeOffice cloud poll ──────────────────────────────────────────────────
# eTimeOffice is pull-based (their cloud holds the punches), so unlike BioMax
# (which pushes) we poll it on a schedule. The job re-pulls a short lookback
# window every tick; ingest dedup makes the overlap harmless.


async def _run_eto_poll() -> dict:
    from app.core.config.settings import get_settings
    from app.modules.attendance.integrations.etimeoffice import service as eto_service

    settings = get_settings()
    if not settings.ETO_ENABLED or not settings.ETO_BRANCH_ID:
        return {"skipped": "eTimeOffice disabled or ETO_BRANCH_ID unset"}

    branch_id = uuid.UUID(settings.ETO_BRANCH_ID)
    async with async_session_factory() as session:
        summary = await eto_service.sync_recent(session, branch_id=branch_id)
        await session.commit()
    return summary


@celery_app.task(name="attendance.etimeoffice_poll")
def etimeoffice_poll():
    """Beat entrypoint — pull recent eTimeOffice punches for the configured branch."""
    return asyncio.run(_run_eto_poll())


# ── SmartOffice cloud poll ──────────────────────────────────────────────────
# SmartOffice is pull-based (the ZKTeco devices push to its server, we poll its
# REST API), so like eTimeOffice we poll a short lookback window every tick. The
# tighter the beat interval, the closer to real time; ingest dedup makes the
# overlap between polls harmless.


async def _run_smartoffice_poll() -> dict:
    from app.core.config.settings import get_settings
    from app.modules.attendance.integrations.smartoffice import service as so_service

    settings = get_settings()
    if not settings.SMARTOFFICE_ENABLED or not settings.SMARTOFFICE_BRANCH_ID:
        return {"skipped": "SmartOffice disabled or SMARTOFFICE_BRANCH_ID unset"}

    branch_id = uuid.UUID(settings.SMARTOFFICE_BRANCH_ID)
    async with async_session_factory() as session:
        summary = await so_service.sync_recent(session, branch_id=branch_id)
        await session.commit()
    return summary


@celery_app.task(name="attendance.smartoffice_poll")
def smartoffice_poll():
    """Beat entrypoint — pull recent SmartOffice punches for the configured branch."""
    return asyncio.run(_run_smartoffice_poll())
