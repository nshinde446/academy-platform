import json
import uuid
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.notifications.models.notification_models import (
    NotificationQueue,
    NotificationTemplate,
)
from app.modules.notifications.services import notification_service

BRANCH_A_ID = "00000000-0000-0000-0000-000000000001"
BRANCH_B_ID = "00000000-0000-0000-0000-000000000002"


async def _login_admin(client: AsyncClient):
    resp = await client.post("/api/v1/auth/login", json={
        "email": "admin@test.com",
        "password": "Admin123!",
    })
    assert resp.status_code == 200


async def _login_teacher(client: AsyncClient):
    resp = await client.post("/api/v1/auth/login", json={
        "email": "teacher@test.com",
        "password": "Teacher123!",
    })
    assert resp.status_code == 200


def _template_payload(**overrides):
    base = {
        "name": "low_attendance_alert",
        "event_type": "ATTENDANCE_MARKED",
        "channel": "EMAIL",
        "subject": "Low Attendance Alert",
        "body_template": "Dear {student_name}, your attendance is {attendance_percentage}%.",
        "is_active": True,
        "branch_id": BRANCH_A_ID,
    }
    base.update(overrides)
    return base


# ─── Test 1: Create template ────────────────────────────────────────────────

async def test_create_template(client: AsyncClient, seed_data):
    await _login_admin(client)
    resp = await client.post(
        "/api/v1/notifications/templates",
        json=_template_payload(),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "low_attendance_alert"
    assert data["event_type"] == "ATTENDANCE_MARKED"
    assert data["channel"] == "EMAIL"
    assert data["is_active"] is True


# ─── Test 2: List templates ─────────────────────────────────────────────────

async def test_list_templates(client: AsyncClient, seed_data):
    await _login_admin(client)
    await client.post("/api/v1/notifications/templates", json=_template_payload())
    await client.post("/api/v1/notifications/templates", json=_template_payload(
        name="test_alert", event_type="TEST_UPLOADED", channel="SMS",
        body_template="New test uploaded: {test_name}",
    ))
    resp = await client.get("/api/v1/notifications/templates")
    assert resp.status_code == 200
    assert len(resp.json()) >= 2


# ─── Test 3: Update template ────────────────────────────────────────────────

async def test_update_template(client: AsyncClient, seed_data):
    await _login_admin(client)
    resp = await client.post("/api/v1/notifications/templates", json=_template_payload())
    template_id = resp.json()["id"]
    resp = await client.patch(
        f"/api/v1/notifications/templates/{template_id}",
        json={"name": "updated_alert", "is_active": False},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "updated_alert"
    assert resp.json()["is_active"] is False


# ─── Test 4: Soft delete template ───────────────────────────────────────────

async def test_delete_template(client: AsyncClient, seed_data):
    await _login_admin(client)
    resp = await client.post("/api/v1/notifications/templates", json=_template_payload())
    template_id = resp.json()["id"]
    resp = await client.delete(f"/api/v1/notifications/templates/{template_id}")
    assert resp.status_code == 204
    resp = await client.get("/api/v1/notifications/templates")
    ids = [t["id"] for t in resp.json()]
    assert template_id not in ids


# ─── Test 5: Invalid channel rejected ───────────────────────────────────────

async def test_invalid_channel(client: AsyncClient, seed_data):
    await _login_admin(client)
    resp = await client.post(
        "/api/v1/notifications/templates",
        json=_template_payload(channel="PIGEON"),
    )
    assert resp.status_code == 400


# ─── Test 6: Invalid event_type rejected ────────────────────────────────────

async def test_invalid_event_type(client: AsyncClient, seed_data):
    await _login_admin(client)
    resp = await client.post(
        "/api/v1/notifications/templates",
        json=_template_payload(event_type="INVALID_EVENT"),
    )
    assert resp.status_code == 400


# ─── Test 7: Rule evaluation – condition matching ───────────────────────────

async def test_condition_evaluation(client: AsyncClient, seed_data, db_session: AsyncSession):
    await _login_admin(client)
    await client.post("/api/v1/notifications/templates", json=_template_payload(
        name="low_att_conditional",
        condition_json={"type": "comparison", "field": "attendance_percentage", "operator": "lt", "value": 75},
    ))

    event_data = {
        "event_type": "ATTENDANCE_MARKED",
        "branch_id": BRANCH_A_ID,
        "event_id": str(uuid.uuid4()),
        "student_name": "Test Student",
        "attendance_percentage": 60.0,
        "recipient": "student@test.com",
    }
    queued = await notification_service.process_event(db_session, event_data)
    await db_session.commit()
    assert len(queued) >= 1


# ─── Test 8: Condition not met – no notification ────────────────────────────

async def test_condition_not_met(client: AsyncClient, seed_data, db_session: AsyncSession):
    await _login_admin(client)
    await client.post("/api/v1/notifications/templates", json=_template_payload(
        name="low_att_strict",
        condition_json={"type": "comparison", "field": "attendance_percentage", "operator": "lt", "value": 50},
    ))

    event_data = {
        "event_type": "ATTENDANCE_MARKED",
        "branch_id": BRANCH_A_ID,
        "event_id": str(uuid.uuid4()),
        "attendance_percentage": 80.0,
        "recipient": "student@test.com",
    }
    queued = await notification_service.process_event(db_session, event_data)
    await db_session.commit()
    condition_not_met_queued = [q for q in queued if q.template_id is not None]
    for q in queued:
        template = await db_session.get(NotificationTemplate, q.template_id)
        if template and template.name == "low_att_strict":
            pytest.fail("Should not have enqueued for condition not met")


# ─── Test 9: Queue processing – sends pending notifications ────────────────

async def test_queue_processing(client: AsyncClient, seed_data, db_session: AsyncSession):
    await _login_admin(client)
    resp = await client.post("/api/v1/notifications/templates", json=_template_payload(
        name="queue_test",
    ))
    template_id = uuid.UUID(resp.json()["id"])

    item = NotificationQueue(
        template_id=template_id,
        recipient="test@example.com",
        channel="EMAIL",
        payload_json=json.dumps({"student_name": "Test"}),
        delivery_status="PENDING",
        branch_id=uuid.UUID(BRANCH_A_ID),
        status="active",
        is_deleted=False,
    )
    db_session.add(item)
    await db_session.commit()

    result = await notification_service.process_queue(db_session)
    await db_session.commit()
    assert result["sent"] >= 1
    assert result["failed"] == 0


# ─── Test 10: Retry logic – failed increments retry_count ──────────────────

async def test_retry_logic(client: AsyncClient, seed_data, db_session: AsyncSession):
    await _login_admin(client)
    resp = await client.post("/api/v1/notifications/templates", json=_template_payload(
        name="retry_test",
    ))
    template_id = uuid.UUID(resp.json()["id"])

    item = NotificationQueue(
        template_id=template_id,
        recipient="fail@example.com",
        channel="EMAIL",
        payload_json=json.dumps({"test": True}),
        delivery_status="PENDING",
        retry_count=2,
        max_retries=3,
        branch_id=uuid.UUID(BRANCH_A_ID),
        status="active",
        is_deleted=False,
    )
    db_session.add(item)
    await db_session.commit()

    from app.modules.notifications.repositories import notification_repository
    await notification_repository.mark_failed(db_session, item, "Test failure")
    await db_session.commit()

    await db_session.refresh(item)
    assert item.retry_count == 3
    assert item.delivery_status == "FAILED"
    assert item.error_message == "Test failure"


# ─── Test 11: Branch isolation ──────────────────────────────────────────────

async def test_branch_isolation(client: AsyncClient, seed_data):
    await _login_admin(client)
    await client.post("/api/v1/notifications/templates", json=_template_payload(
        name="branch_a_only",
        branch_id=BRANCH_A_ID,
    ))
    resp = await client.get(
        "/api/v1/notifications/templates",
        params={"branch_id": BRANCH_B_ID},
    )
    assert resp.status_code == 200
    names = [t["name"] for t in resp.json()]
    assert "branch_a_only" not in names


# ─── Test 12: Global template visible to all branches ───────────────────────

async def test_global_template(client: AsyncClient, seed_data):
    await _login_admin(client)
    await client.post("/api/v1/notifications/templates", json=_template_payload(
        name="global_alert",
        branch_id=None,
    ))
    resp = await client.get(
        "/api/v1/notifications/templates",
        params={"branch_id": BRANCH_B_ID},
    )
    names = [t["name"] for t in resp.json()]
    assert "global_alert" in names


# ─── Test 13: Audit logging on template creation ────────────────────────────

async def test_audit_log_on_create(client: AsyncClient, seed_data):
    await _login_admin(client)
    await client.post("/api/v1/notifications/templates", json=_template_payload(
        name="audit_test",
    ))
    resp = await client.get(
        "/api/v1/audit/logs",
        params={"table_name": "notification_templates", "action": "CREATE"},
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert any(log["table_name"] == "notification_templates" and log["action"] == "CREATE" for log in items)


# ─── Test 14: RBAC – teacher cannot create template ────────────────────────

async def test_teacher_cannot_create_template(client: AsyncClient, seed_data):
    await _login_teacher(client)
    resp = await client.post(
        "/api/v1/notifications/templates",
        json=_template_payload(),
    )
    assert resp.status_code == 403


# ─── Test 15: View queue requires super_admin ───────────────────────────────

async def test_queue_requires_admin(client: AsyncClient, seed_data):
    await _login_teacher(client)
    resp = await client.get("/api/v1/notifications/queue")
    assert resp.status_code == 403


# ─── Test 16: Template placeholder rendering ────────────────────────────────

def test_render_template():
    body = "Hello {student_name}, your score is {score}%."
    data = {"student_name": "Alice", "score": "85"}
    result = notification_service.render_template(body, data)
    assert result == "Hello Alice, your score is 85%."


# ─── Test 17: Event consumer enqueues for matching template ─────────────────

async def test_event_consumer_integration(client: AsyncClient, seed_data, db_session: AsyncSession):
    await _login_admin(client)
    await client.post("/api/v1/notifications/templates", json=_template_payload(
        name="marks_alert",
        event_type="MARKS_UPDATED",
        body_template="Student {student_name} scored {marks_obtained}",
    ))

    event_data = {
        "event_type": "MARKS_UPDATED",
        "branch_id": BRANCH_A_ID,
        "event_id": str(uuid.uuid4()),
        "student_name": "Test Student",
        "marks_obtained": 45.0,
        "recipient": "student@test.com",
    }
    queued = await notification_service.process_event(db_session, event_data)
    await db_session.commit()
    assert len(queued) >= 1
    assert queued[0].channel == "EMAIL"
    assert queued[0].recipient == "student@test.com"
