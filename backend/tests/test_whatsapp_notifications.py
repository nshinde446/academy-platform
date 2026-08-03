"""WhatsApp (Meta Cloud API) notification path.

Covers the pure helpers, the HTTP client against a mocked transport (no live
Meta calls, ever), channel dispatch in send_notification, the disabled-flag
no-op, and the event->queue consumer that bridges the absent sweep to delivery.
"""

import json
import uuid

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.events.services import event_service
from app.modules.notifications.integrations.whatsapp import client as wa
from app.modules.notifications.models.notification_models import (
    NotificationQueue,
    NotificationTemplate,
)
from app.modules.notifications.services import notification_service

BRANCH_A_ID = "00000000-0000-0000-0000-000000000001"


# ─── Pure helpers ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("raw,expected", [
    ("9876543210", "919876543210"),        # bare 10-digit -> prefix 91
    ("+91 98765 43210", "919876543210"),    # already has cc, strip formatting
    ("098765 43210", "919876543210"),       # trunk 0 -> drop, add cc
    ("91-98765-43210", "919876543210"),
    ("", None),                              # empty
    ("12345", None),                         # too short
    ("9" * 20, None),                        # too long
])
def test_normalize_recipient(raw, expected):
    assert wa.normalize_recipient(raw) == expected


def test_build_template_payload_shape():
    payload = wa.build_template_payload(
        to="919876543210",
        template_name="attendance_absent_alert",
        language="en",
        body_params=["Rahul", "03 Aug 2026"],
    )
    assert payload["messaging_product"] == "whatsapp"
    assert payload["to"] == "919876543210"
    assert payload["type"] == "template"
    assert payload["template"]["name"] == "attendance_absent_alert"
    assert payload["template"]["language"] == {"code": "en"}
    params = payload["template"]["components"][0]["parameters"]
    assert [p["text"] for p in params] == ["Rahul", "03 Aug 2026"]


def test_build_template_payload_no_params_omits_components():
    payload = wa.build_template_payload(
        to="919876543210", template_name="t", language="en", body_params=[],
    )
    assert "components" not in payload["template"]


def test_ordered_body_params_follows_body_template():
    body = "Dear parent, {student_name} was ABSENT on {attendance_date}."
    payload = {"student_name": "Rahul", "attendance_date": "03 Aug 2026", "extra": "x"}
    assert notification_service._ordered_body_params(body, payload) == [
        "Rahul", "03 Aug 2026",
    ]


def test_ordered_body_params_missing_key_is_blank():
    assert notification_service._ordered_body_params("{a} {b}", {"a": "x"}) == ["x", ""]


# ─── HTTP client against a mocked transport ─────────────────────────────────

async def _send_with_transport(handler) -> str:
    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as c:
        return await wa.send_template_message(
            access_token="tok", phone_number_id="123", api_version="v21.0",
            to="919876543210", template_name="t", language="en",
            body_params=["Rahul"], client=c,
        )


async def test_send_template_message_success_returns_wamid():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer tok"
        assert "/v21.0/123/messages" in str(request.url)
        return httpx.Response(200, json={"messages": [{"id": "wamid.ABC"}]})

    assert await _send_with_transport(handler) == "wamid.ABC"


async def test_send_template_message_4xx_is_permanent():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": {"code": 132001, "message": "Template not found"}})

    with pytest.raises(wa.WhatsAppError) as exc:
        await _send_with_transport(handler)
    assert exc.value.retryable is False
    assert "132001" in str(exc.value)


async def test_send_template_message_5xx_is_retryable():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="upstream unavailable")

    with pytest.raises(wa.WhatsAppError) as exc:
        await _send_with_transport(handler)
    assert exc.value.retryable is True


async def test_send_template_message_429_is_retryable():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": {"code": 130429, "message": "rate limit"}})

    with pytest.raises(wa.WhatsAppError) as exc:
        await _send_with_transport(handler)
    assert exc.value.retryable is True


# ─── send_notification channel dispatch ─────────────────────────────────────

class _FakeSettings:
    def __init__(self, enabled=True, token="tok", phone="123"):
        self.WHATSAPP_ENABLED = enabled
        self.WHATSAPP_ACCESS_TOKEN = token
        self.WHATSAPP_PHONE_NUMBER_ID = phone
        self.WHATSAPP_API_VERSION = "v21.0"


def _wa_queue_item(recipient="9876543210", payload=None):
    return NotificationQueue(
        template_id=uuid.uuid4(),
        recipient=recipient,
        channel="WHATSAPP",
        payload_json=json.dumps(payload or {"student_name": "Rahul", "attendance_date": "03 Aug 2026"}),
        delivery_status="PENDING",
    )


def _wa_template():
    return NotificationTemplate(
        name="absent", event_type="STUDENT_ABSENT", channel="WHATSAPP",
        body_template="{student_name} was absent on {attendance_date}.",
        is_active=True,
        provider_template_name="attendance_absent_alert",
        provider_language="en",
    )


async def test_send_notification_whatsapp_disabled_skips(monkeypatch):
    monkeypatch.setattr(notification_service, "get_settings", lambda: _FakeSettings(enabled=False))
    outcome, error, retryable = await notification_service.send_notification(
        _wa_queue_item(), _wa_template()
    )
    assert outcome == "SKIP"


async def test_send_notification_whatsapp_enabled_sends(monkeypatch):
    monkeypatch.setattr(notification_service, "get_settings", lambda: _FakeSettings())

    captured = {}

    async def fake_send(**kwargs):
        captured.update(kwargs)
        return "wamid.SENT"

    monkeypatch.setattr(wa, "send_template_message", fake_send)

    outcome, error, retryable = await notification_service.send_notification(
        _wa_queue_item(), _wa_template()
    )
    assert outcome == "SENT"
    assert captured["to"] == "919876543210"                 # normalized
    assert captured["template_name"] == "attendance_absent_alert"
    assert captured["body_params"] == ["Rahul", "03 Aug 2026"]  # ordered from body


async def test_send_notification_whatsapp_bad_number_fails_permanently(monkeypatch):
    monkeypatch.setattr(notification_service, "get_settings", lambda: _FakeSettings())
    outcome, error, retryable = await notification_service.send_notification(
        _wa_queue_item(recipient="123"), _wa_template()
    )
    assert outcome == "FAILED"
    assert retryable is False


async def test_send_notification_whatsapp_missing_template_name_fails(monkeypatch):
    monkeypatch.setattr(notification_service, "get_settings", lambda: _FakeSettings())
    tmpl = _wa_template()
    tmpl.provider_template_name = None
    outcome, error, retryable = await notification_service.send_notification(
        _wa_queue_item(), tmpl
    )
    assert outcome == "FAILED"


async def test_send_notification_email_still_logs_sent():
    item = NotificationQueue(
        template_id=uuid.uuid4(), recipient="a@b.com", channel="EMAIL",
        payload_json=json.dumps({"x": 1}), delivery_status="PENDING",
    )
    outcome, error, retryable = await notification_service.send_notification(item, None)
    assert outcome == "SENT"


# ─── process_queue: disabled WhatsApp row stays PENDING ─────────────────────

async def test_process_queue_skips_disabled_whatsapp(
    client, seed_data, db_session: AsyncSession, monkeypatch
):
    monkeypatch.setattr(notification_service, "get_settings", lambda: _FakeSettings(enabled=False))
    tmpl = _wa_template()
    tmpl.branch_id = uuid.UUID(BRANCH_A_ID)
    db_session.add(tmpl)
    await db_session.flush()

    item = _wa_queue_item()
    item.template_id = tmpl.id
    item.branch_id = uuid.UUID(BRANCH_A_ID)
    db_session.add(item)
    await db_session.commit()

    result = await notification_service.process_queue(db_session)
    await db_session.commit()
    assert result["skipped"] >= 1

    await db_session.refresh(item)
    assert item.delivery_status == "PENDING"  # untouched, flushes once enabled


# ─── consume_events: absent sweep -> queue bridge ───────────────────────────

async def test_consume_events_enqueues_and_is_idempotent(
    client, seed_data, db_session: AsyncSession
):
    tmpl = _wa_template()
    tmpl.branch_id = uuid.UUID(BRANCH_A_ID)
    db_session.add(tmpl)
    await db_session.flush()

    await event_service.emit_event(
        db_session,
        event_type="STUDENT_ABSENT",
        branch_id=uuid.UUID(BRANCH_A_ID),
        student_id=None,
        metadata={
            "attendance_date": "2026-08-03",
            "student_name": "Rahul Sharma",
            "recipient": "9876543210",
        },
    )
    await db_session.commit()

    first = await notification_service.consume_events(db_session)
    await db_session.commit()
    assert first["consumed"] == 1
    assert first["enqueued"] == 1

    # The queued row targets the parent's number on the WHATSAPP channel.
    queue = await notification_service.list_queue(db_session, branch_id=uuid.UUID(BRANCH_A_ID))
    wa_rows = [q for q in queue if q["channel"] == "WHATSAPP"]
    assert wa_rows and wa_rows[0]["recipient"] == "9876543210"

    # Second drain must not re-enqueue the same event.
    second = await notification_service.consume_events(db_session)
    await db_session.commit()
    assert second["consumed"] == 0
    assert second["enqueued"] == 0
