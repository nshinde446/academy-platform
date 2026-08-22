"""PR-B notification module — WhatsApp master toggle + lecture-reminder sender.

Covers the per-branch master toggle (settings CRUD + the process_queue gate) and
the morning lecture-reminder emitter (one event per student with lectures today,
idempotent, gated by the toggle in the beat task).
"""

import json
import uuid
from datetime import date, datetime, timezone

from httpx import AsyncClient
from sqlalchemy import select

from app.modules.attendance.jobs import tasks
from app.modules.attendance.services import daily_service
from app.modules.events.models.event_models import AcademicEvent
from app.modules.lectures.models.lecture_models import Lecture
from app.modules.notifications.models.notification_models import (
    NotificationQueue,
    NotificationTemplate,
)
from app.modules.notifications.repositories import notification_repository
from app.modules.notifications.services import notification_service
from app.modules.student.models.student_models import Student, StudentBatchMapping

BRANCH_A_ID = "00000000-0000-0000-0000-000000000001"
DAY = date(2026, 6, 22)
IST = "Asia/Kolkata"


async def _login_admin(client: AsyncClient):
    resp = await client.post("/api/v1/auth/login", json={
        "email": "admin@test.com", "password": "Admin123!",
    })
    assert resp.status_code == 200


# ─── master toggle: settings CRUD ───────────────────────────────────────────

async def test_settings_whatsapp_toggle_default_and_persist(client, seed_data):
    await _login_admin(client)
    resp = await client.get(
        "/api/v1/notifications/settings", params={"branch_id": BRANCH_A_ID}
    )
    assert resp.status_code == 200
    assert resp.json()["whatsapp_enabled"] is False  # default off

    resp = await client.put(
        "/api/v1/notifications/settings",
        params={"branch_id": BRANCH_A_ID},
        json={"whatsapp_enabled": True},
    )
    assert resp.status_code == 200
    assert resp.json()["whatsapp_enabled"] is True

    resp = await client.get(
        "/api/v1/notifications/settings", params={"branch_id": BRANCH_A_ID}
    )
    assert resp.json()["whatsapp_enabled"] is True


# ─── master toggle: process_queue gate ──────────────────────────────────────

def _wa_template(branch_id):
    return NotificationTemplate(
        name="absent", event_type="STUDENT_ABSENT", channel="WHATSAPP",
        body_template="{student_name} was absent on {attendance_date}.",
        is_active=True, provider_template_name="attendance_absent_alert",
        provider_language="en", branch_id=branch_id,
    )


def _wa_item(template_id, branch_id):
    return NotificationQueue(
        template_id=template_id, recipient="9876543210", channel="WHATSAPP",
        payload_json=json.dumps({"student_name": "Rahul", "attendance_date": "2026-06-22"}),
        delivery_status="PENDING", branch_id=branch_id,
    )


class _FakeEnv:
    WHATSAPP_ENABLED = True
    WHATSAPP_ACCESS_TOKEN = "tok"
    WHATSAPP_PHONE_NUMBER_ID = "123"
    WHATSAPP_API_VERSION = "v21.0"


async def test_process_queue_sends_when_branch_toggle_on(
    client, seed_data, db_session, monkeypatch
):
    branch_id = uuid.UUID(BRANCH_A_ID)
    await notification_repository.upsert_settings(
        db_session, branch_id, whatsapp_enabled=True
    )
    tmpl = _wa_template(branch_id)
    db_session.add(tmpl)
    await db_session.flush()
    db_session.add(_wa_item(tmpl.id, branch_id))
    await db_session.commit()

    monkeypatch.setattr(notification_service, "get_settings", lambda: _FakeEnv())
    sent = {}

    async def fake_send(**kwargs):
        sent.update(kwargs)
        return "wamid.OK"

    monkeypatch.setattr(
        notification_service.whatsapp_client, "send_template_message", fake_send
    )

    result = await notification_service.process_queue(db_session)
    await db_session.commit()
    assert result["sent"] >= 1
    assert sent["to"] == "919876543210"


async def test_process_queue_skips_when_branch_toggle_off(
    client, seed_data, db_session, monkeypatch
):
    branch_id = uuid.UUID(BRANCH_A_ID)
    # No settings row -> whatsapp_enabled defaults off.
    tmpl = _wa_template(branch_id)
    db_session.add(tmpl)
    await db_session.flush()
    item = _wa_item(tmpl.id, branch_id)
    db_session.add(item)
    await db_session.commit()

    monkeypatch.setattr(notification_service, "get_settings", lambda: _FakeEnv())
    result = await notification_service.process_queue(db_session)
    await db_session.commit()
    assert result["skipped"] >= 1
    await db_session.refresh(item)
    assert item.delivery_status == "PENDING"


# ─── lecture-reminder emitter ───────────────────────────────────────────────

async def _build_lecture_day(db_session, seed_data):
    branch = seed_data["branch_a"]
    batch = seed_data["batch"]
    student = seed_data["student"]
    student.parent_mobile = "9876500001"
    db_session.add(StudentBatchMapping(
        student_id=student.id, batch_id=batch.id, branch_id=branch.id,
        status="active", is_deleted=False,
    ))
    db_session.add(Lecture(
        teacher_id=seed_data["teacher"].id, batch_id=batch.id,
        subject_id=seed_data["subject"].id,
        academic_year_id=seed_data["academic_year"].id,
        scheduled_start=datetime(2026, 6, 22, 4, 30, tzinfo=timezone.utc),
        scheduled_end=datetime(2026, 6, 22, 6, 30, tzinfo=timezone.utc),
        branch_id=branch.id, status="active", is_deleted=False,
    ))
    await db_session.commit()
    return branch, student


async def test_lecture_reminders_emit_per_student(client, seed_data, db_session):
    branch, student = await _build_lecture_day(db_session, seed_data)
    emitted = await daily_service.run_lecture_reminders(
        db_session, branch_id=branch.id, day=DAY, tz_name=IST,
    )
    await db_session.commit()
    assert len(emitted) == 1
    meta = json.loads(emitted[0].metadata_json)
    assert meta["student_name"]
    assert meta["subjects"]  # the day's subject name(s)
    assert meta["recipient"] == "9876500001"


async def test_lecture_reminders_idempotent(client, seed_data, db_session):
    branch, _ = await _build_lecture_day(db_session, seed_data)
    first = await daily_service.run_lecture_reminders(
        db_session, branch_id=branch.id, day=DAY, tz_name=IST,
    )
    await db_session.commit()
    assert len(first) == 1
    second = await daily_service.run_lecture_reminders(
        db_session, branch_id=branch.id, day=DAY, tz_name=IST,
    )
    await db_session.commit()
    assert second == []


async def test_reminder_beat_gated_on_toggle(client, seed_data, db_session):
    branch, _ = await _build_lecture_day(db_session, seed_data)
    # 07:30 IST on DAY -> due; but toggle off -> no events.
    await tasks.send_lecture_reminders_for_due_branches(
        db_session, datetime(2026, 6, 22, 2, 0, tzinfo=timezone.utc)
    )
    await db_session.commit()
    none = (await db_session.execute(
        select(AcademicEvent).where(AcademicEvent.event_type == "LECTURE_REMINDER")
    )).scalars().all()
    assert none == []

    # Turn the master toggle on -> the due branch emits.
    await notification_repository.upsert_settings(
        db_session, branch.id, whatsapp_enabled=True
    )
    await db_session.commit()
    await tasks.send_lecture_reminders_for_due_branches(
        db_session, datetime(2026, 6, 22, 2, 0, tzinfo=timezone.utc)
    )
    await db_session.commit()
    some = (await db_session.execute(
        select(AcademicEvent).where(AcademicEvent.event_type == "LECTURE_REMINDER")
    )).scalars().all()
    assert len(some) == 1
