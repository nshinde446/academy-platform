"""Staff day-attendance aggregation — the staff twin of ``daily_service``.

Turns ``StaffRawPunchLog`` rows into one ``StaffDailyAttendance`` per staff per
LOCAL day. Differs from the student flow in three ways:

- cutoffs are **shift-based** (per-staff ``shift_start`` / ``shift_end``, falling
  back to ``STAFF_SHIFT_*`` settings) rather than the coaching class-start;
- it derives WORK / OT / BREAK minutes to feed the TeamOffice-style reports;
- an empty day resolves to WO (weekly-off), HOLIDAY, or ABSENT.

Idempotent and MANUAL-safe, exactly like the student rebuild.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config.settings import get_settings
from app.modules.attendance.models.attendance_models import (
    StaffDailyAttendance,
    StaffRawPunchLog,
)
from app.modules.attendance.services.daily_service import branch_timezone
from app.modules.attendance.time_utils import day_bounds, local_date_of, local_time_on
from app.modules.lectures.models.lecture_models import Holiday
from app.modules.staff.models.staff_models import Staff


def _parse_hhmm(value: str | None, default: str) -> time:
    raw = (value or default).strip()
    hh, _, mm = raw.partition(":")
    try:
        return time(int(hh), int(mm or 0))
    except (TypeError, ValueError):
        h, m = default.split(":")
        return time(int(h), int(m))


def _weekly_off_set(value: str | None, default: str) -> set[int]:
    raw = value if value is not None else default
    out: set[int] = set()
    for part in (raw or "").split(","):
        part = part.strip()
        if part.isdigit():
            out.add(int(part))
    return out


async def _get_row(
    session: AsyncSession, staff_id: uuid.UUID, day: date
) -> StaffDailyAttendance | None:
    return (await session.execute(
        select(StaffDailyAttendance).where(
            StaffDailyAttendance.staff_id == staff_id,
            StaffDailyAttendance.attendance_date == day,
            StaffDailyAttendance.is_deleted == False,  # noqa: E712
        )
    )).scalar_one_or_none()


async def _punches_for_day(
    session: AsyncSession,
    staff_id: uuid.UUID,
    branch_id: uuid.UUID,
    start: datetime,
    end: datetime,
) -> list[StaffRawPunchLog]:
    return list((await session.execute(
        select(StaffRawPunchLog)
        .where(
            StaffRawPunchLog.staff_id == staff_id,
            StaffRawPunchLog.branch_id == branch_id,
            StaffRawPunchLog.punch_timestamp >= start,
            StaffRawPunchLog.punch_timestamp < end,
            StaffRawPunchLog.is_deleted == False,  # noqa: E712
        )
        .order_by(StaffRawPunchLog.punch_timestamp)
    )).scalars().all())


async def _is_holiday(session: AsyncSession, branch_id: uuid.UUID, day: date) -> bool:
    return (await session.execute(
        select(Holiday.id).where(
            Holiday.branch_id == branch_id,
            Holiday.holiday_date == day,
            Holiday.is_deleted == False,  # noqa: E712
        ).limit(1)
    )).scalar_one_or_none() is not None


def _classify(
    punches: list[StaffRawPunchLog],
    *,
    day: date,
    tz_name: str,
    staff: Staff | None,
    is_holiday: bool,
) -> dict:
    """-> dict of StaffDailyAttendance field values."""
    settings = get_settings()
    weekly_off = _weekly_off_set(
        staff.weekly_off_days if staff else None, settings.STAFF_WEEKLY_OFF_DAYS
    )

    if not punches:
        if is_holiday:
            status = "HOLIDAY"
        elif day.weekday() in weekly_off:
            status = "WO"
        else:
            status = "ABSENT"
        return {
            "first_in": None, "last_out": None, "day_status": status,
            "signoff": "NA", "source": "SYSTEM",
            "work_minutes": 0, "ot_minutes": 0, "break_minutes": 0,
        }

    grace = timedelta(minutes=settings.ATTENDANCE_GRACE_PERIOD_MINUTES)
    shift_start_t = _parse_hhmm(staff.shift_start if staff else None, settings.STAFF_SHIFT_START)
    shift_end_t = _parse_hhmm(staff.shift_end if staff else None, settings.STAFF_SHIFT_END)
    shift_start = local_time_on(day, tz_name, shift_start_t.hour, shift_start_t.minute)
    shift_end = local_time_on(day, tz_name, shift_end_t.hour, shift_end_t.minute)

    first_in = punches[0].punch_timestamp
    if first_in.tzinfo is None:
        first_in = first_in.replace(tzinfo=timezone.utc)

    if len(punches) > 1:
        last_out = punches[-1].punch_timestamp
        if last_out.tzinfo is None:
            last_out = last_out.replace(tzinfo=timezone.utc)
        signoff = "COMPLETE"
        work_minutes = max(0, int((last_out - first_in).total_seconds() // 60))
        ot_minutes = max(0, int((last_out - shift_end).total_seconds() // 60))
    else:
        last_out = None  # punched in, never out
        signoff = "MISSING"
        work_minutes = 0
        ot_minutes = 0

    late = first_in > shift_start + grace
    half_day = signoff == "COMPLETE" and work_minutes < settings.STAFF_HALF_DAY_MINUTES
    if half_day:
        day_status = "HALF_DAY"
    elif late:
        day_status = "LATE"
    else:
        day_status = "PRESENT"

    return {
        "first_in": first_in, "last_out": last_out, "day_status": day_status,
        "signoff": signoff, "source": "BIOMETRIC",
        "work_minutes": work_minutes, "ot_minutes": ot_minutes, "break_minutes": 0,
    }


async def rebuild_daily(
    session: AsyncSession,
    *,
    staff_id: uuid.UUID,
    branch_id: uuid.UUID,
    day: date,
    tz_name: str | None = None,
) -> StaffDailyAttendance:
    """Recompute a staff member's day row from punches. Idempotent; MANUAL-safe."""
    tz_name = tz_name or await branch_timezone(session, branch_id)

    existing = await _get_row(session, staff_id, day)
    if existing is not None and existing.source == "MANUAL":
        return existing  # human edit wins

    staff = (await session.execute(
        select(Staff).where(Staff.id == staff_id)
    )).scalar_one_or_none()

    start, end = day_bounds(day, tz_name)
    punches = await _punches_for_day(session, staff_id, branch_id, start, end)
    is_holiday = await _is_holiday(session, branch_id, day)
    fields = _classify(
        punches, day=day, tz_name=tz_name, staff=staff, is_holiday=is_holiday
    )

    if existing is None:
        existing = StaffDailyAttendance(
            staff_id=staff_id, branch_id=branch_id, attendance_date=day
        )
        session.add(existing)

    for key, value in fields.items():
        setattr(existing, key, value)
    existing.is_deleted = False
    await session.flush()
    return existing


async def rebuild(
    session: AsyncSession,
    *,
    branch_id: uuid.UUID,
    affected_staff: list[tuple[uuid.UUID, datetime]],
    tz_name: str | None = None,
) -> int:
    """Recompute staff day rows for the (staff, local-day) cells a fresh ingest
    touched. Mirrors ``daily_service.rebuild_after_ingest`` for staff (there is
    no lecture-projection Layer 2 for staff). Returns rows rebuilt."""
    if not affected_staff:
        return 0
    tz_name = tz_name or await branch_timezone(session, branch_id)
    cells: set[tuple[uuid.UUID, date]] = {
        (staff_id, local_date_of(ts, tz_name)) for staff_id, ts in affected_staff
    }
    for staff_id, day in cells:
        await rebuild_daily(
            session, staff_id=staff_id, branch_id=branch_id, day=day, tz_name=tz_name
        )
    return len(cells)
