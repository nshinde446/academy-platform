import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient

BRANCH_A_ID = "00000000-0000-0000-0000-000000000001"
BRANCH_B_ID = "00000000-0000-0000-0000-000000000002"
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


def _lecture_payload(start_offset_hours=1, end_offset_hours=2):
    now = datetime.now(timezone.utc)
    return {
        "teacher_id": TEACHER_ID,
        "batch_id": BATCH_ID,
        "classroom_id": CLASSROOM_ID,
        "subject_id": SUBJECT_ID,
        "scheduled_start": (now + timedelta(hours=start_offset_hours)).isoformat(),
        "scheduled_end": (now + timedelta(hours=end_offset_hours)).isoformat(),
        "delivery_mode": "offline",
    }


async def _create_lecture(client: AsyncClient, offset=1):
    payload = _lecture_payload(start_offset_hours=offset, end_offset_hours=offset + 1)
    resp = await client.post("/api/v1/lectures", json=payload)
    assert resp.status_code == 200
    return resp.json()


# ─── Test 1: Receive raw punch logs ────────────────────────────────────────────

async def test_receive_raw_punches(client: AsyncClient, seed_data):
    await _login_admin(client)
    now = datetime.now(timezone.utc)
    resp = await client.post("/api/v1/attendance/raw", json={
        "punches": [
            {
                "device_id": "BIO-001",
                "student_id": STUDENT_ID,
                "punch_timestamp": now.isoformat(),
                "sync_batch_id": "SYNC-001",
            }
        ]
    })
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["device_id"] == "BIO-001"
    assert resp.json()[0]["student_id"] == STUDENT_ID


# ─── Test 2: Manual attendance marking ─────────────────────────────────────────

async def test_mark_attendance_manual(client: AsyncClient, seed_data):
    await _login_admin(client)
    lecture = await _create_lecture(client)
    resp = await client.post(
        f"/api/v1/attendance/lecture/{lecture['id']}/mark",
        params={"branch_id": BRANCH_A_ID},
        json={
            "student_id": STUDENT_ID,
            "attendance_status": "PRESENT",
            "source": "MANUAL",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["attendance_status"] == "PRESENT"
    assert resp.json()["source"] == "MANUAL"


# ─── Test 3: Override existing attendance ──────────────────────────────────────

async def test_override_attendance(client: AsyncClient, seed_data):
    await _login_admin(client)
    lecture = await _create_lecture(client)
    await client.post(
        f"/api/v1/attendance/lecture/{lecture['id']}/mark",
        params={"branch_id": BRANCH_A_ID},
        json={"student_id": STUDENT_ID, "attendance_status": "ABSENT", "source": "SYSTEM"},
    )
    resp = await client.post(
        f"/api/v1/attendance/lecture/{lecture['id']}/mark",
        params={"branch_id": BRANCH_A_ID},
        json={"student_id": STUDENT_ID, "attendance_status": "MANUAL_OVERRIDE", "source": "MANUAL"},
    )
    assert resp.status_code == 200
    assert resp.json()["attendance_status"] == "MANUAL_OVERRIDE"
    assert resp.json()["source"] == "MANUAL"


# ─── Test 4: Get lecture attendance ────────────────────────────────────────────

async def test_get_lecture_attendance(client: AsyncClient, seed_data):
    await _login_admin(client)
    lecture = await _create_lecture(client)
    await client.post(
        f"/api/v1/attendance/lecture/{lecture['id']}/mark",
        params={"branch_id": BRANCH_A_ID},
        json={"student_id": STUDENT_ID, "attendance_status": "PRESENT", "source": "MANUAL"},
    )
    resp = await client.get(
        f"/api/v1/attendance/lecture/{lecture['id']}",
        params={"branch_id": BRANCH_A_ID},
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 1


# ─── Test 5: Get student attendance history ────────────────────────────────────

async def test_get_student_attendance(client: AsyncClient, seed_data):
    await _login_admin(client)
    lecture = await _create_lecture(client)
    await client.post(
        f"/api/v1/attendance/lecture/{lecture['id']}/mark",
        params={"branch_id": BRANCH_A_ID},
        json={"student_id": STUDENT_ID, "attendance_status": "PRESENT", "source": "MANUAL"},
    )
    resp = await client.get(
        f"/api/v1/attendance/student/{STUDENT_ID}",
        params={"branch_id": BRANCH_A_ID},
    )
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


# ─── Test 6: Create attendance exception ──────────────────────────────────────

async def test_create_exception(client: AsyncClient, seed_data):
    await _login_admin(client)
    lecture = await _create_lecture(client)
    resp = await client.post(
        "/api/v1/attendance/exceptions",
        params={"branch_id": BRANCH_A_ID},
        json={
            "student_id": STUDENT_ID,
            "lecture_id": lecture["id"],
            "reason": "Duplicate punch detected",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["resolved"] is False
    assert resp.json()["reason"] == "Duplicate punch detected"


# ─── Test 7: Resolve exception ─────────────────────────────────────────────────

async def test_resolve_exception(client: AsyncClient, seed_data):
    await _login_admin(client)
    lecture = await _create_lecture(client)
    create_resp = await client.post(
        "/api/v1/attendance/exceptions",
        params={"branch_id": BRANCH_A_ID},
        json={
            "student_id": STUDENT_ID,
            "lecture_id": lecture["id"],
            "reason": "Late arrival edge case",
        },
    )
    exc_id = create_resp.json()["id"]
    resp = await client.patch(
        f"/api/v1/attendance/exceptions/{exc_id}/resolve",
        params={"branch_id": BRANCH_A_ID},
        json={"resolution_notes": "Verified with CCTV"},
    )
    assert resp.status_code == 200
    assert resp.json()["resolved"] is True
    assert resp.json()["resolution_notes"] == "Verified with CCTV"


# ─── Test 8: Cannot resolve already resolved exception ─────────────────────────

async def test_cannot_resolve_twice(client: AsyncClient, seed_data):
    await _login_admin(client)
    lecture = await _create_lecture(client)
    create_resp = await client.post(
        "/api/v1/attendance/exceptions",
        params={"branch_id": BRANCH_A_ID},
        json={
            "student_id": STUDENT_ID,
            "lecture_id": lecture["id"],
            "reason": "Device malfunction",
        },
    )
    exc_id = create_resp.json()["id"]
    await client.patch(
        f"/api/v1/attendance/exceptions/{exc_id}/resolve",
        params={"branch_id": BRANCH_A_ID},
        json={"resolution_notes": "Fixed"},
    )
    resp = await client.patch(
        f"/api/v1/attendance/exceptions/{exc_id}/resolve",
        params={"branch_id": BRANCH_A_ID},
        json={"resolution_notes": "Again"},
    )
    assert resp.status_code == 422
    assert "already resolved" in resp.json()["error"]["message"]


# ─── Test 9: Invalid attendance status ─────────────────────────────────────────

async def test_invalid_attendance_status(client: AsyncClient, seed_data):
    await _login_admin(client)
    lecture = await _create_lecture(client)
    resp = await client.post(
        f"/api/v1/attendance/lecture/{lecture['id']}/mark",
        params={"branch_id": BRANCH_A_ID},
        json={"student_id": STUDENT_ID, "attendance_status": "INVALID", "source": "MANUAL"},
    )
    assert resp.status_code == 422
    assert "Invalid attendance status" in resp.json()["error"]["message"]


# ─── Test 10: Invalid source ──────────────────────────────────────────────────

async def test_invalid_source(client: AsyncClient, seed_data):
    await _login_admin(client)
    lecture = await _create_lecture(client)
    resp = await client.post(
        f"/api/v1/attendance/lecture/{lecture['id']}/mark",
        params={"branch_id": BRANCH_A_ID},
        json={"student_id": STUDENT_ID, "attendance_status": "PRESENT", "source": "TELEPATHY"},
    )
    assert resp.status_code == 422
    assert "Invalid source" in resp.json()["error"]["message"]


# ─── Test 11: Branch isolation on attendance ──────────────────────────────────

async def test_branch_isolation_attendance(client: AsyncClient, seed_data):
    await _login_admin(client)
    lecture = await _create_lecture(client)
    resp = await client.get(
        f"/api/v1/attendance/lecture/{lecture['id']}",
        params={"branch_id": BRANCH_B_ID},
    )
    assert resp.status_code == 403


# ─── Test 12: Attendance report ────────────────────────────────────────────────

async def test_attendance_report(client: AsyncClient, seed_data):
    await _login_admin(client)
    lecture = await _create_lecture(client, offset=5)
    await client.post(
        f"/api/v1/attendance/lecture/{lecture['id']}/mark",
        params={"branch_id": BRANCH_A_ID},
        json={"student_id": STUDENT_ID, "attendance_status": "PRESENT", "source": "MANUAL"},
    )
    resp = await client.get(
        f"/api/v1/attendance/lecture/{lecture['id']}/report",
        params={"branch_id": BRANCH_A_ID},
    )
    assert resp.status_code == 200
    report = resp.json()
    assert report["total_students"] == 1
    assert report["present"] == 1
    assert report["absent"] == 0
