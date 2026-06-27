"""Makeup queue: GET /lectures/pending-makeups.

Cancelled / no-show lectures with no linked makeup session surface as owing a
makeup; recording a makeup session (or otherwise resolving) drops them off.
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


async def _schedule(client: AsyncClient, hours_ahead: int = 5) -> str:
    now = datetime.now(timezone.utc)
    start = now + timedelta(hours=hours_ahead)
    resp = await client.post(
        "/api/v1/lectures",
        json={
            "teacher_id": TEACHER_ID,
            "batch_id": BATCH_A_ID,
            "classroom_id": CLASSROOM_ID,
            "subject_id": SUBJECT_ID,
            "scheduled_start": start.isoformat(),
            "scheduled_end": (start + timedelta(hours=1)).isoformat(),
            "delivery_mode": "offline",
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


async def _makeups(client: AsyncClient) -> list[dict]:
    resp = await client.get(
        "/api/v1/lectures/pending-makeups", params={"branch_id": BRANCH_A_ID}
    )
    assert resp.status_code == 200
    return resp.json()


@pytest.mark.asyncio
async def test_empty_when_nothing_missed(client: AsyncClient, seed_data):
    await _login_admin(client)
    await _schedule(client)  # a plain scheduled lecture is not owed a makeup
    assert await _makeups(client) == []


@pytest.mark.asyncio
async def test_cancelled_and_no_show_are_queued(client: AsyncClient, seed_data):
    await _login_admin(client)
    cancelled = await _schedule(client, 5)
    await client.patch(
        f"/api/v1/lectures/{cancelled}/cancel", params={"branch_id": BRANCH_A_ID}
    )
    noshow = await _schedule(client, 7)
    await client.patch(
        f"/api/v1/lectures/{noshow}/no-show",
        params={"branch_id": BRANCH_A_ID},
        json={"no_show_reason": "EXTERNAL"},
    )

    ids = [r["id"] for r in await _makeups(client)]
    assert cancelled in ids
    assert noshow in ids
    assert len(ids) == 2


@pytest.mark.asyncio
async def test_recording_makeup_drops_it_off(client: AsyncClient, seed_data):
    await _login_admin(client)
    cancelled = await _schedule(client, 5)
    await client.patch(
        f"/api/v1/lectures/{cancelled}/cancel", params={"branch_id": BRANCH_A_ID}
    )
    assert len(await _makeups(client)) == 1

    # Record a makeup session linked to the cancelled lecture.
    now = datetime.now(timezone.utc)
    resp = await client.post(
        "/api/v1/lectures/sessions",
        params={"branch_id": BRANCH_A_ID},
        json={
            "teacher_id": TEACHER_ID,
            "subject_id": SUBJECT_ID,
            "batch_ids": [BATCH_A_ID],
            "lecture_ids": [cancelled],
            "classroom_id": CLASSROOM_ID,
            "actual_start": now.isoformat(),
            "delivery_mode": "offline",
            "origin": "makeup",
        },
    )
    assert resp.status_code == 200, resp.text
    # Linked → covered → no longer owed a makeup.
    assert await _makeups(client) == []
