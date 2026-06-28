"""Biometric ingestion service — vendor-agnostic.

Takes a list of normalized ``PunchEvent`` and writes them to
``raw_punch_logs``. Handles:

- Student lookup via ``Student.rfid_number`` matching the
  vendor-assigned user id (BioMax / ZKTeco both work this way — they
  expose a numeric ID that we store on the student row when enrolling
  the finger).
- Deduplication: same (student_id, punch_timestamp) within ~5 seconds
  is treated as a re-send and skipped. Biometric devices commonly
  retransmit the same punch on partial network drops.

Aggregation from raw_punch_logs → attendance_records is the existing
attendance module's job; this layer only writes the raw log.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.attendance.models.attendance_models import RawPunchLog
from app.modules.attendance.integrations.biomax.schemas import (
    IngestResult,
    PunchEvent,
)
from app.modules.student.models.student_models import Student


# Two punches for the same student within this window count as
# duplicates. Devices retransmit on network blip; users physically
# can't punch twice in a second.
DUPLICATE_WINDOW = timedelta(seconds=5)


def _normalize_direction(raw: str | None) -> str | None:
    """Map a vendor's direction value to "IN"/"OUT"; None if absent/unknown.

    Vendors use 0/1, in/out, I/O, check-in/check-out, etc. We only persist a
    clean IN/OUT (or None) so the aggregator can trust the column."""
    if raw is None:
        return None
    v = str(raw).strip().lower()
    if v in {"in", "i", "0", "checkin", "check-in", "check_in"}:
        return "IN"
    if v in {"out", "o", "1", "checkout", "check-out", "check_out"}:
        return "OUT"
    return None


async def ingest_punches(
    session: AsyncSession,
    events: list[PunchEvent],
    branch_id: uuid.UUID,
) -> IngestResult:
    if not events:
        return IngestResult(received=0, inserted=0, skipped_no_student=0, skipped_duplicate=0)

    # Resolve vendor_user_id → student in one query.
    vendor_ids = sorted({e.vendor_user_id for e in events})
    student_rows = (await session.execute(
        select(Student.id, Student.rfid_number).where(
            Student.rfid_number.in_(vendor_ids),
            Student.branch_id == branch_id,
            Student.is_deleted == False,
        )
    )).all()
    student_by_vendor_id: dict[str, uuid.UUID] = {
        row[1]: row[0] for row in student_rows if row[1]
    }

    inserted = 0
    skipped_no_student = 0
    skipped_duplicate = 0
    errors: list[str] = []

    for ev in events:
        student_id = student_by_vendor_id.get(ev.vendor_user_id)
        if student_id is None:
            skipped_no_student += 1
            continue

        # Duplicate check — same student, near-identical timestamp.
        lo = ev.punch_timestamp - DUPLICATE_WINDOW
        hi = ev.punch_timestamp + DUPLICATE_WINDOW
        existing = (await session.execute(
            select(RawPunchLog.id).where(
                and_(
                    RawPunchLog.student_id == student_id,
                    RawPunchLog.punch_timestamp >= lo,
                    RawPunchLog.punch_timestamp <= hi,
                    RawPunchLog.is_deleted == False,
                )
            ).limit(1)
        )).scalar_one_or_none()
        if existing is not None:
            skipped_duplicate += 1
            continue

        try:
            session.add(RawPunchLog(
                device_id=ev.device_id,
                sync_batch_id=ev.sync_batch_id,
                synced_at=None,  # filled by the aggregator when it processes
                student_id=student_id,
                punch_timestamp=ev.punch_timestamp,
                direction=_normalize_direction(ev.direction),
                branch_id=branch_id,
            ))
            inserted += 1
        except Exception as exc:  # noqa: BLE001 — surface to caller, don't break batch
            errors.append(f"{ev.vendor_user_id}@{ev.punch_timestamp}: {exc}")

    await session.flush()

    return IngestResult(
        received=len(events),
        inserted=inserted,
        skipped_no_student=skipped_no_student,
        skipped_duplicate=skipped_duplicate,
        errors=errors,
    )
