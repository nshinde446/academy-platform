"""Downloadable staff attendance reports.

One parameterized engine over ``StaffDailyAttendance``:

    (kind, frequency, scope, department_ids, staff_ids, start, end, fmt)

* ``kind='performance'`` renders the TeamOffice-style **grid** (a day column per
  date, IN/OUT/WORK/OT/Status per staff).
* every other kind renders a **list** — a flat, filtered projection. The kind
  selects the row filter (present / absent / late_in / early_out / early_in /
  over_time / half_day / mis_punch / in_out / short_performance).
* the GPS kinds are **not applicable** to the biometric fleet (no GPS source) —
  they return a valid file carrying an explicit note rather than a bogus grid.

``scope`` + ``department_ids`` + ``staff_ids`` narrow the staff set (All/Few
company/department/employee from the reference screen). ``frequency`` is
validated for labelling; the actual window is ``start..end`` the caller passes.
"""

from __future__ import annotations

import re
import uuid
from datetime import date, datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config.settings import get_settings
from app.modules.attendance.models.attendance_models import StaffDailyAttendance
from app.modules.attendance.services import daily_service
from app.modules.attendance.services import staff_export_service as ex
from app.modules.attendance.services.staff_daily_service import _parse_hhmm
from app.modules.attendance.time_utils import get_tz, local_time_on
from app.modules.staff.models.staff_models import Department, Staff

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
PDF_MIME = "application/pdf"

FREQUENCIES = {"daily", "weekly", "monthly"}
PRESENT_STATUSES = {"PRESENT", "LATE", "HALF_DAY"}

# kind -> (human title, is it a GPS placeholder?)
LIST_KINDS = {
    "present": "Daily Present Report",
    "absent": "Daily Absent Report",
    "late_in": "Late IN Report",
    "early_out": "Early OUT Report",
    "early_in": "Early IN Report",
    "over_time": "Over Time Report",
    "half_day": "Half Day Report",
    "mis_punch": "Mis Punch Report",
    "in_out": "In / Out Report",
    "short_performance": "Short Performance Report",
}
GPS_KINDS = {
    "gps_approved": "GPS Approved Report",
    "gps_rejected": "GPS Rejected Report",
    "gps_pending": "GPS Pending Report",
}


def _slug(s: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower() or "report"


def _check(fmt: str, frequency: str) -> None:
    if fmt not in ("xlsx", "pdf"):
        raise HTTPException(status_code=400, detail="format must be xlsx or pdf")
    if frequency not in FREQUENCIES:
        raise HTTPException(status_code=400, detail="frequency must be daily/weekly/monthly")


def _aware(dt: datetime | None) -> datetime | None:
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _dates_in_range(start: date, end: date) -> list[date]:
    days = (end - start).days
    return [start + timedelta(days=i) for i in range(days + 1)]


async def _resolve_staff(
    session: AsyncSession,
    branch_id: uuid.UUID,
    department_ids: list[uuid.UUID] | None,
    staff_ids: list[uuid.UUID] | None,
) -> tuple[list[Staff], dict[uuid.UUID, str]]:
    query = select(Staff).where(
        Staff.branch_id == branch_id, Staff.is_deleted == False  # noqa: E712
    )
    if staff_ids:
        query = query.where(Staff.id.in_(staff_ids))
    elif department_ids:
        query = query.where(Staff.department_id.in_(department_ids))
    staff = list((await session.execute(query.order_by(Staff.emp_code))).scalars().all())
    dept_names = {
        d.id: d.name
        for d in (await session.execute(
            select(Department).where(
                Department.branch_id == branch_id, Department.is_deleted == False  # noqa: E712
            )
        )).scalars().all()
    }
    return staff, dept_names


async def _daily_rows(
    session: AsyncSession, branch_id: uuid.UUID, staff_ids: list[uuid.UUID],
    start: date, end: date,
) -> dict[tuple[uuid.UUID, date], StaffDailyAttendance]:
    if not staff_ids:
        return {}
    rows = (await session.execute(
        select(StaffDailyAttendance).where(
            StaffDailyAttendance.branch_id == branch_id,
            StaffDailyAttendance.staff_id.in_(staff_ids),
            StaffDailyAttendance.attendance_date >= start,
            StaffDailyAttendance.attendance_date <= end,
            StaffDailyAttendance.is_deleted == False,  # noqa: E712
        )
    )).scalars().all()
    return {(r.staff_id, r.attendance_date): r for r in rows}


def _shift_bounds(staff: Staff, day: date, tz: str) -> tuple[datetime, datetime]:
    s = get_settings()
    st = _parse_hhmm(staff.shift_start, s.STAFF_SHIFT_START)
    en = _parse_hhmm(staff.shift_end, s.STAFF_SHIFT_END)
    return (
        local_time_on(day, tz, st.hour, st.minute),
        local_time_on(day, tz, en.hour, en.minute),
    )


def _fmt_t(dt: datetime | None, tz: str) -> str:
    dt = _aware(dt)
    return dt.astimezone(get_tz(tz)).strftime("%H:%M") if dt else "—"


def _match(kind: str, row: StaffDailyAttendance | None, staff: Staff, day: date, tz: str) -> bool:
    if row is None:
        return kind == "absent" and day.weekday() not in _weekly_off(staff)
    st = row.day_status
    if kind == "present":
        return st in PRESENT_STATUSES
    if kind == "absent":
        return st == "ABSENT"
    if kind == "late_in":
        return st == "LATE"
    if kind == "half_day":
        return st == "HALF_DAY"
    if kind == "over_time":
        return (row.ot_minutes or 0) > 0
    if kind == "mis_punch":
        return row.signoff == "MISSING"
    if kind == "in_out":
        return row.first_in is not None
    grace = timedelta(minutes=get_settings().ATTENDANCE_GRACE_PERIOD_MINUTES)
    shift_start, shift_end = _shift_bounds(staff, day, tz)
    if kind == "early_in":
        return row.first_in is not None and _aware(row.first_in) < shift_start
    if kind == "early_out":
        return row.last_out is not None and _aware(row.last_out) < shift_end - grace
    if kind == "short_performance":
        full = max(1, int((shift_end - shift_start).total_seconds() // 60))
        return st in PRESENT_STATUSES and 0 < (row.work_minutes or 0) < full
    return False


def _weekly_off(staff: Staff) -> set[int]:
    raw = staff.weekly_off_days if staff.weekly_off_days is not None else get_settings().STAFF_WEEKLY_OFF_DAYS
    return {int(p) for p in (raw or "").split(",") if p.strip().isdigit()}


async def generate(
    session: AsyncSession, *, branch_id: uuid.UUID, kind: str, frequency: str,
    department_ids: list[uuid.UUID] | None, staff_ids: list[uuid.UUID] | None,
    start: date, end: date, fmt: str,
) -> tuple[str, bytes, str]:
    _check(fmt, frequency)
    tz = await daily_service.branch_timezone(session, branch_id)
    brand = get_settings().ACADEMY_BRAND_NAME
    gen = ex.generated_stamp(tz)
    staff, dept_names = await _resolve_staff(session, branch_id, department_ids, staff_ids)
    rows = await _daily_rows(session, branch_id, [s.id for s in staff], start, end)
    freq_label = frequency.capitalize()
    period = ex._period(start, end)

    # GPS reports — not applicable to the biometric fleet.
    if kind in GPS_KINDS:
        title = f"{freq_label} · {GPS_KINDS[kind]}"
        subtitle = (
            f"{period} · Not applicable — the biometric fleet has no GPS source. "
            f"GPS approval reports come from a mobile-punch system, which this "
            f"deployment does not use."
        )
        base = f"staff-{_slug(kind)}-{start}-{end}"
        if fmt == "xlsx":
            return f"{base}.xlsx", ex.list_xlsx(
                brand=brand, title=title, subtitle=subtitle, rows=[], generated=gen), XLSX_MIME
        return f"{base}.pdf", await ex.render_html_to_pdf(
            ex.list_html(brand=brand, title=title, subtitle=subtitle, rows=[], generated=gen)), PDF_MIME

    dates = _dates_in_range(start, end)

    if kind == "performance":
        blocks = []
        for s in staff:
            cells = []
            present = absent = wo = work_ot = 0
            for d in dates:
                r = rows.get((s.id, d))
                if r is None:
                    st = "WO" if d.weekday() in _weekly_off(s) else "ABSENT"
                    cells.append({"in": "", "out": "", "work": "", "ot": "", "status": st})
                    if st == "WO":
                        wo += 1
                    else:
                        absent += 1
                    continue
                if r.day_status in PRESENT_STATUSES:
                    present += 1
                elif r.day_status == "WO":
                    wo += 1
                elif r.day_status == "ABSENT":
                    absent += 1
                work_ot += (r.work_minutes or 0) + (r.ot_minutes or 0)
                cells.append({
                    "in": _fmt_t(r.first_in, tz), "out": _fmt_t(r.last_out, tz),
                    "work": ex.fmt_minutes(r.work_minutes), "ot": ex.fmt_minutes(r.ot_minutes),
                    "status": r.day_status,
                })
            blocks.append({
                "emp_code": s.emp_code,
                "name": f"{s.first_name} {s.last_name}".strip(),
                "department": dept_names.get(s.department_id, ""),
                "present": present, "absent": absent, "wo": wo,
                "work_ot": ex.fmt_minutes(work_ot), "cells": cells,
            })
        title = f"{freq_label} Performance Report"
        subtitle = f"{period} · {len(staff)} staff"
        base = f"staff-performance-{start}-{end}"
        if fmt == "xlsx":
            return f"{base}.xlsx", ex.grid_xlsx(
                brand=brand, title=title, subtitle=subtitle, dates=dates,
                staff_blocks=blocks, generated=gen), XLSX_MIME
        html = ex.grid_html(
            brand=brand, title=title, subtitle=subtitle, dates=dates,
            staff_blocks=blocks, generated=gen)
        return f"{base}.pdf", await ex.render_html_to_pdf(html, landscape=True), PDF_MIME

    if kind not in LIST_KINDS:
        raise HTTPException(status_code=400, detail=f"unknown report kind '{kind}'")

    out_rows: list[dict] = []
    for s in staff:
        name = f"{s.first_name} {s.last_name}".strip()
        dept = dept_names.get(s.department_id, "")
        for d in dates:
            r = rows.get((s.id, d))
            if not _match(kind, r, s, d, tz):
                continue
            out_rows.append({
                "date": d.isoformat(), "emp_code": s.emp_code, "name": name,
                "department": dept,
                "in": _fmt_t(r.first_in, tz) if r else "—",
                "out": _fmt_t(r.last_out, tz) if r else "—",
                "work": ex.fmt_minutes(r.work_minutes) if r else "0:00",
                "ot": ex.fmt_minutes(r.ot_minutes) if r else "0:00",
                "status": r.day_status if r else "ABSENT",
            })

    title = f"{freq_label} · {LIST_KINDS[kind]}"
    subtitle = f"{period} · {len(out_rows)} rows"
    base = f"staff-{_slug(kind)}-{start}-{end}"
    if fmt == "xlsx":
        return f"{base}.xlsx", ex.list_xlsx(
            brand=brand, title=title, subtitle=subtitle, rows=out_rows, generated=gen), XLSX_MIME
    html = ex.list_html(
        brand=brand, title=title, subtitle=subtitle, rows=out_rows, generated=gen)
    return f"{base}.pdf", await ex.render_html_to_pdf(html, landscape=True), PDF_MIME
