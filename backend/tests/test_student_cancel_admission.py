"""Point 4 — Cancel Admission keeps the record.

A cancelled admission must vanish from active lists yet stay recoverable and
listable, with its batch / cancel date / reason, and Restore must bring it back
exactly as before.
"""

import uuid

import pytest

from app.modules.student.models.student_models import Student, StudentBatchMapping
from app.modules.student.services import student_service

BRANCH = "00000000-0000-0000-0000-000000000001"


async def _login(client) -> str:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.com", "password": "Admin123!"},
    )
    return resp.cookies["access_token"]


def _csv(*lines: str) -> bytes:
    header = "Name,Class,Target,Batch,Roll No"
    return ("\n".join([header, *lines]) + "\n").encode("utf-8")


async def _import_two(client, token) -> list[dict]:
    await client.post(
        f"/api/v1/students/import?branch_id={BRANCH}",
        files={"file": ("s.csv", _csv("Asha,11,NEET,BATCH-A,C-1", "Bina,11,NEET,BATCH-A,C-2"), "text/csv")},
        cookies={"access_token": token},
    )
    roster = await client.get(
        f"/api/v1/students?branch_id={BRANCH}", cookies={"access_token": token}
    )
    return roster.json()


class TestCancelAdmission:
    @pytest.mark.usefixtures("seed_data")
    async def test_cancel_hides_but_keeps_and_lists(self, client, seed_data):
        token = await _login(client)
        students = await _import_two(client, token)
        assert len(students) >= 2
        target = students[0]

        resp = await client.post(
            f"/api/v1/students/{target['id']}/cancel-admission?branch_id={BRANCH}",
            json={"reason": "Shifted city"},
            cookies={"access_token": token},
        )
        assert resp.status_code == 200

        # Gone from the active roster and the stats roster.
        active = await client.get(
            f"/api/v1/students?branch_id={BRANCH}", cookies={"access_token": token}
        )
        assert target["id"] not in [s["id"] for s in active.json()]
        stats = await client.get(
            f"/api/v1/students/roster?branch_id={BRANCH}", cookies={"access_token": token}
        )
        assert target["id"] not in [s["id"] for s in stats.json()["items"]]

        # Present in the Cancelled Students tab with batch + reason + date.
        cancelled = await client.get(
            f"/api/v1/students/cancelled?branch_id={BRANCH}", cookies={"access_token": token}
        )
        rows = cancelled.json()
        row = next(r for r in rows if r["id"] == target["id"])
        assert row["cancellation_reason"] == "Shifted city"
        assert row["cancelled_at"] is not None
        # Batch field is part of the tab's row shape (value resolved from the
        # intact mapping; the batch-name resolution is covered precisely below).
        assert "batch_name" in row

    @pytest.mark.usefixtures("seed_data")
    async def test_restore_brings_back(self, client, seed_data):
        token = await _login(client)
        students = await _import_two(client, token)
        target = students[0]

        await client.post(
            f"/api/v1/students/{target['id']}/cancel-admission?branch_id={BRANCH}",
            json={"reason": None},
            cookies={"access_token": token},
        )
        restore = await client.post(
            f"/api/v1/students/{target['id']}/restore?branch_id={BRANCH}",
            cookies={"access_token": token},
        )
        assert restore.status_code == 200

        active = await client.get(
            f"/api/v1/students?branch_id={BRANCH}", cookies={"access_token": token}
        )
        assert target["id"] in [s["id"] for s in active.json()]
        cancelled = await client.get(
            f"/api/v1/students/cancelled?branch_id={BRANCH}", cookies={"access_token": token}
        )
        assert target["id"] not in [r["id"] for r in cancelled.json()]

    @pytest.mark.usefixtures("seed_data")
    async def test_restore_unknown_is_404(self, client, seed_data):
        token = await _login(client)
        students = await _import_two(client, token)
        # An active (never-cancelled) student can't be restored.
        resp = await client.post(
            f"/api/v1/students/{students[0]['id']}/restore?branch_id={BRANCH}",
            cookies={"access_token": token},
        )
        assert resp.status_code == 404


@pytest.mark.usefixtures("seed_data")
async def test_list_cancelled_shows_batch_and_round_trips(db_session, seed_data):
    """Service-level: a cancelled student with an intact batch mapping shows its
    batch name in the Cancelled tab; cancel soft-deletes and restore reverses."""
    branch_id = seed_data["branch_a"].id
    batch = seed_data["batch"]
    s = Student(
        id=uuid.uuid4(), branch_id=branch_id,
        academic_year_id=seed_data["academic_year"].id,
        first_name="Cancel", last_name="Me", enrollment_number="CANC-1",
        status="active", is_deleted=False,
    )
    db_session.add(s)
    db_session.add(StudentBatchMapping(
        student_id=s.id, batch_id=batch.id, branch_id=branch_id,
        status="active", is_deleted=False,
    ))
    await db_session.flush()

    await student_service.cancel_admission(
        db_session, s.id, branch_id, seed_data["admin_user"].id,
        reason="Fees not paid",
    )
    await db_session.flush()
    assert s.is_deleted is True and s.status == "cancelled"

    rows = await student_service.list_cancelled_students(db_session, branch_id)
    row = next(r for r in rows if r["id"] == s.id)
    assert row["batch_name"] == batch.name
    assert row["cancellation_reason"] == "Fees not paid"

    await student_service.restore_admission(
        db_session, s.id, branch_id, seed_data["admin_user"].id,
    )
    await db_session.flush()
    assert s.is_deleted is False and s.status == "active"
    assert s.cancelled_at is None and s.cancellation_reason is None
    assert all(r["id"] != s.id for r in await student_service.list_cancelled_students(db_session, branch_id))
