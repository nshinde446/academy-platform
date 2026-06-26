"""End-of-day actuals must not be recordable for a future-scheduled lecture.

A lecture scheduled for a future day hasn't happened, so it can't have
actuals / be completed. Today and past remain allowed (EOD backfill).
"""

import pytest
from httpx import AsyncClient

BRANCH_A_ID = "00000000-0000-0000-0000-000000000001"
BATCH_A_ID = "00000000-0000-0000-0000-000000000070"
SUBJECT_ID = "00000000-0000-0000-0000-000000000050"
TEACHER_ID = "00000000-0000-0000-0000-000000000060"
CLASSROOM_ID = "00000000-0000-0000-0000-000000000080"


async def _login_admin(client: AsyncClient):
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.com", "password": "Admin123!"},
    )
    assert resp.status_code == 200


async def _schedule(client: AsyncClient, start: str, end: str) -> str:
    resp = await client.post(
        "/api/v1/lectures",
        json={
            "teacher_id": TEACHER_ID,
            "batch_id": BATCH_A_ID,
            "classroom_id": CLASSROOM_ID,
            "subject_id": SUBJECT_ID,
            "scheduled_start": start,
            "scheduled_end": end,
            "delivery_mode": "offline",
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_actuals_rejected_for_future_lecture(client: AsyncClient, seed_data):
    await _login_admin(client)
    lid = await _schedule(client, "2099-01-01T14:30:00Z", "2099-01-01T15:30:00Z")
    resp = await client.patch(
        f"/api/v1/lectures/{lid}/actuals",
        params={"branch_id": BRANCH_A_ID},
        json={
            "actual_start": "2099-01-01T14:30:00Z",
            "actual_end": "2099-01-01T15:30:00Z",
        },
    )
    assert resp.status_code == 422
    assert "future" in resp.json()["error"]["message"].lower()


@pytest.mark.asyncio
async def test_actuals_allowed_for_past_lecture(client: AsyncClient, seed_data):
    await _login_admin(client)
    lid = await _schedule(client, "2020-01-01T09:00:00Z", "2020-01-01T10:00:00Z")
    resp = await client.patch(
        f"/api/v1/lectures/{lid}/actuals",
        params={"branch_id": BRANCH_A_ID},
        json={
            "actual_start": "2020-01-01T09:05:00Z",
            "actual_end": "2020-01-01T10:00:00Z",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["lecture_status"] == "completed"
