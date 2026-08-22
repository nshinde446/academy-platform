"""Client priority changes — day report, manual mark, register rfid/source, notify.

Covers: the single-day report builders (PRN/RFID/In/Out/Status columns + counts),
the super-admin-only manual day mark (MANUAL row that survives a punch rebuild),
the register now carrying rfid_number + source, and the on-demand notify emitter.
"""

from datetime import date, datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.modules.attendance.models.attendance_models import DailyAttendance, RawPunchLog
from app.modules.attendance.services import (
    attendance_export_service as ex,
    daily_service,
)
from app.modules.events.models.event_models import AcademicEvent
from app.modules.lectures.models.lecture_models import Lecture
from app.modules.student.models.student_models import Student, StudentBatchMapping

BRANCH_A = "00000000-0000-0000-0000-000000000001"
BATCH_ID = "00000000-0000-0000-0000-000000000070"
STUDENT_ID = "00000000-0000-0000-0000-000000000090"
DAY = date(2026, 6, 22)
IST = "Asia/Kolkata"


async def _login_admin(client: AsyncClient):
    resp = await client.post("/api/v1/auth/login", json={
        "email": "admin@test.com", "password": "Admin123!",
    })
    assert resp.status_code == 200


async def _login_teacher(client: AsyncClient):
    resp = await client.post("/api/v1/auth/login", json={
        "email": "teacher@test.com", "password": "Teacher123!",
    })
    assert resp.status_code == 200


async def _enroll_present(db_session, seed_data):
    """Enrol the seed student in the batch with a PRESENT punch + rfid."""
    seed_data["student"].rfid_number = "6433012"
    db_session.add(StudentBatchMapping(
        student_id=seed_data["student"].id, batch_id=seed_data["batch"].id,
        branch_id=seed_data["branch_a"].id, status="active", is_deleted=False,
    ))
    db_session.add(DailyAttendance(
        student_id=seed_data["student"].id, branch_id=seed_data["branch_a"].id,
        attendance_date=DAY, day_status="PRESENT", signoff="COMPLETE",
        source="BIOMETRIC",
        first_in=datetime(2026, 6, 22, 2, 24, tzinfo=timezone.utc),
        last_out=datetime(2026, 6, 22, 5, 3, tzinfo=timezone.utc),
    ))
    await db_session.commit()


# ─── register now carries rfid_number + source ──────────────────────────────

async def test_register_returns_rfid_and_source(client, seed_data, db_session):
    await _enroll_present(db_session, seed_data)
    await _login_admin(client)
    resp = await client.get("/api/v1/attendance/daily/register", params={
        "branch_id": BRANCH_A, "batch_id": BATCH_ID, "day": DAY.isoformat(),
    })
    assert resp.status_code == 200
    row = resp.json()[0]
    assert row["rfid_number"] == "6433012"
    assert row["source"] == "BIOMETRIC"


# ─── day report builders (req 4) ────────────────────────────────────────────

def _rows():
    return [
        {"student_id": STUDENT_ID, "name": "Aarohi Kale", "enrollment_number": "2801037",
         "rfid_number": "6433012", "mark": "P", "day_status": "PRESENT",
         "first_in": datetime(2026, 6, 22, 2, 24, tzinfo=timezone.utc),
         "last_out": datetime(2026, 6, 22, 5, 3, tzinfo=timezone.utc), "source": "BIOMETRIC"},
        {"student_id": "x", "name": "Advait Kumthekar", "enrollment_number": "2801099",
         "rfid_number": None, "mark": "A", "day_status": "ABSENT",
         "first_in": None, "last_out": None, "source": "SYSTEM"},
        {"student_id": "y", "name": "Manual Mia", "enrollment_number": "2801100",
         "rfid_number": None, "mark": "P", "day_status": "PRESENT",
         "first_in": None, "last_out": None, "source": "MANUAL"},
    ]


def test_day_report_html_columns_and_counts():
    html = ex.day_report_html(
        brand="Matrix Science Academy", batch_name="11th Impulse 2",
        day=DAY, rows=_rows(), tz_name=IST,
    )
    for col in ("Sr. No.", "PRN", "Student Name", "RFID", "In Time", "Out Time", "Status"):
        assert col in html
    assert "11th Impulse 2" in html
    assert "Powered by EduPulse Technologies" in html
    assert "2801037" in html and "6433012" in html
    # 3 students, 2 present, 1 absent -> 66.7%
    assert "Total Present: <b>2</b>" in html
    assert "Total Absent: <b>1</b>" in html
    assert "Manual" in html  # manual tag on the hand-marked present row


def test_day_report_xlsx_builds():
    data = ex.day_report_xlsx(
        brand="Matrix Science Academy", batch_name="11th Impulse 2",
        day=DAY, rows=_rows(), tz_name=IST,
    )
    assert data[:2] == b"PK"  # a real xlsx (zip) container


async def test_day_report_endpoint_pdf(client, seed_data, db_session):
    await _enroll_present(db_session, seed_data)
    await _login_admin(client)
    resp = await client.get("/api/v1/attendance/reports/day", params={
        "branch_id": BRANCH_A, "batch_id": BATCH_ID, "day": DAY.isoformat(), "fmt": "xlsx",
    })
    assert resp.status_code == 200
    assert resp.content[:2] == b"PK"


# ─── manual mark (req 5) ────────────────────────────────────────────────────

async def test_manual_mark_creates_manual_row(client, seed_data, db_session):
    db_session.add(StudentBatchMapping(
        student_id=seed_data["student"].id, batch_id=seed_data["batch"].id,
        branch_id=seed_data["branch_a"].id, status="active", is_deleted=False,
    ))
    await db_session.commit()

    await _login_admin(client)
    resp = await client.post(
        "/api/v1/attendance/daily/mark",
        params={"branch_id": BRANCH_A},
        json={"student_id": STUDENT_ID, "day": DAY.isoformat(), "status": "PRESENT"},
    )
    assert resp.status_code == 200
    assert resp.json()["source"] == "MANUAL"
    assert resp.json()["day_status"] == "PRESENT"

    row = (await db_session.execute(
        select(DailyAttendance).where(DailyAttendance.student_id == seed_data["student"].id)
    )).scalar_one()
    assert row.source == "MANUAL"


async def test_manual_mark_survives_punch_rebuild(client, seed_data, db_session):
    await _login_admin(client)
    await client.post(
        "/api/v1/attendance/daily/mark",
        params={"branch_id": BRANCH_A},
        json={"student_id": STUDENT_ID, "day": DAY.isoformat(), "status": "PRESENT"},
    )
    # A later punch sync must not clobber the hand mark (decision 7).
    db_session.add(RawPunchLog(
        student_id=seed_data["student"].id, branch_id=seed_data["branch_a"].id,
        device_id="d1", punch_timestamp=datetime(2026, 6, 22, 4, 0, tzinfo=timezone.utc),
        is_deleted=False,
    ))
    await db_session.commit()
    await daily_service.rebuild_daily(
        db_session, student_id=seed_data["student"].id,
        branch_id=seed_data["branch_a"].id, day=DAY, tz_name=IST,
    )
    await db_session.commit()

    row = (await db_session.execute(
        select(DailyAttendance).where(DailyAttendance.student_id == seed_data["student"].id)
    )).scalar_one()
    assert row.source == "MANUAL"  # untouched


async def test_manual_mark_forbidden_for_teacher(client, seed_data, db_session):
    await _login_teacher(client)
    resp = await client.post(
        "/api/v1/attendance/daily/mark",
        params={"branch_id": BRANCH_A},
        json={"student_id": STUDENT_ID, "day": DAY.isoformat(), "status": "PRESENT"},
    )
    assert resp.status_code == 403


# ─── on-demand notify (extra #2) ────────────────────────────────────────────

async def test_notify_emits_event_per_student(client, seed_data, db_session):
    seed_data["student"].parent_mobile = "9876543210"
    db_session.add(DailyAttendance(
        student_id=seed_data["student"].id, branch_id=seed_data["branch_a"].id,
        attendance_date=DAY, day_status="ABSENT", signoff="NA", source="SYSTEM",
    ))
    await db_session.commit()

    await _login_admin(client)
    resp = await client.post(
        "/api/v1/attendance/daily/notify",
        params={"branch_id": BRANCH_A},
        json={"batch_id": BATCH_ID, "day": DAY.isoformat(), "student_ids": [STUDENT_ID]},
    )
    assert resp.status_code == 200
    assert resp.json()["queued"] == 1

    events = (await db_session.execute(
        select(AcademicEvent).where(
            AcademicEvent.event_type == "DAILY_ATTENDANCE_DIGEST",
            AcademicEvent.branch_id == seed_data["branch_a"].id,
        )
    )).scalars().all()
    assert len(events) == 1
