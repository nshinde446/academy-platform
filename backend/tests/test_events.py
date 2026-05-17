import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient

BRANCH_A_ID = "00000000-0000-0000-0000-000000000001"
TEACHER_ID = "00000000-0000-0000-0000-000000000060"
BATCH_ID = "00000000-0000-0000-0000-000000000070"
CLASSROOM_ID = "00000000-0000-0000-0000-000000000080"
STUDENT_ID = "00000000-0000-0000-0000-000000000090"
SUBJECT_ID = "00000000-0000-0000-0000-000000000050"


async def _login_admin(client: AsyncClient):
    resp = await client.post("/api/v1/auth/login", json={
        "email": "admin@test.com",
        "password": "Admin123!",
    })
    assert resp.status_code == 200


def _lecture_payload(offset=1):
    now = datetime.now(timezone.utc)
    return {
        "teacher_id": TEACHER_ID,
        "batch_id": BATCH_ID,
        "classroom_id": CLASSROOM_ID,
        "subject_id": SUBJECT_ID,
        "scheduled_start": (now + timedelta(hours=offset)).isoformat(),
        "scheduled_end": (now + timedelta(hours=offset + 1)).isoformat(),
        "delivery_mode": "offline",
    }


# ─── Test 1: LECTURE_STARTED event emitted ─────────────────────────────────────

async def test_lecture_started_event(client: AsyncClient, seed_data):
    await _login_admin(client)
    resp = await client.post("/api/v1/lectures", json=_lecture_payload())
    lecture = resp.json()
    await client.patch(
        f"/api/v1/lectures/{lecture['id']}/start",
        params={"branch_id": BRANCH_A_ID},
    )
    resp = await client.get(
        "/api/v1/events",
        params={"event_type": "LECTURE_STARTED"},
    )
    assert resp.status_code == 200
    events = resp.json()
    assert any(e["event_type"] == "LECTURE_STARTED" and e["lecture_id"] == lecture["id"] for e in events)


# ─── Test 2: LECTURE_COMPLETED event emitted ───────────────────────────────────

async def test_lecture_completed_event(client: AsyncClient, seed_data):
    await _login_admin(client)
    resp = await client.post("/api/v1/lectures", json=_lecture_payload(offset=3))
    lecture = resp.json()
    await client.patch(
        f"/api/v1/lectures/{lecture['id']}/start",
        params={"branch_id": BRANCH_A_ID},
    )
    await client.patch(
        f"/api/v1/lectures/{lecture['id']}/complete",
        params={"branch_id": BRANCH_A_ID},
    )
    resp = await client.get(
        "/api/v1/events",
        params={"event_type": "LECTURE_COMPLETED"},
    )
    assert resp.status_code == 200
    events = resp.json()
    assert any(e["event_type"] == "LECTURE_COMPLETED" for e in events)


# ─── Test 3: ATTENDANCE_MARKED event emitted ──────────────────────────────────

async def test_attendance_marked_event(client: AsyncClient, seed_data):
    await _login_admin(client)
    resp = await client.post("/api/v1/lectures", json=_lecture_payload(offset=5))
    lecture = resp.json()
    await client.post(
        f"/api/v1/attendance/lecture/{lecture['id']}/mark",
        params={"branch_id": BRANCH_A_ID},
        json={"student_id": STUDENT_ID, "attendance_status": "PRESENT", "source": "MANUAL"},
    )
    resp = await client.get(
        "/api/v1/events",
        params={"event_type": "ATTENDANCE_MARKED"},
    )
    assert resp.status_code == 200
    events = resp.json()
    assert any(e["event_type"] == "ATTENDANCE_MARKED" for e in events)


# ─── Test 4: TEST_UPLOADED event emitted on publish ───────────────────────────

async def test_test_uploaded_event(client: AsyncClient, seed_data):
    await _login_admin(client)
    resp = await client.post("/api/v1/tests", json={
        "name": "Event Test",
        "batch_id": BATCH_ID,
        "subject_id": SUBJECT_ID,
        "duration_minutes": 60,
        "total_marks": 100.0,
    })
    test = resp.json()
    await client.patch(
        f"/api/v1/tests/{test['id']}/publish",
        params={"branch_id": BRANCH_A_ID},
    )
    resp = await client.get(
        "/api/v1/events",
        params={"event_type": "TEST_UPLOADED"},
    )
    assert resp.status_code == 200
    events = resp.json()
    assert any(e["event_type"] == "TEST_UPLOADED" for e in events)


# ─── Test 5: MARKS_UPDATED event emitted ──────────────────────────────────────

async def test_marks_updated_event(client: AsyncClient, seed_data):
    await _login_admin(client)
    resp = await client.post("/api/v1/tests", json={
        "name": "Marks Event Test",
        "batch_id": BATCH_ID,
        "subject_id": SUBJECT_ID,
        "duration_minutes": 30,
        "total_marks": 50.0,
    })
    test = resp.json()
    await client.post(
        "/api/v1/marks",
        params={"test_id": test["id"], "branch_id": BRANCH_A_ID},
        json={"marks": [{"student_id": STUDENT_ID, "marks_obtained": 40.0}]},
    )
    resp = await client.get(
        "/api/v1/events",
        params={"event_type": "MARKS_UPDATED"},
    )
    assert resp.status_code == 200
    events = resp.json()
    assert any(e["event_type"] == "MARKS_UPDATED" for e in events)


# ─── Test 6: List events with filtering ────────────────────────────────────────

async def test_list_events_filtering(client: AsyncClient, seed_data):
    await _login_admin(client)
    resp = await client.post("/api/v1/lectures", json=_lecture_payload(offset=7))
    lecture = resp.json()
    await client.patch(
        f"/api/v1/lectures/{lecture['id']}/start",
        params={"branch_id": BRANCH_A_ID},
    )
    resp = await client.get(
        "/api/v1/events",
        params={"branch_id": BRANCH_A_ID},
    )
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


# ─── Test 7: Replay event resets processed flag ───────────────────────────────

async def test_replay_event(client: AsyncClient, seed_data):
    await _login_admin(client)
    resp = await client.post("/api/v1/lectures", json=_lecture_payload(offset=9))
    lecture = resp.json()
    await client.patch(
        f"/api/v1/lectures/{lecture['id']}/start",
        params={"branch_id": BRANCH_A_ID},
    )
    events_resp = await client.get(
        "/api/v1/events",
        params={"event_type": "LECTURE_STARTED"},
    )
    event = events_resp.json()[0]
    resp = await client.post(f"/api/v1/events/replay/{event['id']}")
    assert resp.status_code == 200
    assert resp.json()["processed"] is False


# ─── Test 8: Event contains metadata ──────────────────────────────────────────

async def test_event_has_metadata(client: AsyncClient, seed_data):
    await _login_admin(client)
    resp = await client.post("/api/v1/lectures", json=_lecture_payload(offset=11))
    lecture = resp.json()
    await client.patch(
        f"/api/v1/lectures/{lecture['id']}/start",
        params={"branch_id": BRANCH_A_ID},
    )
    events_resp = await client.get(
        "/api/v1/events",
        params={"event_type": "LECTURE_STARTED"},
    )
    events = events_resp.json()
    matching = [e for e in events if e["lecture_id"] == lecture["id"]]
    assert len(matching) == 1
    assert matching[0]["metadata"] is not None
    assert "actual_start" in matching[0]["metadata"]


# ─── Test 9: Events require super_admin ────────────────────────────────────────

async def test_events_require_admin(client: AsyncClient, seed_data):
    await client.post("/api/v1/auth/login", json={
        "email": "teacher@test.com",
        "password": "Teacher123!",
    })
    resp = await client.get("/api/v1/events")
    assert resp.status_code == 403


# ─── Test 10: Filter unprocessed events ────────────────────────────────────────

async def test_filter_unprocessed(client: AsyncClient, seed_data):
    await _login_admin(client)
    resp = await client.post("/api/v1/lectures", json=_lecture_payload(offset=13))
    lecture = resp.json()
    await client.patch(
        f"/api/v1/lectures/{lecture['id']}/start",
        params={"branch_id": BRANCH_A_ID},
    )
    resp = await client.get(
        "/api/v1/events",
        params={"processed": False},
    )
    assert resp.status_code == 200
    for event in resp.json():
        assert event["processed"] is False
