"""BioMax iclock/ADMS push: ATTLOG parsing, direction mapping, serial gating,
handshake, and the end-to-end ingest landing a DailyAttendance row.
"""

import uuid
from datetime import date, datetime, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.attendance.integrations.biomax import iclock
from app.modules.attendance.integrations.biomax.service import ingest_punches
from app.modules.attendance.models.attendance_models import DailyAttendance
from app.modules.attendance.services import daily_service
from app.modules.student.models.student_models import Student


async def _student(db_session: AsyncSession, seed_data, rfid: str) -> Student:
    s = Student(
        id=uuid.uuid4(),
        branch_id=seed_data["branch_a"].id,
        academic_year_id=seed_data["academic_year"].id,
        first_name="Bm", last_name=f"User-{rfid}",
        enrollment_number=f"BMX-{rfid}", rfid_number=rfid,
        status="active", is_deleted=False,
    )
    db_session.add(s)
    await db_session.commit()
    return s


# ── pure parsing ─────────────────────────────────────────────────────────────


def test_parse_attlog_tab_separated_ist_to_utc():
    body = (
        "3001\t2026-05-28 09:55:00\t0\t1\t0\n"
        "3001\t2026-05-28 15:10:00\t1\t1\t0\n"
    )
    events = iclock.parse_attlog(body, "Asia/Kolkata")
    assert len(events) == 2
    assert events[0].vendor_user_id == "3001"
    assert events[0].direction == "IN"   # status 0
    assert events[0].punch_timestamp == datetime(2026, 5, 28, 4, 25, tzinfo=timezone.utc)
    assert events[1].direction == "OUT"  # status 1


def test_parse_attlog_skips_malformed_lines():
    body = (
        "\n"                                  # blank
        "3002\n"                              # no timestamp
        "3003\tnot-a-date\t0\n"               # bad timestamp
        "3004\t2026-05-28 10:30:00\t0\n"      # good
    )
    events = iclock.parse_attlog(body, "Asia/Kolkata")
    assert [e.vendor_user_id for e in events] == ["3004"]


def test_attlog_direction_mapping():
    assert iclock._attlog_direction("0") == "IN"
    assert iclock._attlog_direction("4") == "IN"
    assert iclock._attlog_direction("1") == "OUT"
    assert iclock._attlog_direction("5") == "OUT"
    assert iclock._attlog_direction("2") is None
    assert iclock._attlog_direction("") is None


# ── serial allowlist gating ─────────────────────────────────────────────────


def test_require_known_device_rejects_unknown(monkeypatch):
    monkeypatch.setattr(
        iclock, "get_settings",
        lambda: type("S", (), {"BIOMAX_DEVICE_SERIALS": "ABC123,DEF456"})(),
    )
    assert iclock._require_known_device("ABC123") == "ABC123"
    with pytest.raises(HTTPException) as exc:
        iclock._require_known_device("NOPE")
    assert exc.value.status_code == 401
    with pytest.raises(HTTPException):
        iclock._require_known_device(None)


def test_require_known_device_empty_allowlist_rejects_all(monkeypatch):
    monkeypatch.setattr(
        iclock, "get_settings",
        lambda: type("S", (), {"BIOMAX_DEVICE_SERIALS": ""})(),
    )
    with pytest.raises(HTTPException):
        iclock._require_known_device("ABC123")


async def test_handshake_contains_serial_and_realtime(monkeypatch):
    monkeypatch.setattr(
        iclock, "get_settings",
        lambda: type("S", (), {"BIOMAX_DEVICE_SERIALS": "SN-1"})(),
    )
    resp = await iclock.iclock_handshake(sn="SN-1")
    text = resp.body.decode()
    assert "GET OPTION FROM: SN-1" in text
    assert "Realtime=1" in text


# ── end-to-end ingest ───────────────────────────────────────────────────────


@pytest.mark.usefixtures("seed_data")
async def test_attlog_ingest_lands_daily_attendance(db_session, seed_data):
    await _student(db_session, seed_data, "3001")
    body = (
        "3001\t2026-05-28 09:55:00\t0\n"
        "3001\t2026-05-28 15:10:00\t1\n"
    )
    tz_name = await daily_service.branch_timezone(db_session, seed_data["branch_a"].id)
    events = iclock.parse_attlog(body, tz_name)
    result = await ingest_punches(db_session, events, seed_data["branch_a"].id)
    await daily_service.rebuild_after_ingest(
        db_session, branch_id=seed_data["branch_a"].id,
        affected=[(a.student_id, a.punch_timestamp) for a in result.affected],
        tz_name=tz_name,
    )
    await db_session.commit()

    assert result.inserted == 2
    day = (await db_session.execute(
        select(DailyAttendance).where(
            DailyAttendance.attendance_date == date(2026, 5, 28)
        )
    )).scalar_one()
    assert day.day_status == "PRESENT"
    assert day.signoff == "COMPLETE"
