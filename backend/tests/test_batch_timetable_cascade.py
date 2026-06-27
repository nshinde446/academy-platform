"""Batch deletion cleans up its timetable; orphan slots are skipped quietly.

Hardening after a prod incident: deleted batches had left their batch_schedules
behind, so the all-batches generator reported them as 'batch not found'.
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.batch.models.batch_models import Batch

BRANCH_A_ID = "00000000-0000-0000-0000-000000000001"
BATCH_B_ID = "00000000-0000-0000-0000-000000000071"
SUBJECT_ID = "00000000-0000-0000-0000-000000000050"
TEACHER_ID = "00000000-0000-0000-0000-000000000060"
CLASSROOM_ID = "00000000-0000-0000-0000-000000000080"


async def _login_admin(client: AsyncClient):
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.com", "password": "Admin123!"},
    )
    assert resp.status_code == 200


async def _put_monday_slot(client: AsyncClient):
    return await client.put(
        "/api/v1/lectures/timetable",
        params={"branch_id": BRANCH_A_ID, "batch_id": BATCH_B_ID},
        json={
            "slots": [
                {
                    "day_of_week": 0,
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


async def _generate_all(client: AsyncClient, day: str) -> dict:
    resp = await client.post(
        "/api/v1/lectures/timetable/generate",
        params={"branch_id": BRANCH_A_ID, "from_date": day, "to_date": day},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


@pytest.mark.asyncio
async def test_deleting_batch_clears_its_timetable(client: AsyncClient, seed_data):
    await _login_admin(client)
    assert (await _put_monday_slot(client)).status_code == 200
    # All-batches generate on a Monday picks up the slot.
    assert (await _generate_all(client, "2026-06-01"))["generated"] == 1

    # Delete the batch → its timetable is cascaded away.
    resp = await client.delete(
        f"/api/v1/batches/{BATCH_B_ID}", params={"branch_id": BRANCH_A_ID}
    )
    assert resp.status_code == 204

    # Its timetable is gone (batch no longer exists).
    tt = await client.get(
        "/api/v1/lectures/timetable",
        params={"branch_id": BRANCH_A_ID, "batch_id": BATCH_B_ID},
    )
    assert tt.status_code == 404

    # A later Monday generates nothing from the deleted batch, with no
    # "batch not found" noise.
    body = await _generate_all(client, "2026-06-08")
    assert body["generated"] == 0
    assert all("batch not found" not in e for e in body["errors"])


@pytest.mark.asyncio
async def test_all_batches_generate_skips_orphan_slots_quietly(
    client: AsyncClient, db_session: AsyncSession, seed_data
):
    await _login_admin(client)
    assert (await _put_monday_slot(client)).status_code == 200

    # Simulate a pre-fix orphan: soft-delete the batch WITHOUT cascading, so its
    # slot lingers. The generator must ignore it silently.
    batch = await db_session.get(Batch, uuid.UUID(BATCH_B_ID))
    batch.is_deleted = True
    await db_session.commit()

    body = await _generate_all(client, "2026-06-01")
    assert body["generated"] == 0
    assert all("batch not found" not in e for e in body["errors"])
