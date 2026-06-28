"""rebuild_daily aggregator (B4) — punches -> one DailyAttendance row.

Scenarios mirror the real Aryan Parte export: an IN+OUT day, the common
IN-only "missed punch-out" day, a late single punch, and an absent day.
Branch tz defaults to Asia/Kolkata; IST = UTC+5:30, so the on-time cutoff
10:10 IST == 04:40 UTC.
"""

import uuid
from datetime import date, datetime, timezone

import pytest

from app.modules.attendance.models.attendance_models import (
    DailyAttendance,
    RawPunchLog,
)
from app.modules.attendance.services import daily_service

DAY = date(2026, 6, 22)


def _utc(h, m):
    return datetime(2026, 6, 22, h, m, tzinfo=timezone.utc)


async def _punch(db_session, seed_data, *, h, m, direction=None):
    p = RawPunchLog(
        device_id="dev1",
        student_id=seed_data["student"].id,
        punch_timestamp=_utc(h, m),
        direction=direction,
        branch_id=seed_data["branch_a"].id,
    )
    db_session.add(p)
    await db_session.flush()
    return p


async def _rebuild(db_session, seed_data):
    return await daily_service.rebuild_daily(
        db_session,
        student_id=seed_data["student"].id,
        branch_id=seed_data["branch_a"].id,
        day=DAY,
    )


@pytest.mark.usefixtures("seed_data")
async def test_in_and_out_present_complete(db_session, seed_data):
    await _punch(db_session, seed_data, h=3, m=59)   # 09:29 IST
    await _punch(db_session, seed_data, h=8, m=54)   # 14:24 IST
    row = await _rebuild(db_session, seed_data)
    assert row.day_status == "PRESENT"
    assert row.signoff == "COMPLETE"
    assert row.first_in == _utc(3, 59)
    assert row.last_out == _utc(8, 54)
    assert row.source == "BIOMETRIC"


@pytest.mark.usefixtures("seed_data")
async def test_single_punch_present_missing_out(db_session, seed_data):
    await _punch(db_session, seed_data, h=2, m=45)   # 08:15 IST, before cutoff
    row = await _rebuild(db_session, seed_data)
    assert row.day_status == "PRESENT"
    assert row.signoff == "MISSING"      # the 24/25 norm
    assert row.last_out is None


@pytest.mark.usefixtures("seed_data")
async def test_late_single_punch(db_session, seed_data):
    await _punch(db_session, seed_data, h=6, m=9)    # 11:39 IST, after 10:10 cutoff
    row = await _rebuild(db_session, seed_data)
    assert row.day_status == "LATE"
    assert row.signoff == "MISSING"


@pytest.mark.usefixtures("seed_data")
async def test_no_punch_absent(db_session, seed_data):
    row = await _rebuild(db_session, seed_data)
    assert row.day_status == "ABSENT"
    assert row.signoff == "NA"
    assert row.source == "SYSTEM"
    assert row.first_in is None and row.last_out is None


@pytest.mark.usefixtures("seed_data")
async def test_idempotent_single_row(db_session, seed_data):
    await _punch(db_session, seed_data, h=3, m=59)
    await _rebuild(db_session, seed_data)
    await _rebuild(db_session, seed_data)
    await db_session.commit()
    rows = (await db_session.execute(
        DailyAttendance.__table__.select().where(
            DailyAttendance.student_id == seed_data["student"].id
        )
    )).all()
    assert len(rows) == 1


@pytest.mark.usefixtures("seed_data")
async def test_manual_override_not_clobbered(db_session, seed_data):
    # A human marked the student PRESENT manually; a later rebuild (no punches)
    # must NOT flip it to ABSENT.
    manual = DailyAttendance(
        student_id=seed_data["student"].id,
        branch_id=seed_data["branch_a"].id,
        attendance_date=DAY,
        first_in=None,
        last_out=None,
        day_status="PRESENT",
        signoff="NA",
        source="MANUAL",
        override_by=seed_data["admin_user"].id,
        override_at=datetime.now(timezone.utc),
    )
    db_session.add(manual)
    await db_session.flush()

    row = await _rebuild(db_session, seed_data)
    assert row.source == "MANUAL"
    assert row.day_status == "PRESENT"
