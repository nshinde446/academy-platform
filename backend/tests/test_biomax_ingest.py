"""Tests for the vendor-agnostic biometric ingestion service.

These tests bypass the webhook payload parser (BioMax-specific, stubbed
until vendor docs land) and exercise the parts that ship today:
- Student lookup by rfid_number
- Dedup window
- Insert into raw_punch_logs
"""

import uuid
from datetime import datetime, timezone, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.attendance.integrations.biomax.schemas import PunchEvent
from app.modules.attendance.integrations.biomax.service import (
    DUPLICATE_WINDOW,
    ingest_punches,
)
from app.modules.attendance.models.attendance_models import RawPunchLog
from app.modules.student.models.student_models import Student


async def _make_student_with_rfid(
    db_session: AsyncSession,
    seed_data,
    rfid: str,
) -> Student:
    s = Student(
        id=uuid.uuid4(),
        branch_id=seed_data["branch_a"].id,
        academic_year_id=seed_data["academic_year"].id,
        first_name="Bio",
        last_name=f"Test-{rfid}",
        enrollment_number=f"STU-{rfid}",
        rfid_number=rfid,
        status="active",
        is_deleted=False,
    )
    db_session.add(s)
    await db_session.commit()
    return s


class TestBiometricIngest:
    @pytest.mark.usefixtures("seed_data")
    async def test_inserts_punches_for_known_students(self, db_session, seed_data):
        s1 = await _make_student_with_rfid(db_session, seed_data, "1001")
        s2 = await _make_student_with_rfid(db_session, seed_data, "1002")

        events = [
            PunchEvent(
                vendor_user_id="1001",
                punch_timestamp=datetime(2026, 5, 28, 9, 0, tzinfo=timezone.utc),
                device_id="dev-A",
            ),
            PunchEvent(
                vendor_user_id="1002",
                punch_timestamp=datetime(2026, 5, 28, 9, 0, tzinfo=timezone.utc),
                device_id="dev-A",
            ),
        ]
        result = await ingest_punches(db_session, events, seed_data["branch_a"].id)
        assert result.inserted == 2
        assert result.skipped_no_student == 0

        rows = (await db_session.execute(select(RawPunchLog))).scalars().all()
        assert len(rows) == 2
        assert {r.student_id for r in rows} == {s1.id, s2.id}

    @pytest.mark.usefixtures("seed_data")
    async def test_skips_unknown_vendor_id(self, db_session, seed_data):
        await _make_student_with_rfid(db_session, seed_data, "1001")
        events = [
            PunchEvent(
                vendor_user_id="9999",  # not in DB
                punch_timestamp=datetime(2026, 5, 28, 9, 0, tzinfo=timezone.utc),
            ),
        ]
        result = await ingest_punches(db_session, events, seed_data["branch_a"].id)
        assert result.inserted == 0
        assert result.skipped_no_student == 1

    @pytest.mark.usefixtures("seed_data")
    async def test_dedup_window(self, db_session, seed_data):
        await _make_student_with_rfid(db_session, seed_data, "1001")
        t0 = datetime(2026, 5, 28, 9, 0, tzinfo=timezone.utc)

        first = await ingest_punches(
            db_session,
            [PunchEvent(vendor_user_id="1001", punch_timestamp=t0)],
            seed_data["branch_a"].id,
        )
        assert first.inserted == 1

        # Re-send within the dedup window — should be skipped.
        within = await ingest_punches(
            db_session,
            [PunchEvent(
                vendor_user_id="1001",
                punch_timestamp=t0 + timedelta(seconds=2),
            )],
            seed_data["branch_a"].id,
        )
        assert within.inserted == 0
        assert within.skipped_duplicate == 1

        # Outside the window — accepted as a fresh punch.
        outside = await ingest_punches(
            db_session,
            [PunchEvent(
                vendor_user_id="1001",
                punch_timestamp=t0 + DUPLICATE_WINDOW + timedelta(seconds=1),
            )],
            seed_data["branch_a"].id,
        )
        assert outside.inserted == 1
