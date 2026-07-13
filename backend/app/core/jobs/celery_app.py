"""Celery application + beat schedule.

This is the previously-missing infra: the codebase had Celery installed and
orphan task stubs but no app factory, no beat, no worker. The first real
periodic job is the nightly absent sweep (per branch, at that branch's local
23:30). Run with:

    celery -A app.core.jobs.celery_app.celery_app worker -B -l info

``-B`` runs the embedded beat scheduler. The sweep beat fires every 15 minutes;
each run marks only the branches whose *local* time is in the 23:00–23:59 hour,
and the sweep is idempotent so repeated firings in that window are harmless.
"""

from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from app.core.config.settings import get_settings

settings = get_settings()

celery_app = Celery(
    "academy",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Beat itself ticks in UTC; per-branch local 23:30 is resolved inside the
    # task from each branch's timezone.
    beat_schedule={
        "attendance-nightly-absent-sweep": {
            "task": "attendance.nightly_absent_sweep",
            "schedule": crontab(minute="*/15"),
        },
        # eTimeOffice is cloud/pull — poll its rolling lookback every 10 min.
        # No-op when ETO_ENABLED is false, so it's safe to always schedule.
        "attendance-etimeoffice-poll": {
            "task": "attendance.etimeoffice_poll",
            "schedule": crontab(minute="*/10"),
        },
        # SmartOffice is cloud/pull too — poll every 2 min for near-real-time
        # attendance. No-op when SMARTOFFICE_ENABLED is false, so always safe to
        # schedule; dedup makes the overlapping windows harmless.
        "attendance-smartoffice-poll": {
            "task": "attendance.smartoffice_poll",
            "schedule": crontab(minute="*/2"),
        },
    },
    # Explicit import so the worker registers our tasks without autodiscover.
    imports=("app.modules.attendance.jobs.tasks",),
)
