"""Per-course subject management — the Courses "Subjects" manager.

Covers seeding a course's subjects from a syllabus preset (idempotent),
listing the syllabus presets, manual delete with the in-use guard, and the
admin-only gate. This is what makes a manually-created batch's course
schedulable (its subject dropdown was empty before).
"""

import uuid
from datetime import datetime, timezone

import pytest

from app.modules.lectures.models.lecture_models import Lecture

BRANCH = "00000000-0000-0000-0000-000000000001"
AY = "00000000-0000-0000-0000-000000000030"
SEEDED_SUBJECT = "00000000-0000-0000-0000-000000000050"
TEACHER = "00000000-0000-0000-0000-000000000060"
BATCH = "00000000-0000-0000-0000-000000000070"


async def _admin_token(client):
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.com", "password": "Admin123!"},
    )
    return resp.cookies["access_token"]


async def _teacher_token(client):
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "teacher@test.com", "password": "Teacher123!"},
    )
    return resp.cookies["access_token"]


async def _empty_course(client, token, code):
    resp = await client.post(
        "/api/v1/academic/courses",
        json={"branch_id": BRANCH, "name": f"Course {code}", "code": code},
        cookies={"access_token": token},
    )
    assert resp.status_code == 200
    return resp.json()["id"]


@pytest.mark.usefixtures("seed_data")
async def test_seed_from_syllabus_creates_subjects(client, seed_data):
    token = await _admin_token(client)
    course_id = await _empty_course(client, token, "CET2-01")

    # Starts empty — this is the "No subjects for this course" state.
    before = await client.get(
        f"/api/v1/academic/subjects?branch_id={BRANCH}&course_id={course_id}",
        cookies={"access_token": token},
    )
    assert before.json() == []

    resp = await client.post(
        "/api/v1/academic/subjects/seed",
        json={"branch_id": BRANCH, "course_id": course_id, "syllabus_key": "JEE"},
        cookies={"access_token": token},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["created"] == 3
    names = {s["name"] for s in body["subjects"]}
    assert names == {"Physics", "Chemistry", "Mathematics"}
    # Every seeded subject is scoped to the target course.
    assert all(s["course_id"] == course_id for s in body["subjects"])


@pytest.mark.usefixtures("seed_data")
async def test_seed_is_idempotent(client, seed_data):
    token = await _admin_token(client)
    course_id = await _empty_course(client, token, "CET2-02")

    first = await client.post(
        "/api/v1/academic/subjects/seed",
        json={"branch_id": BRANCH, "course_id": course_id, "syllabus_key": "MHT-CET"},
        cookies={"access_token": token},
    )
    assert first.json()["created"] == 4

    # Re-seeding never duplicates or clobbers an existing skeleton.
    again = await client.post(
        "/api/v1/academic/subjects/seed",
        json={"branch_id": BRANCH, "course_id": course_id, "syllabus_key": "JEE"},
        cookies={"access_token": token},
    )
    assert again.status_code == 200
    assert again.json()["created"] == 0
    assert len(again.json()["subjects"]) == 4


@pytest.mark.usefixtures("seed_data")
async def test_seed_unknown_syllabus_400(client, seed_data):
    token = await _admin_token(client)
    course_id = await _empty_course(client, token, "CET2-03")
    resp = await client.post(
        "/api/v1/academic/subjects/seed",
        json={"branch_id": BRANCH, "course_id": course_id, "syllabus_key": "NONSENSE"},
        cookies={"access_token": token},
    )
    assert resp.status_code == 400


@pytest.mark.usefixtures("seed_data")
async def test_list_syllabi(client, seed_data):
    token = await _admin_token(client)
    resp = await client.get(
        "/api/v1/academic/syllabi", cookies={"access_token": token}
    )
    assert resp.status_code == 200
    keys = {o["key"] for o in resp.json()}
    assert {"JEE", "NEET", "MHT-CET"} <= keys
    jee = next(o for o in resp.json() if o["key"] == "JEE")
    assert jee["subjects"] == ["Physics", "Chemistry", "Mathematics"]


@pytest.mark.usefixtures("seed_data")
async def test_delete_subject(client, seed_data):
    token = await _admin_token(client)
    course_id = await _empty_course(client, token, "CET2-04")
    created = await client.post(
        "/api/v1/academic/subjects",
        json={
            "branch_id": BRANCH,
            "academic_year_id": AY,
            "course_id": course_id,
            "name": "Temp",
            "code": "TMP",
        },
        cookies={"access_token": token},
    )
    subject_id = created.json()["id"]

    resp = await client.delete(
        f"/api/v1/academic/subjects/{subject_id}?branch_id={BRANCH}",
        cookies={"access_token": token},
    )
    assert resp.status_code == 204

    listing = await client.get(
        f"/api/v1/academic/subjects?branch_id={BRANCH}&course_id={course_id}",
        cookies={"access_token": token},
    )
    assert subject_id not in {s["id"] for s in listing.json()}


@pytest.mark.usefixtures("seed_data")
async def test_delete_subject_blocked_when_lecture_uses_it(client, seed_data, db_session):
    token = await _admin_token(client)
    db_session.add(
        Lecture(
            id=uuid.uuid4(),
            branch_id=uuid.UUID(BRANCH),
            academic_year_id=uuid.UUID(AY),
            teacher_id=uuid.UUID(TEACHER),
            batch_id=uuid.UUID(BATCH),
            subject_id=uuid.UUID(SEEDED_SUBJECT),
            scheduled_start=datetime(2026, 8, 4, 12, 0, tzinfo=timezone.utc),
            scheduled_end=datetime(2026, 8, 4, 13, 0, tzinfo=timezone.utc),
        )
    )
    await db_session.commit()

    resp = await client.delete(
        f"/api/v1/academic/subjects/{SEEDED_SUBJECT}?branch_id={BRANCH}",
        cookies={"access_token": token},
    )
    assert resp.status_code == 409


@pytest.mark.usefixtures("seed_data")
async def test_seed_and_delete_are_admin_only(client, seed_data):
    token = await _teacher_token(client)
    seed = await client.post(
        "/api/v1/academic/subjects/seed",
        json={"branch_id": BRANCH, "course_id": "00000000-0000-0000-0000-000000000040", "syllabus_key": "JEE"},
        cookies={"access_token": token},
    )
    assert seed.status_code == 403
    delete = await client.delete(
        f"/api/v1/academic/subjects/{SEEDED_SUBJECT}?branch_id={BRANCH}",
        cookies={"access_token": token},
    )
    assert delete.status_code == 403
