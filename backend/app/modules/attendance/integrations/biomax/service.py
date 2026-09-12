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

import logging

from app.modules.attendance.models.attendance_models import RawPunchLog, StaffRawPunchLog
from app.modules.attendance.integrations.biomax.schemas import (
    AffectedPunch,
    AffectedStaffPunch,
    IngestResult,
    PunchEvent,
)
from app.modules.staff.models.staff_models import Staff
from app.modules.student.models.student_models import Student

logger = logging.getLogger(__name__)


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

    # Staff badge on the SAME fleet. Resolve any vendor id that isn't a student
    # against Staff.emp_code so those punches route to the staff path instead of
    # being dropped as "no student". A vendor id that matches both is treated as
    # a student (and flagged) — the emp_code / rfid namespaces must not overlap.
    unmatched = [vid for vid in vendor_ids if vid not in student_by_vendor_id]
    staff_by_vendor_id: dict[str, uuid.UUID] = {}
    if unmatched:
        staff_rows = (await session.execute(
            select(Staff.id, Staff.emp_code).where(
                Staff.emp_code.in_(unmatched),
                Staff.branch_id == branch_id,
                Staff.is_deleted == False,  # noqa: E712
            )
        )).all()
        staff_by_vendor_id = {row[1]: row[0] for row in staff_rows if row[1]}
    both = set(student_by_vendor_id) & set(staff_by_vendor_id)
    for vid in both:
        logger.warning(
            "device user %s matches both a student and a staff member in branch "
            "%s; treating as student. Fix the overlapping id.", vid, branch_id,
        )
        staff_by_vendor_id.pop(vid, None)

    inserted = 0
    staff_inserted = 0
    skipped_no_student = 0
    skipped_duplicate = 0
    errors: list[str] = []
    affected: list[AffectedPunch] = []
    affected_staff: list[AffectedStaffPunch] = []

    lo_hi = lambda ts: (ts - DUPLICATE_WINDOW, ts + DUPLICATE_WINDOW)  # noqa: E731

    for ev in events:
        student_id = student_by_vendor_id.get(ev.vendor_user_id)
        staff_id = None if student_id is not None else staff_by_vendor_id.get(ev.vendor_user_id)
        if student_id is None and staff_id is None:
            skipped_no_student += 1
            continue

        lo, hi = lo_hi(ev.punch_timestamp)
        if student_id is not None:
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
                    synced_at=None,
                    student_id=student_id,
                    punch_timestamp=ev.punch_timestamp,
                    direction=_normalize_direction(ev.direction),
                    branch_id=branch_id,
                ))
                inserted += 1
                affected.append(AffectedPunch(
                    student_id=student_id, punch_timestamp=ev.punch_timestamp
                ))
            except Exception as exc:  # noqa: BLE001 — surface, don't break batch
                errors.append(f"{ev.vendor_user_id}@{ev.punch_timestamp}: {exc}")
        else:
            existing = (await session.execute(
                select(StaffRawPunchLog.id).where(
                    and_(
                        StaffRawPunchLog.staff_id == staff_id,
                        StaffRawPunchLog.punch_timestamp >= lo,
                        StaffRawPunchLog.punch_timestamp <= hi,
                        StaffRawPunchLog.is_deleted == False,
                    )
                ).limit(1)
            )).scalar_one_or_none()
            if existing is not None:
                skipped_duplicate += 1
                continue
            try:
                session.add(StaffRawPunchLog(
                    device_id=ev.device_id,
                    sync_batch_id=ev.sync_batch_id,
                    synced_at=None,
                    staff_id=staff_id,
                    punch_timestamp=ev.punch_timestamp,
                    direction=_normalize_direction(ev.direction),
                    branch_id=branch_id,
                ))
                staff_inserted += 1
                affected_staff.append(AffectedStaffPunch(
                    staff_id=staff_id, punch_timestamp=ev.punch_timestamp
                ))
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{ev.vendor_user_id}@{ev.punch_timestamp}: {exc}")

    await session.flush()

    return IngestResult(
        received=len(events),
        inserted=inserted,
        staff_inserted=staff_inserted,
        skipped_no_student=skipped_no_student,
        skipped_duplicate=skipped_duplicate,
        errors=errors,
        affected=affected,
        affected_staff=affected_staff,
    )
