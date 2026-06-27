"""GET /lectures/in-range — the week/calendar window query."""

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
async def test_in_range_returns_only_window(client: AsyncClient, seed_data):
    await _login_admin(client)
    before = await _schedule(
        client, "2026-06-22T09:00:00Z", "2026-06-22T10:00:00Z"
    )
    inside = await _schedule(
        client, "2026-06-24T09:00:00Z", "2026-06-24T10:00:00Z"
    )
    after = await _schedule(
        client, "2026-06-30T09:00:00Z", "2026-06-30T10:00:00Z"
    )

    # Window covering Mon 2026-06-22? No — pick Wed..Sat window 06-23..06-29.
    resp = await client.get(
        "/api/v1/lectures/in-range",
        params={
            "branch_id": BRANCH_A_ID,
            "from_date": "2026-06-23T00:00:00Z",
            "to_date": "2026-06-29T00:00:00Z",
        },
    )
    assert resp.status_code == 200
    ids = [r["id"] for r in resp.json()]
    assert inside in ids
    assert before not in ids
    assert after not in ids
