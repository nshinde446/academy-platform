"""Teacher↔Subject assignment — the in-app path that makes the Subject→Teacher
schedule lock usable (create with subjects, edit subjects, options)."""

from datetime import datetime, timedelta, timezone

from httpx import AsyncClient

BRANCH_A_ID = "00000000-0000-0000-0000-000000000001"
BATCH_ID = "00000000-0000-0000-0000-000000000070"
CLASSROOM_ID = "00000000-0000-0000-0000-000000000080"
SUBJECT_ID = "00000000-0000-0000-0000-000000000050"


async def _login_admin(client: AsyncClient):
    resp = await client.post("/api/v1/auth/login", json={
        "email": "admin@test.com",
        "password": "Admin123!",
    })
    assert resp.status_code == 200


async def test_subject_options_lists_branch_subjects(client: AsyncClient, seed_data):
    await _login_admin(client)
    resp = await client.get(
        "/api/v1/teachers/subject-options", params={"branch_id": BRANCH_A_ID}
    )
    assert resp.status_code == 200
    assert "Physics" in resp.json()


async def test_create_teacher_with_subjects_is_schedulable(client: AsyncClient, seed_data):
    """A teacher created with subjects=["Physics"] is immediately offered by the
    Subject→Teacher dropdown and passes the schedule lock."""
    await _login_admin(client)
    resp = await client.post(
        "/api/v1/teachers",
        json={
            "branch_id": BRANCH_A_ID,
            "first_name": "New",
            "last_name": "Physicist",
            "subjects": ["Physics"],
        },
    )
    assert resp.status_code == 200, resp.text
    new_id = resp.json()["id"]

    # Reflected in the teacher's subjects.
    resp = await client.get(
        f"/api/v1/teachers/{new_id}/subjects", params={"branch_id": BRANCH_A_ID}
    )
    assert resp.status_code == 200
    assert resp.json()["subjects"] == ["Physics"]

    # And in the subject-filtered dropdown.
    resp = await client.get(
        "/api/v1/teachers/by-subject",
        params={"branch_id": BRANCH_A_ID, "subject_id": SUBJECT_ID},
    )
    assert new_id in [t["id"] for t in resp.json()]

    # So the schedule lock now accepts them.
    now = datetime.now(timezone.utc)
    resp = await client.post(
        "/api/v1/lectures",
        json={
            "teacher_id": new_id,
            "batch_id": BATCH_ID,
            "classroom_id": CLASSROOM_ID,
            "subject_id": SUBJECT_ID,
            "scheduled_start": (now + timedelta(hours=50)).isoformat(),
            "scheduled_end": (now + timedelta(hours=51)).isoformat(),
            "delivery_mode": "offline",
        },
    )
    assert resp.status_code == 200, resp.text


async def test_set_subjects_then_unset(client: AsyncClient, seed_data):
    await _login_admin(client)
    teacher = (await client.post(
        "/api/v1/teachers",
        json={"branch_id": BRANCH_A_ID, "first_name": "Edit", "last_name": "Me"},
    )).json()
    tid = teacher["id"]

    # Initially none.
    resp = await client.get(
        f"/api/v1/teachers/{tid}/subjects", params={"branch_id": BRANCH_A_ID}
    )
    assert resp.json()["subjects"] == []

    # Assign Physics.
    resp = await client.put(
        f"/api/v1/teachers/{tid}/subjects",
        params={"branch_id": BRANCH_A_ID},
        json={"subjects": ["Physics"]},
    )
    assert resp.status_code == 200
    assert resp.json()["subjects"] == ["Physics"]

    # Clear it again (idempotent replace).
    resp = await client.put(
        f"/api/v1/teachers/{tid}/subjects",
        params={"branch_id": BRANCH_A_ID},
        json={"subjects": []},
    )
    assert resp.status_code == 200
    assert resp.json()["subjects"] == []
