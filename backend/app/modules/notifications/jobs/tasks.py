"""Celery task for the notification pipeline.

One periodic job drives the whole delivery path in two steps against a single
session:

1. ``consume_events`` — turn freshly emitted ``AcademicEvent`` rows (e.g. the
   nightly absent sweep's ``STUDENT_ABSENT``) into queued notifications.
2. ``process_queue`` — deliver PENDING queue rows through their channel's sender
   (WhatsApp via the Meta Cloud API; EMAIL/SMS/PUSH still log-only).

Safe to schedule unconditionally: WhatsApp sends are gated behind
``WHATSAPP_ENABLED`` (default off), so while that's false WHATSAPP rows are left
PENDING and no Meta charge is ever incurred — flip the flag on and the next
drain flushes them.

Run (worker registers the task via celery_app imports)::

    celery -A app.core.jobs.celery_app.celery_app worker -B -l info
"""

from __future__ import annotations

import asyncio

from app.core.database.session import async_session_factory
from app.core.jobs.celery_app import celery_app
from app.modules.notifications.services import notification_service


async def _run_pipeline() -> dict:
    async with async_session_factory() as session:
        consumed = await notification_service.consume_events(session)
        processed = await notification_service.process_queue(session)
        await session.commit()
    return {**consumed, **processed}


@celery_app.task(name="notifications.process_pipeline")
def process_notification_queue() -> dict:
    """Beat entrypoint — consume events then drain the notification queue."""
    return asyncio.run(_run_pipeline())
