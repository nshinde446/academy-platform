"""S4 — holiday calendar + scheduler skipping.

Covers /lectures/holidays CRUD and that the timetable generator and
copy-to-next-day skip non-teaching days.
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


async def _add_holiday(client: AsyncClient, day: str, name: str):
    return await client.post(
        "/api/v1/lectures/holidays",
        params={"branch_id": BRANCH_A_ID},
        json={"holiday_date": day, "name": name},
    )


async def _put_monday_timetable(client: AsyncClient):
    return await client.put(
        "/api/v1/lectures/timetable",
        params={"branch_id": BRANCH_A_ID, "batch_id": BATCH_A_ID},
        json={
            "slots": [
                {
                    "day_of_week": 0,  # Monday
                    "start_time": "09:00",
                    "end_time": "10:00",
                    "subject_id": SUBJECT_ID,
                    "teacher_id": TEACHER_ID,
                    "classroom_id": CLASSROOM_ID,
                    "delivery_mode": "offline",
                }
            ]
        },
    )


@pytest.mark.asyncio
async def test_add_list_delete_holiday(client: AsyncClient, seed_data):
    await _login_admin(client)
    resp = await _add_holiday(client, "2026-06-08", "Founder's Day")
    assert resp.status_code == 200
    holiday_id = resp.json()["id"]

    resp = await client.get(
        "/api/v1/lectures/holidays", params={"branch_id": BRANCH_A_ID}
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["name"] == "Founder's Day"

    resp = await client.delete(
        f"/api/v1/lectures/holidays/{holiday_id}",
        params={"branch_id": BRANCH_A_ID},
    )
    assert resp.status_code == 204

    resp = await client.get(
        "/api/v1/lectures/holidays", params={"branch_id": BRANCH_A_ID}
    )
    assert resp.json() == []


@pytest.mark.asyncio
async def test_duplicate_holiday_rejected(client: AsyncClient, seed_data):
    await _login_admin(client)
    assert (await _add_holiday(client, "2026-06-08", "A")).status_code == 200
    dup = await _add_holiday(client, "2026-06-08", "B")
    assert dup.status_code == 409


@pytest.mark.asyncio
async def test_generate_skips_holiday(client: AsyncClient, seed_data):
    await _login_admin(client)
    await _put_monday_timetable(client)
    # 06-01 and 06-08 are Mondays; mark 06-08 a holiday → only 06-01 generates.
    await _add_holiday(client, "2026-06-08", "Holiday")
    resp = await client.post(
        "/api/v1/lectures/timetable/generate",
        params={
            "branch_id": BRANCH_A_ID,
            "batch_id": BATCH_A_ID,
            "from_date": "2026-06-01",
            "to_date": "2026-06-14",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["generated"] == 1


@pytest.mark.asyncio
async def test_copy_onto_holiday_copies_nothing(client: AsyncClient, seed_data):
    await _login_admin(client)
    # Seed one lecture on 2026-06-01 (Monday) via the timetable generator.
    await _put_monday_timetable(client)
    await client.post(
        "/api/v1/lectures/timetable/generate",
        params={
            "branch_id": BRANCH_A_ID,
            "batch_id": BATCH_A_ID,
            "from_date": "2026-06-01",
            "to_date": "2026-06-01",
        },
    )
    # 06-02 is a holiday → copying 06-01 → 06-02 copies nothing.
    await _add_holiday(client, "2026-06-02", "Holiday")
    resp = await client.post(
        "/api/v1/lectures/copy-to-next-day",
        params={
            "branch_id": BRANCH_A_ID,
            "source_date": "2026-06-01",
            "target_date": "2026-06-02",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["copied"] == 0
    assert "holiday" in body["errors"][0].lower()
