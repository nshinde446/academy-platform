"""S5 — teacher leave + substitute auto-suggest.

Covers /lectures/teacher-leaves CRUD, the scheduling block when a teacher is on
leave, and /lectures/{id}/eligible-substitutes (qualified ∩ free ∩ not-on-leave).
"""

import uuid
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.teacher.models.teacher_models import (
    Teacher,
    TeacherSubjectMapping,
)

BRANCH_A_ID = "00000000-0000-0000-0000-000000000001"
BATCH_A_ID = "00000000-0000-0000-0000-000000000070"
SUBJECT_ID = "00000000-0000-0000-0000-000000000050"
CLASSROOM_ID = "00000000-0000-0000-0000-000000000080"
TEACHER_ID = "00000000-0000-0000-0000-000000000060"
# A second Physics-qualified teacher we add for the substitute tests.
TEACHER2_ID = "00000000-0000-0000-0000-0000000000a2"


async def _login_admin(client: AsyncClient):
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.com", "password": "Admin123!"},
    )
    assert resp.status_code == 200


async def _seed_second_teacher(session: AsyncSession):
    session.add(
        Teacher(
            id=uuid.UUID(TEACHER2_ID),
            branch_id=uuid.UUID(BRANCH_A_ID),
            first_name="Second",
            last_name="Teacher",
            status="active",
        )
    )
    await session.flush()
    session.add(
        TeacherSubjectMapping(
            teacher_id=uuid.UUID(TEACHER2_ID),
            subject_id=uuid.UUID(SUBJECT_ID),
            branch_id=uuid.UUID(BRANCH_A_ID),
            status="active",
        )
    )
    await session.commit()


async def _schedule_lecture(client: AsyncClient, teacher_id: str, start: str, end: str):
    return await client.post(
        "/api/v1/lectures",
        json={
            "teacher_id": teacher_id,
            "batch_id": BATCH_A_ID,
            "classroom_id": CLASSROOM_ID,
            "subject_id": SUBJECT_ID,
            "scheduled_start": start,
            "scheduled_end": end,
            "delivery_mode": "offline",
        },
    )


async def _add_leave(client: AsyncClient, teacher_id: str, start: str, end: str):
    return await client.post(
        "/api/v1/lectures/teacher-leaves",
        params={"branch_id": BRANCH_A_ID},
        json={"teacher_id": teacher_id, "start_date": start, "end_date": end},
    )


@pytest.mark.asyncio
async def test_add_list_delete_leave(client: AsyncClient, seed_data):
    await _login_admin(client)
    resp = await _add_leave(client, TEACHER_ID, "2026-06-10", "2026-06-12")
    assert resp.status_code == 200
    leave_id = resp.json()["id"]

    resp = await client.get(
        "/api/v1/lectures/teacher-leaves", params={"branch_id": BRANCH_A_ID}
    )
    assert len(resp.json()) == 1

    resp = await client.delete(
        f"/api/v1/lectures/teacher-leaves/{leave_id}",
        params={"branch_id": BRANCH_A_ID},
    )
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_cannot_schedule_teacher_on_leave(client: AsyncClient, seed_data):
    await _login_admin(client)
    await _add_leave(client, TEACHER_ID, "2026-06-10", "2026-06-10")
    resp = await _schedule_lecture(
        client, TEACHER_ID, "2026-06-10T09:00:00Z", "2026-06-10T10:00:00Z"
    )
    assert resp.status_code == 422
    assert "on leave" in resp.json()["error"]["message"]


@pytest.mark.asyncio
async def test_eligible_substitutes_excludes_scheduled_and_unqualified(
    client: AsyncClient, db_session: AsyncSession, seed_data
):
    await _login_admin(client)
    await _seed_second_teacher(db_session)

    created = await _schedule_lecture(
        client, TEACHER_ID, "2026-06-15T09:00:00Z", "2026-06-15T10:00:00Z"
    )
    assert created.status_code == 200
    lecture_id = created.json()["id"]

    resp = await client.get(
        f"/api/v1/lectures/{lecture_id}/eligible-substitutes",
        params={"branch_id": BRANCH_A_ID},
    )
    assert resp.status_code == 200
    ids = [r["teacher_id"] for r in resp.json()]
    # The qualified second teacher is eligible; the scheduled teacher is not.
    assert TEACHER2_ID in ids
    assert TEACHER_ID not in ids


@pytest.mark.asyncio
async def test_eligible_substitutes_excludes_on_leave(
    client: AsyncClient, db_session: AsyncSession, seed_data
):
    await _login_admin(client)
    await _seed_second_teacher(db_session)

    created = await _schedule_lecture(
        client, TEACHER_ID, "2026-06-15T09:00:00Z", "2026-06-15T10:00:00Z"
    )
    lecture_id = created.json()["id"]

    # Put the only candidate substitute on leave that day → no eligibles.
    await _add_leave(client, TEACHER2_ID, "2026-06-15", "2026-06-15")
    resp = await client.get(
        f"/api/v1/lectures/{lecture_id}/eligible-substitutes",
        params={"branch_id": BRANCH_A_ID},
    )
    assert resp.json() == []
