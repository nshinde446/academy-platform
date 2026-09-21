"""consume_events must not let no-template events (e.g. ATTENDANCE_MARKED, one per
punch) starve the ones that actually notify (STUDENT_ABSENT)."""

import pytest

from app.modules.events.services import event_service
from app.modules.notifications.models.notification_models import NotificationTemplate
from app.modules.notifications.services import notification_service


@pytest.mark.usefixtures("seed_data")
async def test_consume_skips_no_template_events_and_never_starves(db_session, seed_data):
    branch = seed_data["branch_a"].id
    db_session.add(NotificationTemplate(
        name="absent", event_type="STUDENT_ABSENT", channel="WHATSAPP",
        body_template="{student_name} was absent on {attendance_date}.",
        is_active=True, provider_template_name="attendance_absent_alert",
        provider_language="en", branch_id=branch,
    ))
    await db_session.flush()

    # 5 older no-template events, then 1 notifiable event.
    for _ in range(5):
        await event_service.emit_event(
            db_session, event_type="ATTENDANCE_MARKED", branch_id=branch,
            student_id=seed_data["student"].id, metadata={})
    await event_service.emit_event(
        db_session, event_type="STUDENT_ABSENT", branch_id=branch,
        student_id=seed_data["student"].id,
        metadata={"student_name": "Rahul", "attendance_date": "2026-06-22",
                  "recipient": "9876543210"})
    await db_session.flush()

    # Even with limit=1, the ATTENDANCE_MARKED flood must NOT crowd out the alert.
    r = await notification_service.consume_events(db_session, limit=1)
    assert r["consumed"] == 1 and r["enqueued"] == 1


@pytest.mark.usefixtures("seed_data")
async def test_consume_noop_when_no_active_templates(db_session, seed_data):
    branch = seed_data["branch_a"].id
    await event_service.emit_event(
        db_session, event_type="ATTENDANCE_MARKED", branch_id=branch,
        student_id=seed_data["student"].id, metadata={})
    await db_session.flush()
    r = await notification_service.consume_events(db_session, limit=100)
    assert r == {"consumed": 0, "enqueued": 0}
