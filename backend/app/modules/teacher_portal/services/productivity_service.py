"""Teacher productivity — self-service, factual metrics + buckets for charts.

Reuses the faculty-activity engine (``staff_faculty_service._lecture_stats``) and
the staff attendance ledger to give a teacher their OWN numbers over a selected
range (week / month / quarter / year), split into buckets the frontend charts.

Factual only — lectures taken, on-time %, delayed, late minutes, teaching
minutes, attendance days. No composite "score" or ranking (policy decision).
"""

from __future__ import annotations

import calendar
import uuid
from datetime import date, datetime, timedelta, timezone

from fastapi import HTTPException

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.attendance.models.attendance_models import StaffDailyAttendance
from app.modules.attendance.services import daily_service, staff_faculty_service as faculty
from app.modules.attendance.services import staff_late_fine_service as lf
from app.modules.attendance.time_utils import day_bounds, get_tz
from app.modules.staff.models.staff_models import Staff

_PRESENT = ("PRESENT", "LATE")
VALID_RANGES = ("week", "month", "quarter", "year")


async def _staff(session: AsyncSession, staff_id: uuid.UUID) -> Staff:
    s = (await session.execute(
        select(Staff).where(Staff.id == staff_id, Staff.is_deleted == False)  # noqa: E712
    )).scalar_one_or_none()
    if s is None:
        raise HTTPException(status_code=404, detail="Staff record not found")
    return s


def _months(year: int, months: list[int], today: date) -> list[tuple[str, date, date]]:
    """One bucket per month (label = Jan/Feb…), ends capped at today, months
    that haven't started yet omitted."""
    out = []
    for m in months:
        mstart = date(year, m, 1)
        if mstart > today:
            continue
        mend = date(year, m, calendar.monthrange(year, m)[1])
        out.append((mstart.strftime("%b"), mstart, min(mend, today)))
    return out


def _buckets(range_key: str, today: date) -> tuple[date, date, list[tuple[str, date, date]]]:
    """(period_start, period_end, [(label, bucket_start, bucket_end)]) — bucket
    ends are never in the future (capped at today)."""
    if range_key == "week":
        start = today - timedelta(days=6)
        buckets = [
            ((start + timedelta(days=i)).strftime("%a"),
             start + timedelta(days=i), start + timedelta(days=i))
            for i in range(7)
            if start + timedelta(days=i) <= today
        ]
        return start, today, buckets
    if range_key == "month":
        ndays = calendar.monthrange(today.year, today.month)[1]
        start = date(today.year, today.month, 1)
        end = date(today.year, today.month, ndays)
        buckets = []
        for wk, day0 in enumerate(range(1, ndays + 1, 7), start=1):
            bstart = date(today.year, today.month, day0)
            if bstart > today:
                break
            bend = date(today.year, today.month, min(day0 + 6, ndays))
            buckets.append((f"W{wk}", bstart, min(bend, today)))
        return start, end, buckets
    if range_key == "quarter":
        q = (today.month - 1) // 3
        first = q * 3 + 1
        months = [first, first + 1, first + 2]
        start = date(today.year, first, 1)
        end = date(today.year, months[-1], calendar.monthrange(today.year, months[-1])[1])
        return start, end, _months(today.year, months, today)
    # year
    start, end = date(today.year, 1, 1), date(today.year, 12, 31)
    return start, end, _months(today.year, list(range(1, 13)), today)


async def _attendance(
    session: AsyncSession, s: Staff, start: date, end: date,
) -> tuple[int, int, int, int]:
    """(present_days, absent_days, late_count, late_minutes) over [start, end]."""
    rows = {
        r.attendance_date: r for r in (await session.execute(
            select(StaffDailyAttendance).where(
                StaffDailyAttendance.staff_id == s.id,
                StaffDailyAttendance.branch_id == s.branch_id,
                StaffDailyAttendance.attendance_date >= start,
                StaffDailyAttendance.attendance_date <= end,
                StaffDailyAttendance.is_deleted == False,  # noqa: E712
            )
        )).scalars()
    }
    present = absent = late_count = late_min = 0
    for r in rows.values():
        if r.day_status in _PRESENT:
            present += 1
        elif r.day_status == "ABSENT":
            absent += 1
        first_in = r.first_in
        if first_in is not None:
            if first_in.tzinfo is None:
                first_in = first_in.replace(tzinfo=timezone.utc)
            lm = lf.late_minutes(lf.start_for_day(r.attendance_date, s), first_in)
            if lm > 0:
                late_count += 1
                late_min += lm
    return present, absent, late_count, late_min


async def productivity(
    session: AsyncSession, staff_id: uuid.UUID, range_key: str,
) -> dict:
    if range_key not in VALID_RANGES:
        raise HTTPException(status_code=400, detail=f"range must be one of {VALID_RANGES}")
    s = await _staff(session, staff_id)
    tz_name = await daily_service.branch_timezone(session, s.branch_id)
    today = datetime.now(timezone.utc).astimezone(get_tz(tz_name)).date()
    period_start, period_end, buckets = _buckets(range_key, today)

    teacher_id = s.linked_teacher_id

    out_buckets: list[dict] = []
    tot = {
        "lectures": 0, "on_time": 0, "delayed": 0, "delay_minutes": 0,
        "scheduled_minutes": 0, "delivered_minutes": 0,
        "present_days": 0, "absent_days": 0, "late_count": 0, "late_minutes": 0,
    }
    for label, bstart, bend in buckets:
        lectures = on_time = delayed = delay_min = sched_min = deliv_min = 0
        if teacher_id is not None:
            win_start, _ = day_bounds(bstart, tz_name)
            _, win_end = day_bounds(bend, tz_name)
            st = await faculty._lecture_stats(
                session, s.branch_id, teacher_id, win_start, win_end, tz_name,
            )
            lectures = st["total_lectures"]
            delayed = st["delayed_lectures"]
            on_time = len(st["ontime_detail"])
            delay_min = st["delay_min"]
            sched_min = st["scheduled_min"]
            deliv_min = st["effective_min"]
        present, absent, late_count, late_min = await _attendance(session, s, bstart, bend)

        started = on_time + delayed
        out_buckets.append({
            "label": label,
            "lectures": lectures,
            "on_time": on_time,
            "delayed": delayed,
            "on_time_pct": round(100 * on_time / started, 1) if started else None,
            "late_minutes": late_min,
            "present_days": present,
        })
        tot["lectures"] += lectures
        tot["on_time"] += on_time
        tot["delayed"] += delayed
        tot["delay_minutes"] += delay_min
        tot["scheduled_minutes"] += sched_min
        tot["delivered_minutes"] += deliv_min
        tot["present_days"] += present
        tot["absent_days"] += absent
        tot["late_count"] += late_count
        tot["late_minutes"] += late_min

    started_total = tot["on_time"] + tot["delayed"]
    tot["on_time_pct"] = round(100 * tot["on_time"] / started_total, 1) if started_total else None

    return {
        "range": range_key,
        "start": period_start.isoformat(),
        "end": period_end.isoformat(),
        "is_teacher": teacher_id is not None,
        "totals": tot,
        "buckets": out_buckets,
    }
