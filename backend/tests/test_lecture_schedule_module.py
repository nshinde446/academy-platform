"""Schedule-module enhancements (EduTrack Pro PDF): Subject→Teacher lock,
end-of-day actuals + late flag, copy-to-next-day, teacher productivity."""

import uuid
from datetime import datetime, timedelta, timezone

from httpx import AsyncClient

BRANCH_A_ID = "00000000-0000-0000-0000-000000000001"
TEACHER_ID = "00000000-0000-0000-0000-000000000060"
BATCH_ID = "00000000-0000-0000-0000-000000000070"
CLASSROOM_ID = "00000000-0000-0000-0000-000000000080"
SUBJECT_ID = "00000000-0000-0000-0000-000000000050"


async def _login_admin(client: AsyncClient):
    resp = await client.post("/api/v1/auth/login", json={
        "email": "admin@test.com",
        "password": "Admin123!",
    })
    assert resp.status_code == 200


def _payload(start: datetime, end: datetime, subject_id: str = SUBJECT_ID):
    return {
        "teacher_id": TEACHER_ID,
        "batch_id": BATCH_ID,
        "classroom_id": CLASSROOM_ID,
        "subject_id": subject_id,
        "scheduled_start": start.isoformat(),
        "scheduled_end": end.isoformat(),
        "delivery_mode": "offline",
    }


# ─── Subject→Teacher lock ─────────────────────────────────────────────────────

async def test_schedule_rejects_unassigned_subject(client: AsyncClient, seed_data):
    """Teacher 060 teaches subject 050 only. A different subject must 422."""
    await _login_admin(client)
    now = datetime.now(timezone.utc)
    payload = _payload(
        now + timedelta(hours=20), now + timedelta(hours=21),
        subject_id=str(uuid.uuid4()),
    )
    resp = await client.post("/api/v1/lectures", json=payload)
    assert resp.status_code == 422
    assert "not assigned to this subject" in resp.json()["error"]["message"]


async def test_schedule_allows_assigned_subject(client: AsyncClient, seed_data):
    await _login_admin(client)
    now = datetime.now(timezone.utc)
    resp = await client.post(
        "/api/v1/lectures",
        json=_payload(now + timedelta(hours=22), now + timedelta(hours=23)),
    )
    assert resp.status_code == 200


async def test_teachers_by_subject_endpoint(client: AsyncClient, seed_data):
    await _login_admin(client)
    resp = await client.get(
        "/api/v1/teachers/by-subject",
        params={"branch_id": BRANCH_A_ID, "subject_id": SUBJECT_ID},
    )
    assert resp.status_code == 200
    ids = [t["id"] for t in resp.json()]
    assert TEACHER_ID in ids
    # A subject nobody teaches → empty.
    resp2 = await client.get(
        "/api/v1/teachers/by-subject",
        params={"branch_id": BRANCH_A_ID, "subject_id": str(uuid.uuid4())},
    )
    assert resp2.status_code == 200
    assert resp2.json() == []


# ─── End-of-day actuals + late flag ───────────────────────────────────────────

async def test_actuals_backfill_completes_and_times(client: AsyncClient, seed_data):
    """EOD backfill with no prior live Start/Complete: sets actuals, computes
    duration, marks completed, and is on time (<10 min late)."""
    await _login_admin(client)
    now = datetime.now(timezone.utc)
    start = now + timedelta(hours=30)
    resp = await client.post(
        "/api/v1/lectures", json=_payload(start, start + timedelta(hours=1))
    )
    lecture = resp.json()
    a_start = start + timedelta(minutes=3)
    a_end = start + timedelta(minutes=63)
    resp = await client.patch(
        f"/api/v1/lectures/{lecture['id']}/actuals",
        params={"branch_id": BRANCH_A_ID},
        json={
            "actual_start": a_start.isoformat(),
            "actual_end": a_end.isoformat(),
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["lecture_status"] == "completed"
    assert body["late_flag"] is False
    assert body["actual_duration_min"] == 60


async def test_actuals_late_flag(client: AsyncClient, seed_data):
    await _login_admin(client)
    now = datetime.now(timezone.utc)
    start = now + timedelta(hours=32)
    resp = await client.post(
        "/api/v1/lectures", json=_payload(start, start + timedelta(hours=1))
    )
    lecture = resp.json()
    resp = await client.patch(
        f"/api/v1/lectures/{lecture['id']}/actuals",
        params={"branch_id": BRANCH_A_ID},
        json={
            "actual_start": (start + timedelta(minutes=15)).isoformat(),
            "actual_end": (start + timedelta(minutes=70)).isoformat(),
        },
    )
    assert resp.status_code == 200
    assert resp.json()["late_flag"] is True


async def test_actuals_rejected_on_cancelled(client: AsyncClient, seed_data):
    await _login_admin(client)
    now = datetime.now(timezone.utc)
    start = now + timedelta(hours=34)
    lecture = (await client.post(
        "/api/v1/lectures", json=_payload(start, start + timedelta(hours=1))
    )).json()
    await client.patch(
        f"/api/v1/lectures/{lecture['id']}/cancel",
        params={"branch_id": BRANCH_A_ID},
    )
    resp = await client.patch(
        f"/api/v1/lectures/{lecture['id']}/actuals",
        params={"branch_id": BRANCH_A_ID},
        json={"actual_start": start.isoformat()},
    )
    assert resp.status_code == 422


# ─── Copy to next day ─────────────────────────────────────────────────────────

async def test_copy_to_next_day_idempotent(client: AsyncClient, seed_data):
    await _login_admin(client)
    now = datetime.now(timezone.utc)
    # Pin to 08:00 UTC today so the source-day window is unambiguous.
    today = now.replace(hour=8, minute=0, second=0, microsecond=0)
    await client.post(
        "/api/v1/lectures", json=_payload(today, today + timedelta(hours=1))
    )
    src_date = today.strftime("%Y-%m-%d")

    resp = await client.post(
        "/api/v1/lectures/copy-to-next-day",
        params={"branch_id": BRANCH_A_ID, "source_date": src_date},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["copied"] == 1
    assert body["skipped"] == 0
    # Re-run: the clone already exists on the target day → conflict → skipped.
    resp2 = await client.post(
        "/api/v1/lectures/copy-to-next-day",
        params={"branch_id": BRANCH_A_ID, "source_date": src_date},
    )
    assert resp2.json()["copied"] == 0
    assert resp2.json()["skipped"] == 1


# ─── Teacher productivity ─────────────────────────────────────────────────────

async def test_productivity_after_completion(client: AsyncClient, seed_data):
    await _login_admin(client)
    now = datetime.now(timezone.utc)
    start = now + timedelta(hours=40)
    lecture = (await client.post(
        "/api/v1/lectures", json=_payload(start, start + timedelta(hours=1))
    )).json()
    # Backfill actuals → completed with a known duration.
    await client.patch(
        f"/api/v1/lectures/{lecture['id']}/actuals",
        params={"branch_id": BRANCH_A_ID},
        json={
            "actual_start": start.isoformat(),
            "actual_end": (start + timedelta(minutes=90)).isoformat(),
        },
    )
    resp = await client.get(
        "/api/v1/lectures/insights/productivity",
        params={"branch_id": BRANCH_A_ID},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["summary"]["total_lectures"] >= 1
    rows = [r for r in body["by_teacher"] if r["teacher_id"] == TEACHER_ID]
    assert rows and rows[0]["hours_taught"] >= 1.5
