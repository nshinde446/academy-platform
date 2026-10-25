"""Read-only data for the teacher portal (My Day + month summary).

The teacher sees only their own data. The staff id is resolved by the caller
from the login session; this service never takes a teacher/staff id from the
request. All numbers are **read**, never recomputed: IN/OUT/status come from
``StaffDailyAttendance``; late minutes + fine come from the existing late-fine
logic (``staff_late_fine_service``); lectures come from the same query the
Faculty Activity Report uses. Fine is hidden until the day is closed when
``fine_visibility = after_day_close``.
"""

from __future__ import annotations

import calendar
import uuid
from datetime import date, datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.attendance.models.attendance_models import StaffDailyAttendance
from app.modules.attendance.services import daily_service
from app.modules.attendance.services import staff_faculty_service as fac
from app.modules.attendance.services import staff_late_fine_service as lf
from app.modules.attendance.time_utils import get_tz
from app.modules.academic.models.academic_models import Subject
from app.modules.batch.models.batch_models import Batch
from app.modules.staff.models.staff_models import Department, Staff
from app.modules.teacher_portal.services import config_service

PRESENT_STATUSES = {"PRESENT", "LATE", "HALF_DAY"}


async def _staff(session: AsyncSession, staff_id: uuid.UUID) -> Staff:
    s = (await session.execute(
        select(Staff).where(Staff.id == staff_id, Staff.is_deleted == False)  # noqa: E712
    )).scalar_one_or_none()
    if s is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Staff not found")
    return s


def _in_local(row: StaffDailyAttendance | None, tz) -> datetime | None:
    if row is None or row.first_in is None:
        return None
    in_utc = row.first_in
    if in_utc.tzinfo is None:  # SQLite returns naive; stored as UTC
        in_utc = in_utc.replace(tzinfo=timezone.utc)
    return in_utc.astimezone(tz)


def _fmt(dt: datetime | None) -> str | None:
    return dt.strftime("%H:%M") if dt else None


def _fine_visible(cfg: dict, day: date, now_local: datetime) -> bool:
    """Fine is visible in realtime mode, or once the day is closed: any past day,
    or today after the configured day-close wall-clock time."""
    if cfg.get("fine_visibility") == "realtime":
        return True
    if day < now_local.date():
        return True
    if day > now_local.date():
        return False
    hm = lf._parse_hhmm(str(cfg.get("day_close_time") or "23:30"))
    close_minute = (hm[0] * 60 + hm[1]) if hm else 23 * 60 + 30
    return (now_local.hour * 60 + now_local.minute) >= close_minute


async def profile(session: AsyncSession, staff_id: uuid.UUID) -> dict:
    s = await _staff(session, staff_id)
    dept = (await session.execute(
        select(Department).where(Department.id == s.department_id)
    )).scalar_one_or_none()
    return {
        "name": f"{s.first_name} {s.last_name}".strip(),
        "employee_code": s.emp_code,
        "department": dept.name if dept else None,
        "title": s.title,
        "designation": s.designation,
        "shift_start": s.shift_start,
        "shift_end": s.shift_end,
        "phone": s.phone,
        "email": s.email,
    }


async def update_contact(
    session: AsyncSession,
    staff_id: uuid.UUID,
    *,
    actor_user_id: uuid.UUID,
    phone: str | None = None,
    email: str | None = None,
    phone_set: bool = False,
    email_set: bool = False,
    ip: str | None = None,
) -> dict:
    """Update ONLY the teacher's own contact details (phone / email), identified
    by the session's staff id. ``*_set`` says whether the client sent the field,
    so a one-field patch doesn't blank the other. Writes a business audit row."""
    from app.modules.audit.services import audit_service

    s = await _staff(session, staff_id)
    changed: dict[str, object] = {}
    if phone_set:
        s.phone = phone
        changed["phone"] = phone
    if email_set:
        s.email = email
        changed["email"] = email
    if changed:
        await session.flush()
        await audit_service.log_action(
            session, user_id=actor_user_id, action="UPDATE", table_name="staff",
            record_id=s.id, new_values={"self_contact_update": changed},
            ip_address=ip, branch_id=s.branch_id,
        )
    return await profile(session, staff_id)


async def _lectures_for_day(
    session: AsyncSession, branch_id: uuid.UUID, teacher_id: uuid.UUID,
    day: date, tz_name: str,
) -> list[dict]:
    """The teacher's lectures that day (same source as the Faculty Activity
    Report), each with scheduled/actual times + a status chip."""
    from datetime import timedelta

    from app.modules.attendance.time_utils import local_time_on

    # [00:00 local, next-00:00 local) expressed in UTC.
    start_utc = local_time_on(day, tz_name, 0, 0)
    end_utc = start_utc + timedelta(days=1)
    lectures = await fac._teacher_lectures_on(
        session, branch_id, teacher_id, start_utc, end_utc
    )
    if not lectures:
        return []
    subj_ids = {l.subject_id for l in lectures}
    batch_ids = {l.batch_id for l in lectures}
    subj = {
        r.id: r.name for r in (await session.execute(
            select(Subject).where(Subject.id.in_(subj_ids))
        )).scalars()
    }
    batch = {
        r.id: r.name for r in (await session.execute(
            select(Batch).where(Batch.id.in_(batch_ids))
        )).scalars()
    }

    def _t(dt: datetime | None) -> str | None:
        return fac._fmt_t(dt, tz_name) if dt else None

    rows = []
    for l in lectures:
        if l.actual_start is None:
            chip = "scheduled"
        elif fac._late_strict(l.scheduled_start, l.actual_start):
            chip = "delayed"
        else:
            chip = "on_time"
        rows.append({
            "batch": batch.get(l.batch_id, "—"),
            "subject": subj.get(l.subject_id, "—"),
            "scheduled_start": _t(l.scheduled_start),
            "scheduled_end": _t(l.scheduled_end),
            "actual_start": _t(l.actual_start),
            "actual_end": _t(l.actual_end),
            "status": chip,
        })
    return rows


async def day(session: AsyncSession, staff_id: uuid.UUID, day_: date) -> dict:
    """My Day: attendance IN/OUT/status, first-lecture start, late minutes, fine
    (hidden until day close), and the lecture list — all read, never recomputed."""
    s = await _staff(session, staff_id)
    tz_name = await daily_service.branch_timezone(session, s.branch_id)
    tz = get_tz(tz_name)
    cfg = await config_service.get_config(session)
    now_local = datetime.now(timezone.utc).astimezone(tz)

    row = (await session.execute(
        select(StaffDailyAttendance).where(
            StaffDailyAttendance.staff_id == staff_id,
            StaffDailyAttendance.branch_id == s.branch_id,
            StaffDailyAttendance.attendance_date == day_,
            StaffDailyAttendance.is_deleted == False,  # noqa: E712
        )
    )).scalar_one_or_none()

    in_local = _in_local(row, tz)
    out_local = None
    if row is not None and row.last_out is not None:
        out_utc = row.last_out
        if out_utc.tzinfo is None:
            out_utc = out_utc.replace(tzinfo=timezone.utc)
        out_local = out_utc.astimezone(tz)

    start_hhmm = lf.start_for_day(day_, s)
    # Late minutes only when there is an IN punch (spec: else "Not available").
    late_minutes = lf.late_minutes(start_hhmm, in_local) if in_local else None

    fine_amount = None
    fine_visible = _fine_visible(cfg, day_, now_local)
    if late_minutes is not None:
        slabs = await lf._load_slabs(session)
        fine_amount, _ = lf.fine_for(late_minutes, slabs)

    teacher_id = s.linked_teacher_id
    lectures = (
        await _lectures_for_day(session, s.branch_id, teacher_id, day_, tz_name)
        if teacher_id else []
    )

    return {
        "date": day_.isoformat(),
        "attendance": {
            "in": _fmt(in_local),
            "out": _fmt(out_local) if out_local else ("Missing" if row else None),
            "status": row.day_status if row else "ABSENT",
        },
        "first_lecture_start": start_hhmm,
        "late_minutes": late_minutes,
        "fine": {
            "amount": (fine_amount if fine_visible else None),
            "visible": fine_visible,
        },
        "lectures": lectures,
    }


async def month_summary(
    session: AsyncSession, staff_id: uuid.UUID, year: int, month: int,
) -> dict:
    """Month-to-date totals: present / half / absent days, late count, total late
    minutes, total fine (finalized days only under after_day_close)."""
    s = await _staff(session, staff_id)
    tz_name = await daily_service.branch_timezone(session, s.branch_id)
    tz = get_tz(tz_name)
    cfg = await config_service.get_config(session)
    now_local = datetime.now(timezone.utc).astimezone(tz)
    ndays = calendar.monthrange(year, month)[1]
    first, last = date(year, month, 1), date(year, month, ndays)

    rows = {
        r.attendance_date: r for r in (await session.execute(
            select(StaffDailyAttendance).where(
                StaffDailyAttendance.staff_id == staff_id,
                StaffDailyAttendance.branch_id == s.branch_id,
                StaffDailyAttendance.attendance_date >= first,
                StaffDailyAttendance.attendance_date <= last,
                StaffDailyAttendance.is_deleted == False,  # noqa: E712
            )
        )).scalars()
    }
    slabs = await lf._load_slabs(session)

    present = half = absent = late_count = total_late = 0
    total_fine = 0.0
    for i in range(ndays):
        d = date(year, month, i + 1)
        if d > now_local.date():
            continue
        r = rows.get(d)
        st = r.day_status if r else "ABSENT"
        if st == "HALF_DAY":
            half += 1
        elif st in PRESENT_STATUSES:
            present += 1
        elif st == "ABSENT":
            absent += 1
        in_local = _in_local(r, tz)
        if in_local:
            lm = lf.late_minutes(lf.start_for_day(d, s), in_local)
            if lm > 0:
                late_count += 1
                total_late += lm
                if _fine_visible(cfg, d, now_local):
                    fine, _ = lf.fine_for(lm, slabs)
                    total_fine += fine

    return {
        "year": year, "month": month,
        "present_days": present, "half_days": half, "absent_days": absent,
        "late_count": late_count, "total_late_minutes": total_late,
        "total_fine": round(total_fine, 2),
    }
