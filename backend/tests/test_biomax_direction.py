"""Biometric ingest now persists punch direction (B2).

PunchEvent.direction used to be parsed then dropped. It must land on
RawPunchLog.direction, normalized to IN/OUT, so the day aggregator can use it.
"""

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.modules.attendance.integrations.biomax import service as biomax
from app.modules.attendance.integrations.biomax.schemas import PunchEvent
from app.modules.attendance.models.attendance_models import RawPunchLog


def _student_vendor_id(seed_data):
    return seed_data["student"].rfid_number


@pytest.mark.usefixtures("seed_data")
async def test_direction_persisted_and_normalized(db_session, seed_data):
    student = seed_data["student"]
    student.rfid_number = "777"
    await db_session.commit()

    events = [
        PunchEvent(vendor_user_id="777", punch_timestamp=datetime(2026, 6, 22, 4, 0, tzinfo=timezone.utc), direction="in"),
        PunchEvent(vendor_user_id="777", punch_timestamp=datetime(2026, 6, 22, 9, 0, tzinfo=timezone.utc), direction="OUT"),
        PunchEvent(vendor_user_id="777", punch_timestamp=datetime(2026, 6, 22, 10, 0, tzinfo=timezone.utc), direction="garbage"),
    ]
    res = await biomax.ingest_punches(db_session, events, seed_data["branch_a"].id)
    assert res.inserted == 3

    rows = (await db_session.execute(
        select(RawPunchLog).where(RawPunchLog.student_id == student.id).order_by(RawPunchLog.punch_timestamp)
    )).scalars().all()
    assert [r.direction for r in rows] == ["IN", "OUT", None]


def test_normalize_direction_variants():
    assert biomax._normalize_direction("0") == "IN"
    assert biomax._normalize_direction("check-out") == "OUT"
    assert biomax._normalize_direction(None) is None
    assert biomax._normalize_direction("weird") is None
