"""S3 — recurring weekly timetable (batch_schedules) → lecture generation.

Covers PUT/GET /lectures/timetable and POST /lectures/timetable/generate:
the Subject→Teacher lock on save, weekday matching, conflict-aware idempotent
generation, and skipping of incomplete slots.
"""

import uuid

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


def _slot(day: int, start: str, end: str, **over) -> dict:
    s = {
        "day_of_week": day,
        "start_time": start,
        "end_time": end,
        "subject_id": SUBJECT_ID,
        "teacher_id": TEACHER_ID,
        "classroom_id": CLASSROOM_ID,
        "delivery_mode": "offline",
    }
    s.update(over)
    return s


async def _put_timetable(client: AsyncClient, slots: list[dict]):
    return await client.put(
        "/api/v1/lectures/timetable",
        params={"branch_id": BRANCH_A_ID, "batch_id": BATCH_A_ID},
        json={"slots": slots},
    )


@pytest.mark.asyncio
async def test_set_and_get_timetable(client: AsyncClient, seed_data):
    await _login_admin(client)
    # Monday 09:00–10:00 and Wednesday 11:00–12:30.
    resp = await _put_timetable(client, [_slot(0, "09:00", "10:00"), _slot(2, "11:00", "12:30")])
    assert resp.status_code == 200
    slots = resp.json()
    assert len(slots) == 2
    assert {s["day_of_week"] for s in slots} == {0, 2}

    resp = await client.get(
        "/api/v1/lectures/timetable",
        params={"branch_id": BRANCH_A_ID, "batch_id": BATCH_A_ID},
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_set_timetable_replaces(client: AsyncClient, seed_data):
    await _login_admin(client)
    await _put_timetable(client, [_slot(0, "09:00", "10:00")])
    # Replace with a single different slot — the old one is gone.
    resp = await _put_timetable(client, [_slot(4, "14:00", "15:00")])
    assert resp.status_code == 200
    slots = resp.json()
    assert len(slots) == 1
    assert slots[0]["day_of_week"] == 4


@pytest.mark.asyncio
async def test_set_timetable_rejects_bad_time(client: AsyncClient, seed_data):
    await _login_admin(client)
    resp = await _put_timetable(client, [_slot(0, "10:00", "09:00")])
    assert resp.status_code == 422
    assert "after start_time" in resp.json()["error"]["message"]


@pytest.mark.asyncio
async def test_set_timetable_enforces_teacher_subject_lock(
    client: AsyncClient, seed_data
):
    await _login_admin(client)
    # A teacher id that doesn't teach the subject (random uuid).
    bad_teacher = str(uuid.uuid4())
    resp = await _put_timetable(
        client, [_slot(0, "09:00", "10:00", teacher_id=bad_teacher)]
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_generate_creates_lectures_on_matching_weekdays(
    client: AsyncClient, seed_data
):
    await _login_admin(client)
    # Monday slot only.
    await _put_timetable(client, [_slot(0, "09:00", "10:00")])
    # 2026-06-01 is a Monday; the range 06-01..06-14 contains two Mondays
    # (06-01 and 06-08).
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
    body = resp.json()
    assert body["generated"] == 2
    assert body["skipped"] == 0


@pytest.mark.asyncio
async def test_generate_is_idempotent_on_rerun(client: AsyncClient, seed_data):
    await _login_admin(client)
    await _put_timetable(client, [_slot(0, "09:00", "10:00")])
    params = {
        "branch_id": BRANCH_A_ID,
        "batch_id": BATCH_A_ID,
        "from_date": "2026-06-01",
        "to_date": "2026-06-14",
    }
    first = await client.post("/api/v1/lectures/timetable/generate", params=params)
    assert first.json()["generated"] == 2
    # Second run collides with the lectures just created → all skipped.
    second = await client.post("/api/v1/lectures/timetable/generate", params=params)
    body = second.json()
    assert body["generated"] == 0
    assert body["skipped"] == 2


@pytest.mark.asyncio
async def test_generate_skips_incomplete_slot(client: AsyncClient, seed_data):
    await _login_admin(client)
    # Slot with no teacher/subject — can't generate a lecture.
    await _put_timetable(
        client,
        [_slot(0, "09:00", "10:00", subject_id=None, teacher_id=None)],
    )
    resp = await client.post(
        "/api/v1/lectures/timetable/generate",
        params={
            "branch_id": BRANCH_A_ID,
            "batch_id": BATCH_A_ID,
            "from_date": "2026-06-01",
            "to_date": "2026-06-07",
        },
    )
    body = resp.json()
    assert body["generated"] == 0
    assert body["skipped"] == 1
    assert "missing subject or teacher" in body["errors"][0]
