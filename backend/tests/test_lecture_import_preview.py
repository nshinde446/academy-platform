"""S6 — schedule import dry-run preview.

POST /lectures/import/preview validates every row (codes, times, the
Subject→Teacher lock, conflicts) and reports per-row status without creating
any lectures.
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.batch.models.batch_models import BatchSubjectMapping

BRANCH_A_ID = "00000000-0000-0000-0000-000000000001"
BATCH_A_ID = "00000000-0000-0000-0000-000000000070"
SUBJECT_ID = "00000000-0000-0000-0000-000000000050"


async def _login_admin(client: AsyncClient):
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.com", "password": "Admin123!"},
    )
    assert resp.status_code == 200


async def _map_subject_to_batch(session: AsyncSession):
    session.add(
        BatchSubjectMapping(
            batch_id=uuid.UUID(BATCH_A_ID),
            subject_id=uuid.UUID(SUBJECT_ID),
            branch_id=uuid.UUID(BRANCH_A_ID),
            status="active",
        )
    )
    await session.commit()


HEADER = "date,start_time,end_time,teacher_email,batch_code,subject_code\n"


async def _preview(client: AsyncClient, csv_text: str):
    return await client.post(
        "/api/v1/lectures/import/preview",
        params={"branch_id": BRANCH_A_ID},
        files={"file": ("schedule.csv", csv_text.encode(), "text/csv")},
    )


@pytest.mark.asyncio
async def test_preview_marks_valid_row_ok(
    client: AsyncClient, db_session: AsyncSession, seed_data
):
    await _login_admin(client)
    await _map_subject_to_batch(db_session)

    csv_text = HEADER + "2026-06-01,09:00,10:00,teacher@test.com,BATCH-A,PHY\n"
    resp = await _preview(client, csv_text)
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok_count"] == 1
    assert body["error_count"] == 0
    assert body["rows"][0]["status"] == "ok"

    # Dry-run must NOT have created a lecture.
    listing = await client.get(
        "/api/v1/lectures", params={"branch_id": BRANCH_A_ID}
    )
    assert listing.json() == []


@pytest.mark.asyncio
async def test_preview_flags_unknown_batch(
    client: AsyncClient, db_session: AsyncSession, seed_data
):
    await _login_admin(client)
    await _map_subject_to_batch(db_session)

    csv_text = HEADER + "2026-06-01,09:00,10:00,teacher@test.com,NOPE,PHY\n"
    resp = await _preview(client, csv_text)
    body = resp.json()
    assert body["ok_count"] == 0
    assert body["error_count"] == 1
    assert body["rows"][0]["status"] == "error"
    assert "batch_code" in body["rows"][0]["message"]


@pytest.mark.asyncio
async def test_preview_flags_bad_time(
    client: AsyncClient, db_session: AsyncSession, seed_data
):
    await _login_admin(client)
    await _map_subject_to_batch(db_session)

    csv_text = HEADER + "2026-06-01,10:00,09:00,teacher@test.com,BATCH-A,PHY\n"
    resp = await _preview(client, csv_text)
    body = resp.json()
    assert body["error_count"] == 1
    assert "after start_time" in body["rows"][0]["message"]


@pytest.mark.asyncio
async def test_preview_missing_required_columns(client: AsyncClient, seed_data):
    await _login_admin(client)
    csv_text = "date,start_time\n2026-06-01,09:00\n"
    resp = await _preview(client, csv_text)
    assert resp.status_code == 400
    assert "Missing required columns" in resp.json()["error"]["message"]
