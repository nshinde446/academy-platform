"""eTimeOffice cloud feeder: row→event mapping, tz conversion, and the
end-to-end sync (mocked HTTP) landing as a DailyAttendance row.

The live HTTP call is mocked — we only own the mapping + ingest path.
"""

import uuid
from datetime import date, datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.attendance.integrations.etimeoffice import service as eto_service
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
        first_name="Eto", last_name=f"User-{rfid}",
        enrollment_number=f"ETO-{rfid}", rfid_number=rfid,
        status="active", is_deleted=False,
    )
    db_session.add(s)
    await db_session.commit()
    return s


# ── pure mapping ─────────────────────────────────────────────────────────────


def test_rows_to_events_in_out_ist_to_utc():
    rows = [{
        "Empcode": "2001", "DateString": "28/05/2026",
        "INTime": "09:55", "OUTTime": "15:10", "Status": "P",
    }]
    events = eto_service.rows_to_events(rows, "Asia/Kolkata")
    assert len(events) == 2
    in_ev, out_ev = events
    assert in_ev.vendor_user_id == "2001"
    assert in_ev.direction == "IN"
    # 09:55 IST -> 04:25 UTC
    assert in_ev.punch_timestamp == datetime(2026, 5, 28, 4, 25, tzinfo=timezone.utc)
    # 15:10 IST -> 09:40 UTC
    assert out_ev.direction == "OUT"
    assert out_ev.punch_timestamp == datetime(2026, 5, 28, 9, 40, tzinfo=timezone.utc)


def test_rows_to_events_skips_empty_and_missing():
    rows = [
        {"Empcode": "", "DateString": "28/05/2026", "INTime": "09:55"},   # no id
        {"Empcode": "2002", "DateString": "28/05/2026", "INTime": "--:--",
         "OUTTime": "00:00"},                                              # no punches
        {"Empcode": "2003", "DateString": "28/05/2026", "INTime": "10:30"},  # in only
    ]
    events = eto_service.rows_to_events(rows, "Asia/Kolkata")
    assert len(events) == 1
    assert events[0].vendor_user_id == "2003"
    assert events[0].direction == "IN"


# ── end-to-end sync (mocked fetch) ──────────────────────────────────────────


@pytest.mark.usefixtures("seed_data")
async def test_sync_range_lands_daily_attendance(db_session, seed_data, monkeypatch):
    await _student(db_session, seed_data, "2001")

    async def fake_fetch(**kwargs):
        return [{
            "Empcode": "2001", "DateString": "28/05/2026",
            "INTime": "09:55", "OUTTime": "15:10", "Status": "P",
        }]

    monkeypatch.setattr(eto_service.eto_client, "fetch_punch_data", fake_fetch)

    summary = await eto_service.sync_range(
        db_session, branch_id=seed_data["branch_a"].id,
        from_date=date(2026, 5, 28), to_date=date(2026, 5, 28),
    )
    assert summary["inserted"] == 2
    assert summary["days_rebuilt"] == 1

    punches = (await db_session.execute(select(RawPunchLog))).scalars().all()
    assert len(punches) == 2

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
        return [{"Empcode": "2001", "DateString": "28/05/2026", "INTime": "09:55"}]

    monkeypatch.setattr(eto_service.eto_client, "fetch_punch_data", fake_fetch)

    first = await eto_service.sync_range(
        db_session, branch_id=seed_data["branch_a"].id,
        from_date=date(2026, 5, 28), to_date=date(2026, 5, 28),
    )
    second = await eto_service.sync_range(
        db_session, branch_id=seed_data["branch_a"].id,
        from_date=date(2026, 5, 28), to_date=date(2026, 5, 28),
    )
    assert first["inserted"] == 1
    assert second["inserted"] == 0          # dedup
    assert second["skipped_duplicate"] == 1
