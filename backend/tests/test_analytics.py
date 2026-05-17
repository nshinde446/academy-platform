import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.attendance.models.attendance_models import AttendanceRecord
from app.modules.student.models.student_models import StudentBatchMapping
from app.modules.tests.models.test_models import StudentMark, Test
from app.modules.lectures.models.lecture_models import Lecture

BRANCH_A_ID = "00000000-0000-0000-0000-000000000001"
BRANCH_B_ID = "00000000-0000-0000-0000-000000000002"
TEACHER_ID = "00000000-0000-0000-0000-000000000060"
BATCH_ID = "00000000-0000-0000-0000-000000000070"
CLASSROOM_ID = "00000000-0000-0000-0000-000000000080"
STUDENT_ID = "00000000-0000-0000-0000-000000000090"
SUBJECT_ID = "00000000-0000-0000-0000-000000000050"
ACADEMIC_YEAR_ID = "00000000-0000-0000-0000-000000000030"


async def _login_admin(client: AsyncClient):
    resp = await client.post("/api/v1/auth/login", json={
        "email": "admin@test.com",
        "password": "Admin123!",
    })
    assert resp.status_code == 200


async def _login_teacher(client: AsyncClient):
    resp = await client.post("/api/v1/auth/login", json={
        "email": "teacher@test.com",
        "password": "Teacher123!",
    })
    assert resp.status_code == 200


async def _seed_analytics_data(db_session: AsyncSession):
    now = datetime.now(timezone.utc)
    branch_id = uuid.UUID(BRANCH_A_ID)
    student_id = uuid.UUID(STUDENT_ID)
    teacher_id = uuid.UUID(TEACHER_ID)
    batch_id = uuid.UUID(BATCH_ID)
    subject_id = uuid.UUID(SUBJECT_ID)
    academic_year_id = uuid.UUID(ACADEMIC_YEAR_ID)

    sbm = StudentBatchMapping(
        student_id=student_id,
        batch_id=batch_id,
        branch_id=branch_id,
        status="active",
        is_deleted=False,
    )
    db_session.add(sbm)
    await db_session.flush()

    lecture = Lecture(
        id=uuid.UUID("00000000-0000-0000-0000-000000000a01"),
        teacher_id=teacher_id,
        batch_id=batch_id,
        classroom_id=uuid.UUID(CLASSROOM_ID),
        subject_id=subject_id,
        branch_id=branch_id,
        academic_year_id=academic_year_id,
        scheduled_start=now - timedelta(hours=2),
        scheduled_end=now - timedelta(hours=1),
        actual_start=now - timedelta(hours=2),
        actual_end=now - timedelta(hours=1),
        lecture_status="completed",
        delivery_mode="offline",
        status="active",
        is_deleted=False,
    )
    db_session.add(lecture)
    await db_session.flush()

    for i, att_status in enumerate(["PRESENT", "PRESENT", "ABSENT", "LATE"]):
        rec = AttendanceRecord(
            student_id=student_id,
            lecture_id=lecture.id,
            branch_id=branch_id,
            attendance_status=att_status,
            source="MANUAL",
            marked_at=now - timedelta(minutes=i),
            status="active",
            is_deleted=False,
        )
        db_session.add(rec)
    await db_session.flush()

    test_obj = Test(
        id=uuid.UUID("00000000-0000-0000-0000-000000000b01"),
        name="Analytics Test",
        batch_id=batch_id,
        subject_id=subject_id,
        branch_id=branch_id,
        academic_year_id=academic_year_id,
        duration_minutes=60,
        total_marks=100.0,
        test_status="published",
        status="active",
        is_deleted=False,
    )
    db_session.add(test_obj)
    await db_session.flush()

    mark = StudentMark(
        student_id=student_id,
        test_id=test_obj.id,
        branch_id=branch_id,
        academic_year_id=academic_year_id,
        marks_obtained=70.0,
        max_marks=100.0,
        percentage=70.0,
        grade="B",
        is_absent=False,
        status="active",
        is_deleted=False,
    )
    db_session.add(mark)
    await db_session.commit()


# ─── Test 1: Refresh analytics creates student summary ──────────────────────

async def test_refresh_creates_student_summary(client: AsyncClient, seed_data, db_session: AsyncSession):
    await _seed_analytics_data(db_session)
    await _login_admin(client)
    resp = await client.post(
        "/api/v1/analytics/refresh",
        params={"branch_id": BRANCH_A_ID, "academic_year_id": ACADEMIC_YEAR_ID},
    )
    assert resp.status_code == 200
    assert resp.json()["message"] == "Analytics refreshed successfully"


# ─── Test 2: Get student analytics after refresh ────────────────────────────

async def test_get_student_analytics(client: AsyncClient, seed_data, db_session: AsyncSession):
    await _seed_analytics_data(db_session)
    await _login_admin(client)
    await client.post(
        "/api/v1/analytics/refresh",
        params={"branch_id": BRANCH_A_ID, "academic_year_id": ACADEMIC_YEAR_ID},
    )
    resp = await client.get(
        f"/api/v1/analytics/students/{STUDENT_ID}",
        params={"branch_id": BRANCH_A_ID},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["student_id"] == STUDENT_ID
    assert data["total_attendance"] == 4
    assert data["present_count"] == 2
    assert data["absent_count"] == 1
    assert data["late_count"] == 1
    assert data["attendance_percentage"] == 50.0
    assert data["total_tests"] == 1
    assert data["average_score"] == 70.0


# ─── Test 3: Student risk score calculation ──────────────────────────────────

async def test_student_risk_score(client: AsyncClient, seed_data, db_session: AsyncSession):
    await _seed_analytics_data(db_session)
    await _login_admin(client)
    await client.post(
        "/api/v1/analytics/refresh",
        params={"branch_id": BRANCH_A_ID, "academic_year_id": ACADEMIC_YEAR_ID},
    )
    resp = await client.get(
        f"/api/v1/analytics/students/{STUDENT_ID}",
        params={"branch_id": BRANCH_A_ID},
    )
    data = resp.json()
    expected_risk = (100 - 50.0) * 0.6 + (100 - 70.0) * 0.4
    assert data["risk_score"] == expected_risk


# ─── Test 4: Get teacher analytics after refresh ────────────────────────────

async def test_get_teacher_analytics(client: AsyncClient, seed_data, db_session: AsyncSession):
    await _seed_analytics_data(db_session)
    await _login_admin(client)
    await client.post(
        "/api/v1/analytics/refresh",
        params={"branch_id": BRANCH_A_ID, "academic_year_id": ACADEMIC_YEAR_ID},
    )
    resp = await client.get(
        f"/api/v1/analytics/teachers/{TEACHER_ID}",
        params={"branch_id": BRANCH_A_ID},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["teacher_id"] == TEACHER_ID
    assert data["total_lectures"] == 1
    assert data["completed_lectures"] == 1
    assert data["completion_rate"] == 100.0


# ─── Test 5: Get batch analytics after refresh ──────────────────────────────

async def test_get_batch_analytics(client: AsyncClient, seed_data, db_session: AsyncSession):
    await _seed_analytics_data(db_session)
    await _login_admin(client)
    await client.post(
        "/api/v1/analytics/refresh",
        params={"branch_id": BRANCH_A_ID, "academic_year_id": ACADEMIC_YEAR_ID},
    )
    resp = await client.get(
        f"/api/v1/analytics/batches/{BATCH_ID}",
        params={"branch_id": BRANCH_A_ID},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["batch_id"] == BATCH_ID
    assert data["total_students"] == 1
    assert data["avg_score"] == 70.0


# ─── Test 6: Risk students endpoint ─────────────────────────────────────────

async def test_risk_students(client: AsyncClient, seed_data, db_session: AsyncSession):
    await _seed_analytics_data(db_session)
    await _login_admin(client)
    await client.post(
        "/api/v1/analytics/refresh",
        params={"branch_id": BRANCH_A_ID, "academic_year_id": ACADEMIC_YEAR_ID},
    )
    resp = await client.get(
        f"/api/v1/analytics/batches/{BATCH_ID}/risk-students",
        params={"branch_id": BRANCH_A_ID, "threshold": 30.0},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["student_id"] == STUDENT_ID
    assert data[0]["risk_score"] == 42.0


# ─── Test 7: Risk students with high threshold returns empty ────────────────

async def test_risk_students_high_threshold(client: AsyncClient, seed_data, db_session: AsyncSession):
    await _seed_analytics_data(db_session)
    await _login_admin(client)
    await client.post(
        "/api/v1/analytics/refresh",
        params={"branch_id": BRANCH_A_ID, "academic_year_id": ACADEMIC_YEAR_ID},
    )
    resp = await client.get(
        f"/api/v1/analytics/batches/{BATCH_ID}/risk-students",
        params={"branch_id": BRANCH_A_ID, "threshold": 99.0},
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 0


# ─── Test 8: Student analytics 404 when not refreshed ───────────────────────

async def test_student_analytics_not_found(client: AsyncClient, seed_data):
    await _login_admin(client)
    resp = await client.get(
        f"/api/v1/analytics/students/{STUDENT_ID}",
        params={"branch_id": BRANCH_A_ID},
    )
    assert resp.status_code == 404


# ─── Test 9: Teacher analytics 404 when not refreshed ───────────────────────

async def test_teacher_analytics_not_found(client: AsyncClient, seed_data):
    await _login_admin(client)
    resp = await client.get(
        f"/api/v1/analytics/teachers/{TEACHER_ID}",
        params={"branch_id": BRANCH_A_ID},
    )
    assert resp.status_code == 404


# ─── Test 10: Batch analytics 404 when not refreshed ────────────────────────

async def test_batch_analytics_not_found(client: AsyncClient, seed_data):
    await _login_admin(client)
    resp = await client.get(
        f"/api/v1/analytics/batches/{BATCH_ID}",
        params={"branch_id": BRANCH_A_ID},
    )
    assert resp.status_code == 404


# ─── Test 11: Refresh requires super_admin ───────────────────────────────────

async def test_refresh_requires_admin(client: AsyncClient, seed_data):
    await _login_teacher(client)
    resp = await client.post(
        "/api/v1/analytics/refresh",
        params={"branch_id": BRANCH_A_ID, "academic_year_id": ACADEMIC_YEAR_ID},
    )
    assert resp.status_code == 403


# ─── Test 12: Branch isolation – cross-branch returns 404 ───────────────────

async def test_branch_isolation(client: AsyncClient, seed_data, db_session: AsyncSession):
    await _seed_analytics_data(db_session)
    await _login_admin(client)
    await client.post(
        "/api/v1/analytics/refresh",
        params={"branch_id": BRANCH_A_ID, "academic_year_id": ACADEMIC_YEAR_ID},
    )
    resp = await client.get(
        f"/api/v1/analytics/students/{STUDENT_ID}",
        params={"branch_id": BRANCH_B_ID},
    )
    assert resp.status_code == 404


# ─── Test 13: Refresh creates audit log ──────────────────────────────────────

async def test_refresh_creates_audit_log(client: AsyncClient, seed_data, db_session: AsyncSession):
    await _seed_analytics_data(db_session)
    await _login_admin(client)
    await client.post(
        "/api/v1/analytics/refresh",
        params={"branch_id": BRANCH_A_ID, "academic_year_id": ACADEMIC_YEAR_ID},
    )
    resp = await client.get(
        "/api/v1/audit/logs",
        params={"table_name": "analytics"},
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert any(log["action"] == "REFRESH" and log["table_name"] == "analytics" for log in items)


# ─── Test 14: Batch with no students gets zero summary ──────────────────────

async def test_empty_batch_summary(client: AsyncClient, seed_data, db_session: AsyncSession):
    await _login_admin(client)
    await client.post(
        "/api/v1/analytics/refresh",
        params={"branch_id": BRANCH_A_ID, "academic_year_id": ACADEMIC_YEAR_ID},
    )
    batch_b_id = "00000000-0000-0000-0000-000000000071"
    resp = await client.get(
        f"/api/v1/analytics/batches/{batch_b_id}",
        params={"branch_id": BRANCH_A_ID},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_students"] == 0
    assert data["avg_attendance"] == 0.0
    assert data["avg_score"] == 0.0
