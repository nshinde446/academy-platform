import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient

BRANCH_A_ID = "00000000-0000-0000-0000-000000000001"
BRANCH_B_ID = "00000000-0000-0000-0000-000000000002"
TEACHER_ID = "00000000-0000-0000-0000-000000000060"
BATCH_ID = "00000000-0000-0000-0000-000000000070"
BATCH_B_ID = "00000000-0000-0000-0000-000000000071"
CLASSROOM_ID = "00000000-0000-0000-0000-000000000080"
STUDENT_ID = "00000000-0000-0000-0000-000000000090"
SUBJECT_ID = "00000000-0000-0000-0000-000000000050"
ACADEMIC_YEAR_ID = "00000000-0000-0000-0000-000000000030"


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


def _lecture_payload(
    start_offset_hours: int = 1,
    end_offset_hours: int = 2,
    delivery_mode: str = "offline",
):
    now = datetime.now(timezone.utc)
    return {
        "teacher_id": TEACHER_ID,
        "batch_id": BATCH_ID,
        "classroom_id": CLASSROOM_ID,
        "subject_id": SUBJECT_ID,
        "scheduled_start": (now + timedelta(hours=start_offset_hours)).isoformat(),
        "scheduled_end": (now + timedelta(hours=end_offset_hours)).isoformat(),
        "delivery_mode": delivery_mode,
    }


async def _create_lecture(client: AsyncClient, payload=None):
    if payload is None:
        payload = _lecture_payload()
    resp = await client.post("/api/v1/lectures", json=payload)
    assert resp.status_code == 200
    return resp.json()


# ─── Test 1: Create a lecture successfully ─────────────────────────────────────

async def test_create_lecture(client: AsyncClient, seed_data):
    await _login_admin(client)
    lecture = await _create_lecture(client)
    assert lecture["lecture_status"] == "scheduled"
    assert lecture["teacher_id"] == TEACHER_ID
    assert lecture["batch_id"] == BATCH_ID
    assert lecture["branch_id"] == BRANCH_A_ID


# ─── Test 2: Teacher conflict detection ───────────────────────────────────────

async def test_teacher_conflict(client: AsyncClient, seed_data):
    await _login_admin(client)
    await _create_lecture(client)
    resp = await client.post("/api/v1/lectures", json=_lecture_payload())
    assert resp.status_code == 409
    assert "Teacher" in resp.json()["error"]["message"]


# ─── Test 3: Batch conflict detection ─────────────────────────────────────────

async def test_batch_conflict(client: AsyncClient, seed_data):
    await _login_admin(client)
    payload1 = _lecture_payload()
    await _create_lecture(client, payload1)
    payload2 = _lecture_payload()
    payload2["teacher_id"] = str(uuid.uuid4())
    payload2["classroom_id"] = None
    payload2["delivery_mode"] = "online"
    resp = await client.post("/api/v1/lectures", json=payload2)
    assert resp.status_code == 409
    assert "Batch" in resp.json()["error"]["message"]


# ─── Test 4: Classroom conflict detection ─────────────────────────────────────

async def test_classroom_conflict(client: AsyncClient, seed_data):
    await _login_admin(client)
    await _create_lecture(client)
    now = datetime.now(timezone.utc)
    payload = {
        "teacher_id": str(uuid.uuid4()),
        "batch_id": BATCH_B_ID,
        "classroom_id": CLASSROOM_ID,
        "subject_id": SUBJECT_ID,
        "scheduled_start": (now + timedelta(hours=1)).isoformat(),
        "scheduled_end": (now + timedelta(hours=2)).isoformat(),
        "delivery_mode": "offline",
    }
    resp = await client.post("/api/v1/lectures", json=payload)
    assert resp.status_code == 409
    assert "Classroom" in resp.json()["error"]["message"]


# ─── Test 5: Lifecycle – start lecture ─────────────────────────────────────────

async def test_start_lecture(client: AsyncClient, seed_data):
    await _login_admin(client)
    lecture = await _create_lecture(client)
    resp = await client.patch(
        f"/api/v1/lectures/{lecture['id']}/start",
        params={"branch_id": BRANCH_A_ID},
    )
    assert resp.status_code == 200
    assert resp.json()["lecture_status"] == "started"
    assert resp.json()["actual_start"] is not None


# ─── Test 6: Lifecycle – complete lecture ──────────────────────────────────────

async def test_complete_lecture(client: AsyncClient, seed_data):
    await _login_admin(client)
    lecture = await _create_lecture(client)
    await client.patch(
        f"/api/v1/lectures/{lecture['id']}/start",
        params={"branch_id": BRANCH_A_ID},
    )
    resp = await client.patch(
        f"/api/v1/lectures/{lecture['id']}/complete",
        params={"branch_id": BRANCH_A_ID},
    )
    assert resp.status_code == 200
    assert resp.json()["lecture_status"] == "completed"
    assert resp.json()["actual_end"] is not None


# ─── Test 7: Invalid transition – scheduled → completed ───────────────────────

async def test_invalid_transition_scheduled_to_completed(client: AsyncClient, seed_data):
    await _login_admin(client)
    lecture = await _create_lecture(client)
    resp = await client.patch(
        f"/api/v1/lectures/{lecture['id']}/complete",
        params={"branch_id": BRANCH_A_ID},
    )
    assert resp.status_code == 422
    assert "Cannot transition" in resp.json()["error"]["message"]


# ─── Test 8: Cancel lecture ────────────────────────────────────────────────────

async def test_cancel_lecture(client: AsyncClient, seed_data):
    await _login_admin(client)
    lecture = await _create_lecture(client)
    resp = await client.patch(
        f"/api/v1/lectures/{lecture['id']}/cancel",
        params={"branch_id": BRANCH_A_ID},
    )
    assert resp.status_code == 200
    assert resp.json()["lecture_status"] == "cancelled"


# ─── Test 9: Reschedule lecture ────────────────────────────────────────────────

async def test_reschedule_lecture(client: AsyncClient, seed_data):
    """Reschedule writes new times back as `scheduled` so Start / Cancel /
    No-Show all remain reachable on the lecture row."""
    await _login_admin(client)
    lecture = await _create_lecture(client)
    now = datetime.now(timezone.utc)
    new_start = (now + timedelta(hours=5)).isoformat()
    resp = await client.patch(
        f"/api/v1/lectures/{lecture['id']}/reschedule",
        params={"branch_id": BRANCH_A_ID},
        json={
            "scheduled_start": new_start,
            "scheduled_end": (now + timedelta(hours=6)).isoformat(),
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["lecture_status"] == "scheduled"
    assert body["scheduled_start"].startswith(new_start[:16])


# ─── Test 10: Branch isolation – cannot access other branch's lecture ─────────

async def test_branch_isolation(client: AsyncClient, seed_data):
    await _login_admin(client)
    lecture = await _create_lecture(client)
    resp = await client.get(
        f"/api/v1/lectures/{lecture['id']}",
        params={"branch_id": BRANCH_B_ID},
    )
    assert resp.status_code == 403


# ─── Test 11: Mark attendance ──────────────────────────────────────────────────

async def test_mark_attendance(client: AsyncClient, seed_data):
    await _login_admin(client)
    lecture = await _create_lecture(client)
    resp = await client.post(
        f"/api/v1/lectures/{lecture['id']}/attendance",
        params={"branch_id": BRANCH_A_ID},
        json={
            "student_id": STUDENT_ID,
            "attendance_status": "PRESENT",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["attendance_status"] == "PRESENT"
    assert resp.json()["student_id"] == STUDENT_ID


# ─── Test 12: Get attendance ──────────────────────────────────────────────────

async def test_get_attendance(client: AsyncClient, seed_data):
    await _login_admin(client)
    lecture = await _create_lecture(client)
    await client.post(
        f"/api/v1/lectures/{lecture['id']}/attendance",
        params={"branch_id": BRANCH_A_ID},
        json={"student_id": STUDENT_ID, "attendance_status": "PRESENT"},
    )
    resp = await client.get(
        f"/api/v1/lectures/{lecture['id']}/attendance",
        params={"branch_id": BRANCH_A_ID},
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 1


# ─── Test 13: Soft delete lecture ──────────────────────────────────────────────

async def test_delete_lecture(client: AsyncClient, seed_data):
    await _login_admin(client)
    lecture = await _create_lecture(client)
    resp = await client.delete(
        f"/api/v1/lectures/{lecture['id']}",
        params={"branch_id": BRANCH_A_ID},
    )
    assert resp.status_code == 204
    resp = await client.get(
        f"/api/v1/lectures/{lecture['id']}",
        params={"branch_id": BRANCH_A_ID},
    )
    assert resp.status_code == 404


# ─── Test 14: Online lecture doesn't require classroom ─────────────────────────

async def test_online_lecture_no_classroom(client: AsyncClient, seed_data):
    await _login_admin(client)
    payload = _lecture_payload(start_offset_hours=3, end_offset_hours=4, delivery_mode="online")
    payload["classroom_id"] = None
    lecture = await _create_lecture(client, payload)
    assert lecture["delivery_mode"] == "online"
    assert lecture["classroom_id"] is None


# ─── Test 15: Offline lecture requires classroom ───────────────────────────────

async def test_offline_lecture_requires_classroom(client: AsyncClient, seed_data):
    await _login_admin(client)
    payload = _lecture_payload(start_offset_hours=10, end_offset_hours=11, delivery_mode="offline")
    payload["classroom_id"] = None
    resp = await client.post("/api/v1/lectures", json=payload)
    assert resp.status_code == 422
    assert "classroom" in resp.json()["error"]["message"].lower()


# ─── Test 16: Audit log created on lecture creation ────────────────────────────

async def test_audit_log_on_create(client: AsyncClient, seed_data):
    await _login_admin(client)
    await _create_lecture(client)
    resp = await client.get("/api/v1/audit/logs", params={"table_name": "lectures"})
    assert resp.status_code == 200
    data = resp.json()
    logs = data["items"]
    assert any(log["action"] == "CREATE" and log["table_name"] == "lectures" for log in logs)
