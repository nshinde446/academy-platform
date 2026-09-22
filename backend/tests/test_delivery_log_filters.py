"""WhatsApp delivery-log filters + the case-insensitive channel fix.

The queued rows store ``channel='WHATSAPP'`` while the delivery log queries
``'whatsapp'`` — a case-sensitive match silently returned zero rows and blanked
the page. These tests lock in the case-insensitive match and the batch / free-text
/ date-range filters added on top of it.
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.modules.events.services import event_service
from app.modules.notifications.models.notification_models import NotificationTemplate
from app.modules.notifications.services import notification_service
from app.modules.student.models.student_models import Student, StudentBatchMapping


async def _seed_template(db_session, branch_id):
    db_session.add(NotificationTemplate(
        name="absent", event_type="STUDENT_ABSENT", channel="WHATSAPP",
        body_template="{student_name} was absent on {attendance_date}.",
        is_active=True, provider_template_name="attendance_absent_alert",
        provider_language="en", branch_id=branch_id,
    ))
    await db_session.flush()


async def _emit_absent(db_session, branch_id, student, name, recipient):
    await event_service.emit_event(
        db_session, event_type="STUDENT_ABSENT", branch_id=branch_id,
        student_id=student.id,
        metadata={"student_name": name, "attendance_date": "2026-09-22",
                  "recipient": recipient},
    )


@pytest.mark.usefixtures("seed_data")
async def test_channel_case_insensitive_and_batch_filter(db_session, seed_data):
    branch = seed_data["branch_a"].id
    batch, batch_b = seed_data["batch"], seed_data["batch_b"]
    s1 = seed_data["student"]
    await _seed_template(db_session, branch)

    # s1 -> batch, a new s2 -> batch_b, so batch filtering has something to split.
    db_session.add(StudentBatchMapping(
        student_id=s1.id, batch_id=batch.id, branch_id=branch, is_deleted=False))
    s2 = Student(first_name="Priya", last_name="More", branch_id=branch,
                 academic_year_id=seed_data["academic_year"].id,
                 parent_mobile="7000000002", enrollment_number="STU002",
                 status="active", is_deleted=False)
    db_session.add(s2)
    await db_session.flush()
    db_session.add(StudentBatchMapping(
        student_id=s2.id, batch_id=batch_b.id, branch_id=branch, is_deleted=False))
    await db_session.flush()

    await _emit_absent(db_session, branch, s1, "Rahul Sharma", "9000000001")
    await _emit_absent(db_session, branch, s2, "Priya More", "7000000002")
    await db_session.flush()

    r = await notification_service.consume_events(db_session)
    assert r["enqueued"] == 2

    # Rows are stored "WHATSAPP"; the service filters "whatsapp" — must still find
    # both (the regression this fixes).
    everyone = await notification_service.delivery_log(db_session, branch_id=branch)
    assert len(everyone) == 2
    assert all(r["parent_contact"] for r in everyone)

    # Batch filter resolves via the student's batch membership.
    only_batch = await notification_service.delivery_log(
        db_session, branch_id=branch, batch_id=batch.id)
    assert [r["student_name"] for r in only_batch] == ["Rahul Sharma"]


@pytest.mark.usefixtures("seed_data")
async def test_search_and_date_range_filters(db_session, seed_data):
    branch = seed_data["branch_a"].id
    s1 = seed_data["student"]
    await _seed_template(db_session, branch)
    await _emit_absent(db_session, branch, s1, "Rahul Sharma", "9123456789")
    await db_session.flush()
    await notification_service.consume_events(db_session)

    # q matches student name (case-insensitive) and parent number substring.
    assert len(await notification_service.delivery_log(
        db_session, branch_id=branch, q="rahul")) == 1
    assert len(await notification_service.delivery_log(
        db_session, branch_id=branch, q="9123")) == 1
    assert len(await notification_service.delivery_log(
        db_session, branch_id=branch, q="nobody")) == 0

    today = datetime.now(timezone.utc).date()
    # Inclusive window around today includes the just-created row.
    assert len(await notification_service.delivery_log(
        db_session, branch_id=branch, date_from=today, date_to=today)) == 1
    # A window starting in the future excludes it.
    assert len(await notification_service.delivery_log(
        db_session, branch_id=branch, date_from=today + timedelta(days=2))) == 0
