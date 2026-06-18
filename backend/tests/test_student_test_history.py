"""Tier 13 — /students/{id}/test-history smoke tests.

Covers the per-test batch + institute ranking that powers the
/students/[id] dashboard.
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.student.models.student_models import (
    Student,
    StudentBatchMapping,
)

BRANCH_A_ID = "00000000-0000-0000-0000-000000000001"
BATCH_A_ID = "00000000-0000-0000-0000-000000000070"
BATCH_B_ID = "00000000-0000-0000-0000-000000000071"
SUBJECT_ID = "00000000-0000-0000-0000-000000000050"
ACADEMIC_YEAR_ID = "00000000-0000-0000-0000-000000000030"
STUDENT_A_ID = "00000000-0000-0000-0000-000000000090"
STUDENT_B_ID = "00000000-0000-0000-0000-0000000000b1"
STUDENT_C_ID = "00000000-0000-0000-0000-0000000000c1"


async def _login_admin(client: AsyncClient):
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.com", "password": "Admin123!"},
    )
    assert resp.status_code == 200


async def _seed_extra_students(session: AsyncSession):
    """Adds two extra students so we can verify batch vs institute rank."""
    session.add_all([
        Student(
            id=uuid.UUID(STUDENT_B_ID),
            branch_id=uuid.UUID(BRANCH_A_ID),
            academic_year_id=uuid.UUID(ACADEMIC_YEAR_ID),
            first_name="Batch",
            last_name="Mate",
            status="active",
        ),
        Student(
            id=uuid.UUID(STUDENT_C_ID),
            branch_id=uuid.UUID(BRANCH_A_ID),
            academic_year_id=uuid.UUID(ACADEMIC_YEAR_ID),
            first_name="Other",
            last_name="Batch",
            status="active",
        ),
        StudentBatchMapping(
            student_id=uuid.UUID(STUDENT_A_ID),
            batch_id=uuid.UUID(BATCH_A_ID),
            branch_id=uuid.UUID(BRANCH_A_ID),
            status="active",
        ),
        StudentBatchMapping(
            student_id=uuid.UUID(STUDENT_B_ID),
            batch_id=uuid.UUID(BATCH_A_ID),
            branch_id=uuid.UUID(BRANCH_A_ID),
            status="active",
        ),
        StudentBatchMapping(
            student_id=uuid.UUID(STUDENT_C_ID),
            batch_id=uuid.UUID(BATCH_B_ID),
            branch_id=uuid.UUID(BRANCH_A_ID),
            status="active",
        ),
    ])
    await session.commit()


async def _create_test(client: AsyncClient, name: str) -> dict:
    resp = await client.post(
        "/api/v1/tests",
        json={
            "name": name,
            "description": "smoke",
            "batch_id": BATCH_A_ID,
            "subject_id": SUBJECT_ID,
            "duration_minutes": 60,
            "total_marks": 100.0,
        },
    )
    assert resp.status_code == 200
    return resp.json()


async def _submit_marks(client: AsyncClient, test_id: str, marks: list[dict]):
    resp = await client.post(
        "/api/v1/marks",
        params={"test_id": test_id, "branch_id": BRANCH_A_ID},
        json={"marks": marks},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_history_empty_when_no_marks(client: AsyncClient, seed_data):
    await _login_admin(client)
    resp = await client.get(
        f"/api/v1/students/{STUDENT_A_ID}/test-history",
        params={"branch_id": BRANCH_A_ID},
    )
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_history_returns_batch_and_institute_rank(
    client: AsyncClient, db_session: AsyncSession, seed_data
):
    await _login_admin(client)
    await _seed_extra_students(db_session)

    test = await _create_test(client, "Physics Unit Test")
    # Student A — 90%, Batch peer B — 80%, Other-batch C — 95%.
    await _submit_marks(client, test["id"], [
        {"student_id": STUDENT_A_ID, "marks_obtained": 90.0},
        {"student_id": STUDENT_B_ID, "marks_obtained": 80.0},
        {"student_id": STUDENT_C_ID, "marks_obtained": 95.0},
    ])

    resp = await client.get(
        f"/api/v1/students/{STUDENT_A_ID}/test-history",
        params={"branch_id": BRANCH_A_ID},
    )
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 1
    row = rows[0]
    assert row["test_name"] == "Physics Unit Test"
    assert row["subject_name"] == "Physics"
    assert row["marks_obtained"] == 90.0
    assert row["percentage"] == 90.0
    # 90% beats batch-mate's 80% → batch rank 1 of 2.
    assert row["batch_rank"] == 1
    assert row["batch_size"] == 2
    # 95% from other-batch student outranks A → institute rank 2 of 3.
    assert row["institute_rank"] == 2
    assert row["institute_size"] == 3


@pytest.mark.asyncio
async def test_history_excludes_absent_from_rank(
    client: AsyncClient, db_session: AsyncSession, seed_data
):
    await _login_admin(client)
    await _seed_extra_students(db_session)

    test = await _create_test(client, "Absentee Test")
    # B absent — should not get a rank for themselves, and A should be
    # ranked among the present cohort only.
    await _submit_marks(client, test["id"], [
        {"student_id": STUDENT_A_ID, "marks_obtained": 60.0},
        {"student_id": STUDENT_B_ID, "marks_obtained": 0.0, "is_absent": True},
    ])

    resp = await client.get(
        f"/api/v1/students/{STUDENT_B_ID}/test-history",
        params={"branch_id": BRANCH_A_ID},
    )
    rows = resp.json()
    assert len(rows) == 1
    assert rows[0]["is_absent"] is True
    assert rows[0]["batch_rank"] is None
    assert rows[0]["institute_rank"] is None

    resp = await client.get(
        f"/api/v1/students/{STUDENT_A_ID}/test-history",
        params={"branch_id": BRANCH_A_ID},
    )
    rows = resp.json()
    assert len(rows) == 1
    # A is the only present student in the batch.
    assert rows[0]["batch_rank"] == 1
    assert rows[0]["batch_size"] == 1


async def _seed_topic_responses(session: AsyncSession, test_id: str):
    """Two topics under the seeded Physics subject, four questions, and
    student A's responses: Kinematics 1/2 correct, Thermodynamics 0/2."""
    from app.modules.academic.models.academic_models import Chapter, Topic
    from app.modules.tests.models.test_models import Question, StudentResponse

    # Topics hang off a Chapter (Subject -> Chapter -> Topic); the mastery query
    # itself reaches Subject via Question.subject_id, not via the topic.
    chapter_id = uuid.UUID("00000000-0000-0000-0000-0000000000c9")
    session.add(
        Chapter(
            id=chapter_id,
            branch_id=uuid.UUID(BRANCH_A_ID),
            academic_year_id=uuid.UUID(ACADEMIC_YEAR_ID),
            subject_id=uuid.UUID(SUBJECT_ID),
            name="Mechanics",
            order=0,
        )
    )
    t_kin = uuid.UUID("00000000-0000-0000-0000-0000000000d1")
    t_thermo = uuid.UUID("00000000-0000-0000-0000-0000000000d2")
    session.add_all([
        Topic(
            id=t_kin,
            branch_id=uuid.UUID(BRANCH_A_ID),
            academic_year_id=uuid.UUID(ACADEMIC_YEAR_ID),
            chapter_id=chapter_id,
            name="Kinematics",
            order=0,
        ),
        Topic(
            id=t_thermo,
            branch_id=uuid.UUID(BRANCH_A_ID),
            academic_year_id=uuid.UUID(ACADEMIC_YEAR_ID),
            chapter_id=chapter_id,
            name="Thermodynamics",
            order=1,
        ),
    ])
    qids: dict[str, uuid.UUID] = {}
    questions = []
    for key, tid in [("a", t_kin), ("b", t_kin), ("c", t_thermo), ("d", t_thermo)]:
        qid = uuid.uuid4()
        qids[key] = qid
        questions.append(
            Question(
                id=qid,
                branch_id=uuid.UUID(BRANCH_A_ID),
                academic_year_id=uuid.UUID(ACADEMIC_YEAR_ID),
                subject_id=uuid.UUID(SUBJECT_ID),
                topic_id=tid,
                content=f"Q-{key}",
                correct_answer="A",
            )
        )
    session.add_all(questions)
    session.add_all([
        StudentResponse(
            student_id=uuid.UUID(STUDENT_A_ID),
            test_id=uuid.UUID(test_id),
            question_id=qids[key],
            is_correct=correct,
            branch_id=uuid.UUID(BRANCH_A_ID),
            academic_year_id=uuid.UUID(ACADEMIC_YEAR_ID),
        )
        for key, correct in [("a", True), ("b", False), ("c", False), ("d", False)]
    ])
    await session.commit()


@pytest.mark.asyncio
async def test_topic_mastery_empty_when_no_responses(
    client: AsyncClient, seed_data
):
    await _login_admin(client)
    resp = await client.get(
        f"/api/v1/students/{STUDENT_A_ID}/topic-mastery",
        params={"branch_id": BRANCH_A_ID},
    )
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_topic_mastery_aggregates_and_sorts_weakest_first(
    client: AsyncClient, db_session: AsyncSession, seed_data
):
    await _login_admin(client)
    test = await _create_test(client, "Physics Unit Test")
    await _seed_topic_responses(db_session, test["id"])

    resp = await client.get(
        f"/api/v1/students/{STUDENT_A_ID}/topic-mastery",
        params={"branch_id": BRANCH_A_ID},
    )
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 2
    # Weakest first: Thermodynamics 0% before Kinematics 50%.
    assert rows[0]["topic_name"] == "Thermodynamics"
    assert rows[0]["accuracy_pct"] == 0.0
    assert rows[0]["attempted"] == 2 and rows[0]["correct"] == 0
    assert rows[0]["subject_name"] == "Physics"
    assert rows[1]["topic_name"] == "Kinematics"
    assert rows[1]["accuracy_pct"] == 50.0
    assert rows[1]["attempted"] == 2 and rows[1]["correct"] == 1


async def _seed_scheduled_test(
    session: AsyncSession, test_id: str, name: str, scheduled_at
):
    from app.modules.tests.models.test_models import Test

    session.add(
        Test(
            id=uuid.UUID(test_id),
            name=name,
            batch_id=uuid.UUID(BATCH_A_ID),
            subject_id=uuid.UUID(SUBJECT_ID),
            scheduled_at=scheduled_at,
            branch_id=uuid.UUID(BRANCH_A_ID),
            academic_year_id=uuid.UUID(ACADEMIC_YEAR_ID),
        )
    )
    await session.commit()


async def _seed_mark(session: AsyncSession, test_id: str, student_id: str):
    from app.modules.tests.models.test_models import StudentMark

    session.add(
        StudentMark(
            student_id=uuid.UUID(student_id),
            test_id=uuid.UUID(test_id),
            marks_obtained=50.0,
            max_marks=100.0,
            percentage=50.0,
            branch_id=uuid.UUID(BRANCH_A_ID),
            academic_year_id=uuid.UUID(ACADEMIC_YEAR_ID),
        )
    )
    await session.commit()


@pytest.mark.asyncio
async def test_upcoming_tests_empty_without_batch(client: AsyncClient, seed_data):
    await _login_admin(client)
    resp = await client.get(
        f"/api/v1/students/{STUDENT_A_ID}/upcoming-tests",
        params={"branch_id": BRANCH_A_ID},
    )
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_upcoming_tests_lists_future_untaken_soonest_first(
    client: AsyncClient, db_session: AsyncSession, seed_data
):
    from datetime import datetime, timezone

    await _login_admin(client)
    await _seed_extra_students(db_session)  # maps STUDENT_A -> BATCH_A
    await _seed_scheduled_test(
        db_session,
        "00000000-0000-0000-0000-0000000000e1",
        "Future Test",
        datetime(2030, 1, 1, tzinfo=timezone.utc),
    )
    await _seed_scheduled_test(
        db_session,
        "00000000-0000-0000-0000-0000000000e2",
        "Past Test",
        datetime(2020, 1, 1, tzinfo=timezone.utc),
    )
    await _seed_scheduled_test(
        db_session,
        "00000000-0000-0000-0000-0000000000e3",
        "Sooner Test",
        datetime(2029, 1, 1, tzinfo=timezone.utc),
    )

    resp = await client.get(
        f"/api/v1/students/{STUDENT_A_ID}/upcoming-tests",
        params={"branch_id": BRANCH_A_ID},
    )
    assert resp.status_code == 200
    names = [r["test_name"] for r in resp.json()]
    # Soonest first; the past test is excluded.
    assert names == ["Sooner Test", "Future Test"]


@pytest.mark.asyncio
async def test_upcoming_tests_excludes_already_taken(
    client: AsyncClient, db_session: AsyncSession, seed_data
):
    from datetime import datetime, timezone

    await _login_admin(client)
    await _seed_extra_students(db_session)
    await _seed_scheduled_test(
        db_session,
        "00000000-0000-0000-0000-0000000000e4",
        "Taken Future Test",
        datetime(2031, 1, 1, tzinfo=timezone.utc),
    )
    await _seed_mark(
        db_session, "00000000-0000-0000-0000-0000000000e4", STUDENT_A_ID
    )

    resp = await client.get(
        f"/api/v1/students/{STUDENT_A_ID}/upcoming-tests",
        params={"branch_id": BRANCH_A_ID},
    )
    assert resp.status_code == 200
    assert all(r["test_name"] != "Taken Future Test" for r in resp.json())
