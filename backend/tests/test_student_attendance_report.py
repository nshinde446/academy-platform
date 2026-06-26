"""S2 — /students/{id}/attendance-report and /topics-missed.

Covers the per-student attendance breakdown and the "topics taught while you
were absent" catch-up list that surface on the /students/[id] profile.
"""

import uuid
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.academic.models.academic_models import Chapter, Topic
from app.modules.lectures.models.lecture_models import (
    Lecture,
    LectureAttendanceMapping,
)

BRANCH_A_ID = "00000000-0000-0000-0000-000000000001"
BATCH_A_ID = "00000000-0000-0000-0000-000000000070"
SUBJECT_ID = "00000000-0000-0000-0000-000000000050"
TEACHER_ID = "00000000-0000-0000-0000-000000000060"
ACADEMIC_YEAR_ID = "00000000-0000-0000-0000-000000000030"
STUDENT_A_ID = "00000000-0000-0000-0000-000000000090"

CHAPTER_ID = uuid.UUID("00000000-0000-0000-0000-0000000000ca")
TOPIC_KIN = uuid.UUID("00000000-0000-0000-0000-0000000000da")
TOPIC_THERMO = uuid.UUID("00000000-0000-0000-0000-0000000000db")


async def _login_admin(client: AsyncClient):
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.com", "password": "Admin123!"},
    )
    assert resp.status_code == 200


async def _seed_topics(session: AsyncSession):
    session.add(
        Chapter(
            id=CHAPTER_ID,
            branch_id=uuid.UUID(BRANCH_A_ID),
            academic_year_id=uuid.UUID(ACADEMIC_YEAR_ID),
            subject_id=uuid.UUID(SUBJECT_ID),
            name="Mechanics",
            order=0,
        )
    )
    session.add_all([
        Topic(
            id=TOPIC_KIN,
            branch_id=uuid.UUID(BRANCH_A_ID),
            academic_year_id=uuid.UUID(ACADEMIC_YEAR_ID),
            chapter_id=CHAPTER_ID,
            name="Kinematics",
            order=0,
        ),
        Topic(
            id=TOPIC_THERMO,
            branch_id=uuid.UUID(BRANCH_A_ID),
            academic_year_id=uuid.UUID(ACADEMIC_YEAR_ID),
            chapter_id=CHAPTER_ID,
            name="Thermodynamics",
            order=1,
        ),
    ])
    await session.flush()


def _lecture(lid: uuid.UUID, topic_id: uuid.UUID, hour: int) -> Lecture:
    start = datetime(2026, 5, 20, hour, 0, tzinfo=timezone.utc)
    return Lecture(
        id=lid,
        teacher_id=uuid.UUID(TEACHER_ID),
        batch_id=uuid.UUID(BATCH_A_ID),
        subject_id=uuid.UUID(SUBJECT_ID),
        topic_id=topic_id,
        scheduled_start=start,
        scheduled_end=start.replace(hour=hour + 1),
        delivery_mode="offline",
        lecture_status="completed",
        branch_id=uuid.UUID(BRANCH_A_ID),
        academic_year_id=uuid.UUID(ACADEMIC_YEAR_ID),
    )


def _attendance(lid: uuid.UUID, status_: str) -> LectureAttendanceMapping:
    return LectureAttendanceMapping(
        lecture_id=lid,
        student_id=uuid.UUID(STUDENT_A_ID),
        attendance_status=status_,
        marked_at=datetime(2026, 5, 20, 12, 0, tzinfo=timezone.utc),
        branch_id=uuid.UUID(BRANCH_A_ID),
    )


async def _seed_attendance(session: AsyncSession):
    """Three completed Physics lectures for student A:
      L1 Kinematics    @09:00 → PRESENT
      L2 Thermodynamics@11:00 → ABSENT
      L3 Kinematics    @13:00 → EXCUSED
    """
    await _seed_topics(session)
    l1 = uuid.UUID("00000000-0000-0000-0000-0000000000f1")
    l2 = uuid.UUID("00000000-0000-0000-0000-0000000000f2")
    l3 = uuid.UUID("00000000-0000-0000-0000-0000000000f3")
    session.add_all([
        _lecture(l1, TOPIC_KIN, 9),
        _lecture(l2, TOPIC_THERMO, 11),
        _lecture(l3, TOPIC_KIN, 13),
    ])
    await session.flush()
    session.add_all([
        _attendance(l1, "PRESENT"),
        _attendance(l2, "ABSENT"),
        _attendance(l3, "EXCUSED"),
    ])
    await session.commit()


@pytest.mark.asyncio
async def test_attendance_report_empty(client: AsyncClient, seed_data):
    await _login_admin(client)
    resp = await client.get(
        f"/api/v1/students/{STUDENT_A_ID}/attendance-report",
        params={"branch_id": BRANCH_A_ID},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"held": 0, "present": 0, "attendance_pct": 0.0, "by_subject": []}


@pytest.mark.asyncio
async def test_attendance_report_overall_and_by_subject(
    client: AsyncClient, db_session: AsyncSession, seed_data
):
    await _login_admin(client)
    await _seed_attendance(db_session)

    resp = await client.get(
        f"/api/v1/students/{STUDENT_A_ID}/attendance-report",
        params={"branch_id": BRANCH_A_ID},
    )
    assert resp.status_code == 200
    body = resp.json()
    # 1 PRESENT out of 3 held = 33.3% — matches the roster card definition.
    assert body["held"] == 3
    assert body["present"] == 1
    assert body["attendance_pct"] == 33.3
    assert len(body["by_subject"]) == 1
    phy = body["by_subject"][0]
    assert phy["subject_name"] == "Physics"
    assert phy["held"] == 3
    assert phy["present"] == 1
    assert phy["attendance_pct"] == 33.3


@pytest.mark.asyncio
async def test_topics_missed_lists_absent_and_excused_recent_first(
    client: AsyncClient, db_session: AsyncSession, seed_data
):
    await _login_admin(client)
    await _seed_attendance(db_session)

    resp = await client.get(
        f"/api/v1/students/{STUDENT_A_ID}/topics-missed",
        params={"branch_id": BRANCH_A_ID},
    )
    assert resp.status_code == 200
    rows = resp.json()
    # PRESENT Kinematics lecture is excluded; the ABSENT + EXCUSED ones surface.
    assert len(rows) == 2
    # Most recent first: the 13:00 EXCUSED Kinematics, then 11:00 ABSENT Thermo.
    assert rows[0]["topic_name"] == "Kinematics"
    assert rows[0]["attendance_status"] == "EXCUSED"
    assert rows[1]["topic_name"] == "Thermodynamics"
    assert rows[1]["attendance_status"] == "ABSENT"
    assert rows[1]["subject_name"] == "Physics"
