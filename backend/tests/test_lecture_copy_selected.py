"""Copy hand-picked lectures to a target date (POST /lectures/copy-selected).

Explicit row selection instead of the by-date copy_to_next_day — the admin
ticks which lectures to copy; conflict-, holiday-, and leave-aware.
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


async def _copy_selected(client: AsyncClient, ids: list[str], target: str):
    return await client.post(
        "/api/v1/lectures/copy-selected",
        params={"branch_id": BRANCH_A_ID},
        json={"lecture_ids": ids, "target_date": target},
    )


@pytest.mark.asyncio
async def test_copies_only_selected(client: AsyncClient, seed_data):
    await _login_admin(client)
    # Two lectures on Mon 2026-06-15; only the 09:00 one is selected.
    l1 = await _schedule(client, "2026-06-15T09:00:00Z", "2026-06-15T10:00:00Z")
    await _schedule(client, "2026-06-15T11:00:00Z", "2026-06-15T12:00:00Z")

    resp = await _copy_selected(client, [l1], "2026-06-16")
    assert resp.status_code == 200
    body = resp.json()
    assert body["copied"] == 1
    assert body["skipped"] == 0
    assert body["target_date"] == "2026-06-16"

    # The clone lands on 2026-06-16 at the same 09:00 time; the 11:00 lecture
    # was NOT selected, so nothing at 11:00 on the 16th.
    listing = (
        await client.get("/api/v1/lectures", params={"branch_id": BRANCH_A_ID})
    ).json()
    on_16 = [l for l in listing if l["scheduled_start"].startswith("2026-06-16")]
    assert len(on_16) == 1
    assert "09:00" in on_16[0]["scheduled_start"]


@pytest.mark.asyncio
async def test_rerun_is_idempotent(client: AsyncClient, seed_data):
    await _login_admin(client)
    l1 = await _schedule(client, "2026-06-15T09:00:00Z", "2026-06-15T10:00:00Z")
    first = await _copy_selected(client, [l1], "2026-06-16")
    assert first.json()["copied"] == 1
    # Second copy collides with the clone just made → skipped, not duplicated.
    second = await _copy_selected(client, [l1], "2026-06-16")
    body = second.json()
    assert body["copied"] == 0
    assert body["skipped"] == 1


@pytest.mark.asyncio
async def test_empty_selection_rejected(client: AsyncClient, seed_data):
    await _login_admin(client)
    resp = await _copy_selected(client, [], "2026-06-16")
    assert resp.status_code == 422
    assert "at least one" in resp.json()["error"]["message"].lower()


@pytest.mark.asyncio
async def test_skips_when_target_is_holiday(client: AsyncClient, seed_data):
    await _login_admin(client)
    l1 = await _schedule(client, "2026-06-15T09:00:00Z", "2026-06-15T10:00:00Z")
    await client.post(
        "/api/v1/lectures/holidays",
        params={"branch_id": BRANCH_A_ID},
        json={"holiday_date": "2026-06-16", "name": "Holiday"},
    )
    resp = await _copy_selected(client, [l1], "2026-06-16")
    body = resp.json()
    assert body["copied"] == 0
    assert body["skipped"] == 1
    assert "holiday" in body["errors"][0].lower()
