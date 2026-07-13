"""SmartOffice cloud feeder: row→event mapping, tz conversion, serial filter,
the error envelope, and the end-to-end sync (mocked HTTP) landing as a
DailyAttendance row.

The live HTTP call is mocked — we only own the mapping + ingest path.
"""

import uuid
from datetime import date, datetime, timezone

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.attendance.integrations.smartoffice import client as so_client
from app.modules.attendance.integrations.smartoffice import service as so_service
from app.modules.attendance.models.attendance_models import (
    DailyAttendance,
    RawPunchLog,
)
from app.modules.student.models.student_models import Student


async def _student(db_session: AsyncSession, seed_data, rfid: str) -> Student:
    s = Student(
        id=uuid.uuid4(),
        branch_id=seed_data["branch_a"].id,
        academic_year_id=seed_data["academic_year"].id,
        first_name="SO", last_name=f"User-{rfid}",
        enrollment_number=f"SO-{rfid}", rfid_number=rfid,
        status="active", is_deleted=False,
    )
    db_session.add(s)
    await db_session.commit()
    return s


def _row(code="2001", log="2026-05-28 09:55:00", serial="SNA", direction="in"):
    return {
        "EmployeeCode": code, "LogDate": log,
        "SerialNumber": serial, "PunchDirection": direction,
    }


# ── pure mapping ─────────────────────────────────────────────────────────────


def test_rows_to_events_ist_to_utc_and_fields():
    events = so_service.rows_to_events([_row()], "Asia/Kolkata")
    assert len(events) == 1
    ev = events[0]
    assert ev.vendor_user_id == "2001"
    assert ev.device_id == "SNA"           # serial lands as device id
    assert ev.direction == "in"            # raw; ingest normalizes to IN
    # 09:55 IST -> 04:25 UTC
    assert ev.punch_timestamp == datetime(2026, 5, 28, 4, 25, tzinfo=timezone.utc)


def test_rows_to_events_skips_no_code_and_bad_date():
    rows = [
        _row(code=""),                       # no employee code
        _row(code="2002", log="not-a-date"), # unparseable LogDate
        _row(code="2003"),                   # good
    ]
    events = so_service.rows_to_events(rows, "Asia/Kolkata")
    assert [e.vendor_user_id for e in events] == ["2003"]


def test_rows_to_events_serial_allowlist_filters_foreign_devices():
    rows = [_row(code="2001", serial="SNA"), _row(code="2002", serial="OTHER")]
    events = so_service.rows_to_events(rows, "Asia/Kolkata", allowed_serials={"SNA"})
    assert [e.vendor_user_id for e in events] == ["2001"]


def test_parse_log_datetime_tolerates_missing_seconds():
    assert so_client.parse_log_datetime("2026-05-28 09:55") == datetime(2026, 5, 28, 9, 55)
    assert so_client.parse_log_datetime("") is None


# ── client error envelope ────────────────────────────────────────────────────


async def test_fetch_device_logs_raises_on_error_envelope():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": False, "message": "Invalid API Key."})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(so_client.SmartOfficeError, match="Invalid API Key"):
            await so_client.fetch_device_logs(
                base_url="http://x", api_key="bad",
                from_dt=datetime(2026, 5, 28), to_dt=datetime(2026, 5, 28),
                client=client,
            )


async def test_fetch_device_logs_returns_array():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[_row()])

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        rows = await so_client.fetch_device_logs(
            base_url="http://x", api_key="good",
            from_dt=datetime(2026, 5, 28), to_dt=datetime(2026, 5, 28),
            client=client,
        )
    assert rows and rows[0]["EmployeeCode"] == "2001"


# ── end-to-end sync (mocked fetch) ──────────────────────────────────────────


@pytest.mark.usefixtures("seed_data")
async def test_sync_range_lands_daily_attendance(db_session, seed_data, monkeypatch):
    await _student(db_session, seed_data, "2001")

    async def fake_fetch(**kwargs):
        return [
            _row(code="2001", log="2026-05-28 09:55:00", direction="in"),
            _row(code="2001", log="2026-05-28 15:10:00", direction="out"),
        ]

    monkeypatch.setattr(so_service.so_client, "fetch_device_logs", fake_fetch)

    summary = await so_service.sync_range(
        db_session, branch_id=seed_data["branch_a"].id,
        from_date=date(2026, 5, 28), to_date=date(2026, 5, 28),
    )
    assert summary["inserted"] == 2
    assert summary["days_rebuilt"] == 1

    punches = (await db_session.execute(select(RawPunchLog))).scalars().all()
    assert len(punches) == 2
    # Direction is normalized on ingest ("in" -> "IN").
    assert {p.direction for p in punches} == {"IN", "OUT"}

    day = (await db_session.execute(
        select(DailyAttendance).where(
            DailyAttendance.attendance_date == date(2026, 5, 28)
        )
    )).scalar_one()
    assert day.day_status == "PRESENT"   # 09:55 IST <= 10:10 cutoff
    assert day.signoff == "COMPLETE"     # in + out


@pytest.mark.usefixtures("seed_data")
async def test_sync_range_idempotent(db_session, seed_data, monkeypatch):
    await _student(db_session, seed_data, "2001")

    async def fake_fetch(**kwargs):
        return [_row(code="2001", log="2026-05-28 09:55:00")]

    monkeypatch.setattr(so_service.so_client, "fetch_device_logs", fake_fetch)

    first = await so_service.sync_range(
        db_session, branch_id=seed_data["branch_a"].id,
        from_date=date(2026, 5, 28), to_date=date(2026, 5, 28),
    )
    second = await so_service.sync_range(
        db_session, branch_id=seed_data["branch_a"].id,
        from_date=date(2026, 5, 28), to_date=date(2026, 5, 28),
    )
    assert first["inserted"] == 1
    assert second["inserted"] == 0          # dedup
    assert second["skipped_duplicate"] == 1
