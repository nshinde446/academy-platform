"""Per-batch WhatsApp notification selection (pilot control).

The branch master switch is all-or-nothing; this feature adds a per-batch opt-in
under it. A parent message is only produced when the student's batch is in the
enabled set. Empty set => notify nobody. Covers: the repo round-trip (toggle on /
off / on), that the absent sweep still MARKS everyone but only NOTIFIES enabled
batches, and the GET/PUT API with branch isolation.
"""

import uuid
from datetime import date, datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.modules.attendance.services import daily_service
from app.modules.events.models.event_models import AcademicEvent
from app.modules.lectures.models.lecture_models import Lecture
from app.modules.notifications.repositories import notification_repository
from app.modules.student.models.student_models import Student, StudentBatchMapping

BRANCH_A_ID = "00000000-0000-0000-0000-000000000001"
DAY = date(2026, 6, 22)


async def _login_admin(client: AsyncClient):
    resp = await client.post("/api/v1/auth/login", json={
        "email": "admin@test.com", "password": "Admin123!",
    })
    assert resp.status_code == 200


# ─── repository round-trip ──────────────────────────────────────────────────


async def test_set_enabled_batches_toggle_on_off_on(db_session, seed_data):
    branch_id = seed_data["branch_a"].id
    a = seed_data["batch"].id
    b = seed_data["batch_b"].id

    assert await notification_repository.enabled_whatsapp_batch_ids(
        db_session, branch_id
    ) == set()

    await notification_repository.set_enabled_whatsapp_batches(
        db_session, branch_id, {a, b}
    )
    assert await notification_repository.enabled_whatsapp_batch_ids(
        db_session, branch_id
    ) == {a, b}

    # Narrow to just A (B is soft-deleted).
    await notification_repository.set_enabled_whatsapp_batches(
        db_session, branch_id, {a}
    )
    assert await notification_repository.enabled_whatsapp_batch_ids(
        db_session, branch_id
    ) == {a}

    # Re-enable B — must revive the soft-deleted row, not trip the unique index.
    await notification_repository.set_enabled_whatsapp_batches(
        db_session, branch_id, {a, b}
    )
    assert await notification_repository.enabled_whatsapp_batch_ids(
        db_session, branch_id
    ) == {a, b}

    # Clear everything.
    await notification_repository.set_enabled_whatsapp_batches(
        db_session, branch_id, set()
    )
    assert await notification_repository.enabled_whatsapp_batch_ids(
        db_session, branch_id
    ) == set()


# ─── gating: mark everyone, notify only enabled batches ─────────────────────


async def _two_batch_working_day(db_session, seed_data):
    """Student A in batch A, student B in batch B, both with a lecture on DAY."""
    branch = seed_data["branch_a"]
    batch_a = seed_data["batch"]
    batch_b = seed_data["batch_b"]
    student_a = seed_data["student"]
    student_a.parent_mobile = "9876500001"

    student_b = Student(
        id=uuid.UUID("00000000-0000-0000-0000-0000000000c2"),
        branch_id=branch.id,
        academic_year_id=seed_data["academic_year"].id,
        first_name="Bee", last_name="Kid",
        enrollment_number="STU-B2",
        parent_mobile="9876500002",
        status="active", is_deleted=False,
    )
    db_session.add(student_b)

    db_session.add_all([
        StudentBatchMapping(
            student_id=student_a.id, batch_id=batch_a.id, branch_id=branch.id,
            status="active", is_deleted=False,
        ),
        StudentBatchMapping(
            student_id=student_b.id, batch_id=batch_b.id, branch_id=branch.id,
            status="active", is_deleted=False,
        ),
    ])
    for bt in (batch_a, batch_b):
        db_session.add(Lecture(
            teacher_id=seed_data["teacher"].id, batch_id=bt.id,
            subject_id=seed_data["subject"].id,
            academic_year_id=seed_data["academic_year"].id,
            scheduled_start=datetime(2026, 6, 22, 4, 30, tzinfo=timezone.utc),
            scheduled_end=datetime(2026, 6, 22, 6, 30, tzinfo=timezone.utc),
            branch_id=branch.id, status="active", is_deleted=False,
        ))
    await db_session.flush()
    return branch, student_a, student_b


async def _absent_events(db_session):
    return list((await db_session.execute(
        select(AcademicEvent).where(
            AcademicEvent.event_type == "STUDENT_ABSENT"
        )
    )).scalars().all())


async def test_sweep_notifies_only_enabled_batch(db_session, seed_data):
    branch, student_a, student_b = await _two_batch_working_day(db_session, seed_data)
    # Enable ONLY batch A.
    await notification_repository.set_enabled_whatsapp_batches(
        db_session, branch.id, {seed_data["batch"].id}
    )

    created = await daily_service.run_absent_sweep(
        db_session, branch_id=branch.id, day=DAY, notify=True
    )
    # Both students marked ABSENT (data correctness is not gated).
    assert {r.student_id for r in created} == {student_a.id, student_b.id}

    # Only batch A's parent is notified.
    events = await _absent_events(db_session)
    assert [e.student_id for e in events] == [student_a.id]


async def test_sweep_no_enabled_batch_notifies_nobody(db_session, seed_data):
    branch, student_a, student_b = await _two_batch_working_day(db_session, seed_data)
    # No batch enabled (empty set is the default).

    created = await daily_service.run_absent_sweep(
        db_session, branch_id=branch.id, day=DAY, notify=True
    )
    assert {r.student_id for r in created} == {student_a.id, student_b.id}
    assert await _absent_events(db_session) == []


# ─── API: GET/PUT + branch isolation ────────────────────────────────────────


async def test_whatsapp_batches_get_put_and_isolation(client, seed_data):
    await _login_admin(client)
    batch_a = str(seed_data["batch"].id)
    batch_b = str(seed_data["batch_b"].id)

    # GET lists the branch's batches, all disabled by default.
    resp = await client.get(
        "/api/v1/notifications/whatsapp-batches", params={"branch_id": BRANCH_A_ID}
    )
    assert resp.status_code == 200
    rows = {r["batch_id"]: r for r in resp.json()}
    assert batch_a in rows and batch_b in rows
    assert rows[batch_a]["enabled"] is False

    # PUT enables only batch A.
    resp = await client.put(
        "/api/v1/notifications/whatsapp-batches",
        params={"branch_id": BRANCH_A_ID},
        json={"batch_ids": [batch_a]},
    )
    assert resp.status_code == 200
    rows = {r["batch_id"]: r for r in resp.json()}
    assert rows[batch_a]["enabled"] is True
    assert rows[batch_b]["enabled"] is False

    # Persisted.
    resp = await client.get(
        "/api/v1/notifications/whatsapp-batches", params={"branch_id": BRANCH_A_ID}
    )
    rows = {r["batch_id"]: r for r in resp.json()}
    assert rows[batch_a]["enabled"] is True

    # Branch isolation: a batch_id that isn't a live batch of this branch is rejected.
    resp = await client.put(
        "/api/v1/notifications/whatsapp-batches",
        params={"branch_id": BRANCH_A_ID},
        json={"batch_ids": [str(uuid.uuid4())]},
    )
    assert resp.status_code == 400
