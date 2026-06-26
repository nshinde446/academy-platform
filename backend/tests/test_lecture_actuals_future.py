"""End-of-day actuals must not be recordable for a future-scheduled lecture.

A lecture scheduled for a future day hasn't happened, so it can't have
actuals / be completed. Today and past remain allowed (EOD backfill).
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.academic.models.academic_models import Chapter, Topic

BRANCH_A_ID = "00000000-0000-0000-0000-000000000001"
ACADEMIC_YEAR_ID = "00000000-0000-0000-0000-000000000030"
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
async def test_future_lecture_allows_topic_only_plan(
    client: AsyncClient, db_session: AsyncSession, seed_data
):
    """A generated/future lecture can have its planned topic set ahead of time
    (no actual times) — it just can't be marked completed."""
    await _login_admin(client)
    # Seed a topic under the seeded Physics subject.
    chapter_id = uuid.UUID("00000000-0000-0000-0000-0000000000e7")
    topic_id = uuid.UUID("00000000-0000-0000-0000-0000000000e8")
    db_session.add(
        Chapter(
            id=chapter_id,
            branch_id=uuid.UUID(BRANCH_A_ID),
            academic_year_id=uuid.UUID(ACADEMIC_YEAR_ID),
            subject_id=uuid.UUID(SUBJECT_ID),
            name="Mechanics",
            order=0,
        )
    )
    db_session.add(
        Topic(
            id=topic_id,
            branch_id=uuid.UUID(BRANCH_A_ID),
            academic_year_id=uuid.UUID(ACADEMIC_YEAR_ID),
            chapter_id=chapter_id,
            name="Friction",
            order=0,
        )
    )
    await db_session.commit()

    lid = await _schedule(client, "2099-01-01T14:30:00Z", "2099-01-01T15:30:00Z")
    resp = await client.patch(
        f"/api/v1/lectures/{lid}/actuals",
        params={"branch_id": BRANCH_A_ID},
        json={"topic_id": str(topic_id)},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # Topic is set, but it stays scheduled — not completed (no actuals recorded).
    assert body["topic_id"] == str(topic_id)
    assert body["lecture_status"] == "scheduled"
    assert body["actual_start"] is None


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
