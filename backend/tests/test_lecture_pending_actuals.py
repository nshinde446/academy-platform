"""End-of-day worklist: GET /lectures/pending-actuals.

Past lectures (scheduled end elapsed) still scheduled/started/paused surface
as needing their end-of-day update; future and already-resolved ones don't.
"""

from datetime import datetime, timedelta, timezone

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


async def _schedule(client: AsyncClient, start: datetime, end: datetime) -> str:
    resp = await client.post(
        "/api/v1/lectures",
        json={
            "teacher_id": TEACHER_ID,
            "batch_id": BATCH_A_ID,
            "classroom_id": CLASSROOM_ID,
            "subject_id": SUBJECT_ID,
            "scheduled_start": start.isoformat(),
            "scheduled_end": end.isoformat(),
            "delivery_mode": "offline",
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


async def _pending(client: AsyncClient) -> list[dict]:
    resp = await client.get(
        "/api/v1/lectures/pending-actuals", params={"branch_id": BRANCH_A_ID}
    )
    assert resp.status_code == 200
    return resp.json()


@pytest.mark.asyncio
async def test_empty_when_nothing_overdue(client: AsyncClient, seed_data):
    await _login_admin(client)
    assert await _pending(client) == []


@pytest.mark.asyncio
async def test_past_unresolved_lecture_is_pending(client: AsyncClient, seed_data):
    await _login_admin(client)
    now = datetime.now(timezone.utc)
    past = await _schedule(client, now - timedelta(hours=4), now - timedelta(hours=3))
    # A future lecture must NOT appear.
    await _schedule(client, now + timedelta(hours=3), now + timedelta(hours=4))

    rows = await _pending(client)
    ids = [r["id"] for r in rows]
    assert past in ids
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_completed_lecture_drops_off(
    client: AsyncClient, seed_data
):
    await _login_admin(client)
    now = datetime.now(timezone.utc)
    lid = await _schedule(client, now - timedelta(hours=4), now - timedelta(hours=3))
    assert len(await _pending(client)) == 1

    # Record actuals (completes it) → it leaves the worklist.
    resp = await client.patch(
        f"/api/v1/lectures/{lid}/actuals",
        params={"branch_id": BRANCH_A_ID},
        json={
            "actual_start": (now - timedelta(hours=4)).isoformat(),
            "actual_end": (now - timedelta(hours=3)).isoformat(),
        },
    )
    assert resp.status_code == 200
    assert await _pending(client) == []


@pytest.mark.asyncio
async def test_cancelled_lecture_not_pending(client: AsyncClient, seed_data):
    await _login_admin(client)
    now = datetime.now(timezone.utc)
    lid = await _schedule(client, now - timedelta(hours=4), now - timedelta(hours=3))
    await client.patch(
        f"/api/v1/lectures/{lid}/cancel", params={"branch_id": BRANCH_A_ID}
    )
    assert await _pending(client) == []
