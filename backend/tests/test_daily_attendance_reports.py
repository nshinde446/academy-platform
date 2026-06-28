"""Day-attendance report endpoints (B8) — both reference files + the %.

Reference A = per-student timeline; Reference B = classroom P/A register;
summary = present working days / working days (decision 1).
"""

from datetime import date, datetime, timezone

import pytest
from httpx import AsyncClient

from app.modules.attendance.models.attendance_models import DailyAttendance
from app.modules.lectures.models.lecture_models import Lecture
from app.modules.student.models.student_models import StudentBatchMapping

BRANCH_A = "00000000-0000-0000-0000-000000000001"
BATCH_ID = "00000000-0000-0000-0000-000000000070"
STUDENT_ID = "00000000-0000-0000-0000-000000000090"


async def _login(client: AsyncClient):
    resp = await client.post("/api/v1/auth/login", json={
        "email": "admin@test.com", "password": "Admin123!",
    })
    assert resp.status_code == 200


def _day_row(seed_data, *, d, status, first_in=None, last_out=None, signoff="MISSING"):
    return DailyAttendance(
        student_id=seed_data["student"].id, branch_id=seed_data["branch_a"].id,
        attendance_date=d, first_in=first_in, last_out=last_out,
        day_status=status, signoff=signoff, source="BIOMETRIC",
    )


def _lecture(seed_data, *, start):
    return Lecture(
        teacher_id=seed_data["teacher"].id, batch_id=seed_data["batch"].id,
        subject_id=seed_data["subject"].id, academic_year_id=seed_data["academic_year"].id,
        scheduled_start=start, scheduled_end=start.replace(hour=start.hour + 2),
        branch_id=seed_data["branch_a"].id, status="active", is_deleted=False,
    )


async def test_classroom_register(client: AsyncClient, seed_data, db_session):
    db_session.add(StudentBatchMapping(
        student_id=seed_data["student"].id, batch_id=seed_data["batch"].id,
        branch_id=seed_data["branch_a"].id, status="active", is_deleted=False,
    ))
    db_session.add(_day_row(
        seed_data, d=date(2026, 6, 22), status="PRESENT",
        first_in=datetime(2026, 6, 22, 3, 59, tzinfo=timezone.utc),
    ))
    await db_session.commit()

    await _login(client)
    resp = await client.get("/api/v1/attendance/daily/register", params={
        "branch_id": BRANCH_A, "batch_id": BATCH_ID, "day": "2026-06-22",
    })
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 1
    assert rows[0]["mark"] == "P"
    assert rows[0]["student_id"] == STUDENT_ID


async def test_student_timeline(client: AsyncClient, seed_data, db_session):
    db_session.add(_day_row(seed_data, d=date(2026, 6, 22), status="PRESENT"))
    db_session.add(_day_row(seed_data, d=date(2026, 6, 23), status="ABSENT", signoff="NA"))
    await db_session.commit()

    await _login(client)
    resp = await client.get(f"/api/v1/attendance/daily/student/{STUDENT_ID}", params={
        "branch_id": BRANCH_A, "start": "2026-06-01", "end": "2026-06-30",
    })
    assert resp.status_code == 200
    rows = resp.json()
    assert [r["attendance_date"] for r in rows] == ["2026-06-23", "2026-06-22"]  # newest first


async def test_summary_percentage(client: AsyncClient, seed_data, db_session):
    db_session.add(StudentBatchMapping(
        student_id=seed_data["student"].id, batch_id=seed_data["batch"].id,
        branch_id=seed_data["branch_a"].id, status="active", is_deleted=False,
    ))
    # Two working days (lectures on 22nd & 23rd), present on only the 22nd.
    db_session.add(_lecture(seed_data, start=datetime(2026, 6, 22, 4, 30, tzinfo=timezone.utc)))
    db_session.add(_lecture(seed_data, start=datetime(2026, 6, 23, 4, 30, tzinfo=timezone.utc)))
    db_session.add(_day_row(seed_data, d=date(2026, 6, 22), status="PRESENT"))
    await db_session.commit()

    await _login(client)
    resp = await client.get(f"/api/v1/attendance/daily/summary/{STUDENT_ID}", params={
        "branch_id": BRANCH_A, "start": "2026-06-01", "end": "2026-06-30",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["working_days"] == 2
    assert body["present_days"] == 1
    assert body["attendance_pct"] == 50.0
