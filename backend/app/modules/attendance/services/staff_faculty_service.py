"""Faculty Activity Report — teacher biometric attendance × lectures delivered.

Joins a teaching staff member's ``StaffDailyAttendance`` (via
``Staff.linked_teacher_id``) with the lectures they actually delivered that day
to produce the report from the client's WhatsApp sample:

* IN / OUT + Attendance Hours (from staff attendance);
* Scheduled vs Effective (actual) Lecture Hours + Time-Lost-to-Delay;
* Total Lectures and Delayed Lectures (+ a delayed-lecture detail table);
* a cumulative per-teacher summary over a range.

"Effective teacher" of a lecture is ``actual_teacher_id`` when set, else
``teacher_id`` — the same rule the teacher-productivity report uses.
"""

from __future__ import annotations

import re
import uuid
from datetime import date, datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config.settings import get_settings
from app.modules.attendance.models.attendance_models import StaffDailyAttendance
from app.modules.attendance.services import daily_service
from app.modules.attendance.services import staff_export_service as ex
from app.modules.attendance.time_utils import day_bounds, get_tz
from app.modules.academic.models.academic_models import Subject
from app.modules.batch.models.batch_models import Batch
from app.modules.lectures.models.lecture_models import Lecture
from app.modules.staff.models.staff_models import Staff
from app.modules.teacher.models.teacher_models import Teacher

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
PDF_MIME = "application/pdf"


def _slug(s: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower() or "report"


def _aware(dt: datetime | None) -> datetime | None:
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _minutes(a: datetime | None, b: datetime | None) -> int:
    a, b = _aware(a), _aware(b)
    if a is None or b is None:
        return 0
    return max(0, int((b - a).total_seconds() // 60))


async def _teacher_lectures_on(
    session: AsyncSession, branch_id: uuid.UUID, teacher_id: uuid.UUID,
    start: datetime, end: datetime,
) -> list[Lecture]:
    """Lectures whose EFFECTIVE teacher is this teacher, scheduled in [start,end)."""
    return list((await session.execute(
        select(Lecture).where(
            Lecture.branch_id == branch_id,
            Lecture.scheduled_start >= start,
            Lecture.scheduled_start < end,
            Lecture.is_deleted == False,  # noqa: E712
            or_(
                Lecture.actual_teacher_id == teacher_id,
                (Lecture.actual_teacher_id.is_(None)) & (Lecture.teacher_id == teacher_id),
            ),
        ).order_by(Lecture.scheduled_start)
    )).scalars().all())


async def _lecture_stats(
    session: AsyncSession, branch_id: uuid.UUID, teacher_id: uuid.UUID,
    start: datetime, end: datetime, tz: str,
) -> dict:
    lectures = await _teacher_lectures_on(session, branch_id, teacher_id, start, end)
    scheduled_min = sum(_minutes(l.scheduled_start, l.scheduled_end) for l in lectures)
    effective_min = 0
    delay_min = 0
    delayed = 0
    detail: list[dict] = []
    subj_names: dict[uuid.UUID, str] = {}
    batch_names: dict[uuid.UUID, str] = {}
    for l in lectures:
        if l.actual_duration_min is not None:
            effective_min += l.actual_duration_min
        else:
            effective_min += _minutes(l.actual_start, l.actual_end)
        d = _minutes(l.scheduled_start, l.actual_start) if l.actual_start else 0
        delay_min += d
        if l.late_flag:
            delayed += 1
            subj_names.setdefault(l.subject_id, "")
            batch_names.setdefault(l.batch_id, "")
            detail.append({
                "batch_id": l.batch_id, "subject_id": l.subject_id,
                "scheduled": _fmt_t(l.scheduled_start, tz),
                "actual": _fmt_t(l.actual_start, tz),
                "delay_min": d,
            })

    # Resolve names for the delayed-lecture detail table.
    if detail:
        for sid, name in (await session.execute(
            select(Subject.id, Subject.name).where(Subject.id.in_(subj_names))
        )).all():
            subj_names[sid] = name
        for bid, name in (await session.execute(
            select(Batch.id, Batch.name).where(Batch.id.in_(batch_names))
        )).all():
            batch_names[bid] = name
        for row in detail:
            row["subject"] = subj_names.get(row.pop("subject_id"), "")
            row["batch"] = batch_names.get(row.pop("batch_id"), "")

    return {
        "total_lectures": len(lectures),
        "delayed_lectures": delayed,
        "scheduled_min": scheduled_min,
        "effective_min": effective_min,
        "delay_min": delay_min,
        "delayed_detail": detail,
    }


def _fmt_t(dt: datetime | None, tz: str) -> str:
    dt = _aware(dt)
    return dt.astimezone(get_tz(tz)).strftime("%H:%M") if dt else "—"


async def _teaching_staff(
    session: AsyncSession, branch_id: uuid.UUID, teacher_ids: list[uuid.UUID] | None,
) -> list[Staff]:
    """Staff rows linked to a teacher (the ones the report can join lectures for)."""
    q = select(Staff).where(
        Staff.branch_id == branch_id,
        Staff.is_deleted == False,  # noqa: E712
        Staff.linked_teacher_id.is_not(None),
    )
    if teacher_ids:
        q = q.where(Staff.linked_teacher_id.in_(teacher_ids))
    return list((await session.execute(q.order_by(Staff.emp_code))).scalars().all())


async def _daily_attendance(
    session: AsyncSession, branch_id: uuid.UUID, staff_id: uuid.UUID, day: date,
) -> StaffDailyAttendance | None:
    return (await session.execute(
        select(StaffDailyAttendance).where(
            StaffDailyAttendance.branch_id == branch_id,
            StaffDailyAttendance.staff_id == staff_id,
            StaffDailyAttendance.attendance_date == day,
            StaffDailyAttendance.is_deleted == False,  # noqa: E712
        )
    )).scalar_one_or_none()


async def daily_report(
    session: AsyncSession, *, branch_id: uuid.UUID, teacher_id: uuid.UUID,
    day: date, fmt: str,
) -> tuple[str, bytes, str]:
    tz = await daily_service.branch_timezone(session, branch_id)
    teacher = (await session.execute(
        select(Teacher).where(Teacher.id == teacher_id, Teacher.branch_id == branch_id)
    )).scalar_one_or_none()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found")
    staff = (await session.execute(
        select(Staff).where(
            Staff.linked_teacher_id == teacher_id, Staff.branch_id == branch_id,
            Staff.is_deleted == False,  # noqa: E712
        )
    )).scalar_one_or_none()

    start, end = day_bounds(day, tz)
    att = await _daily_attendance(session, branch_id, staff.id, day) if staff else None
    stats = await _lecture_stats(session, branch_id, teacher_id, start, end, tz)

    data = {
        "teacher_name": f"{teacher.first_name} {teacher.last_name}".strip(),
        "emp_code": staff.emp_code if staff else "—",
        "day": day.isoformat(),
        "in": _fmt_t(att.first_in, tz) if att else "—",
        "out": _fmt_t(att.last_out, tz) if att else "—",
        "attendance_min": (att.work_minutes if att else 0),
        **stats,
    }
    brand = get_settings().ACADEMY_BRAND_NAME
    gen = ex.generated_stamp(tz)
    base = f"faculty-activity-{_slug(data['teacher_name'])}-{day.isoformat()}"
    if fmt == "xlsx":
        return f"{base}.xlsx", _daily_xlsx(brand, data, gen), XLSX_MIME
    return f"{base}.pdf", await ex.render_html_to_pdf(_daily_html(brand, data, gen)), PDF_MIME


async def summary_report(
    session: AsyncSession, *, branch_id: uuid.UUID, start: date, end: date,
    teacher_ids: list[uuid.UUID] | None, fmt: str,
) -> tuple[str, bytes, str]:
    tz = await daily_service.branch_timezone(session, branch_id)
    staff_rows = await _teaching_staff(session, branch_id, teacher_ids)
    win_start, _ = day_bounds(start, tz)
    _, win_end = day_bounds(end, tz)

    # Present-day count per staff over the range.
    rows: list[dict] = []
    for s in staff_rows:
        present_days = (await session.execute(
            select(StaffDailyAttendance).where(
                StaffDailyAttendance.branch_id == branch_id,
                StaffDailyAttendance.staff_id == s.id,
                StaffDailyAttendance.attendance_date >= start,
                StaffDailyAttendance.attendance_date <= end,
                StaffDailyAttendance.day_status.in_(("PRESENT", "LATE", "HALF_DAY")),
                StaffDailyAttendance.is_deleted == False,  # noqa: E712
            )
        )).scalars().all()
        work_min = sum(d.work_minutes or 0 for d in present_days)
        stats = await _lecture_stats(session, branch_id, s.linked_teacher_id, win_start, win_end, tz)
        teacher = (await session.execute(
            select(Teacher).where(Teacher.id == s.linked_teacher_id)
        )).scalar_one_or_none()
        rows.append({
            "emp_code": s.emp_code,
            "teacher_name": (
                f"{teacher.first_name} {teacher.last_name}".strip() if teacher
                else f"{s.first_name} {s.last_name}".strip()
            ),
            "present_days": len(present_days),
            "work": ex.fmt_minutes(work_min),
            "total_lectures": stats["total_lectures"],
            "delayed_lectures": stats["delayed_lectures"],
        })

    brand = get_settings().ACADEMY_BRAND_NAME
    gen = ex.generated_stamp(tz)
    base = f"faculty-summary-{start}-{end}"
    if fmt == "xlsx":
        return f"{base}.xlsx", _summary_xlsx(brand, start, end, rows, gen), XLSX_MIME
    return f"{base}.pdf", await ex.render_html_to_pdf(
        _summary_html(brand, start, end, rows, gen), landscape=True), PDF_MIME


# ── Builders ────────────────────────────────────────────────────────────────

def _daily_html(brand: str, d: dict, gen: str) -> str:
    detail = "".join(
        f"<tr><td>{ex._esc(r['batch'])}</td><td>{ex._esc(r['subject'])}</td>"
        f"<td class='c'>{ex._esc(r['scheduled'])}</td><td class='c'>{ex._esc(r['actual'])}</td>"
        f"<td class='c'>{ex.fmt_minutes(r['delay_min'])}</td></tr>"
        for r in d["delayed_detail"]
    )
    detail_table = (
        f"<h1 style='font-size:13px'>Delayed Lectures</h1>"
        f"<table><tr><th>Batch</th><th>Subject</th><th>Scheduled</th><th>Actual</th>"
        f"<th>Delay</th></tr>{detail}</table>"
        if d["delayed_detail"] else ""
    )
    body = (
        f"<h1>{ex._esc(brand)} — Daily Faculty Activity Report</h1>"
        f"<p class='sub'>{ex._esc(d['teacher_name'])} · Emp {ex._esc(d['emp_code'])} · {ex._esc(d['day'])}</p>"
        f"<table>"
        f"<tr><th>IN Time</th><td class='c'>{ex._esc(d['in'])}</td>"
        f"<th>OUT Time</th><td class='c'>{ex._esc(d['out'])}</td></tr>"
        f"<tr><th>Attendance Hours</th><td class='c'>{ex.fmt_minutes(d['attendance_min'])}</td>"
        f"<th>Scheduled Lecture Hours</th><td class='c'>{ex.fmt_minutes(d['scheduled_min'])}</td></tr>"
        f"<tr><th>Effective Lecture Hours</th><td class='c'>{ex.fmt_minutes(d['effective_min'])}</td>"
        f"<th>Time Lost to Delay</th><td class='c'>{ex.fmt_minutes(d['delay_min'])}</td></tr>"
        f"<tr><th>Total Lectures</th><td class='c'>{d['total_lectures']}</td>"
        f"<th>Delayed Lectures</th><td class='c'>{d['delayed_lectures']}</td></tr>"
        f"</table>{detail_table}"
    )
    return ex._doc(body, gen)


def _daily_xlsx(brand: str, d: dict, gen: str) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Font

    wb = Workbook()
    ws = wb.active
    ws.title = "Faculty Activity"
    ws["A1"] = brand
    ws["A1"].font = Font(bold=True, size=14)
    ws["A2"] = "Daily Faculty Activity Report"
    ws["A3"] = f"{d['teacher_name']} · Emp {d['emp_code']} · {d['day']}"
    ws["A4"] = gen
    pairs = [
        ("IN Time", d["in"]), ("OUT Time", d["out"]),
        ("Attendance Hours", ex.fmt_minutes(d["attendance_min"])),
        ("Scheduled Lecture Hours", ex.fmt_minutes(d["scheduled_min"])),
        ("Effective Lecture Hours", ex.fmt_minutes(d["effective_min"])),
        ("Time Lost to Delay", ex.fmt_minutes(d["delay_min"])),
        ("Total Lectures", d["total_lectures"]),
        ("Delayed Lectures", d["delayed_lectures"]),
    ]
    for i, (k, v) in enumerate(pairs, start=6):
        ws.cell(row=i, column=1, value=k).font = Font(bold=True)
        ws.cell(row=i, column=2, value=v)
    ws.column_dimensions["A"].width = 26
    ws.column_dimensions["B"].width = 16
    return ex._xlsx_bytes(wb)


_SUMMARY_HEADERS = ["Emp Code", "Teacher", "Present Days", "Total Work", "Total Lectures", "Delayed"]


def _summary_html(brand: str, start: date, end: date, rows: list[dict], gen: str) -> str:
    ths = "".join(f"<th>{ex._esc(h)}</th>" for h in _SUMMARY_HEADERS)
    body_rows = "".join(
        f"<tr><td class='c'>{ex._esc(r['emp_code'])}</td><td>{ex._esc(r['teacher_name'])}</td>"
        f"<td class='c'>{r['present_days']}</td><td class='c'>{ex._esc(r['work'])}</td>"
        f"<td class='c'>{r['total_lectures']}</td><td class='c'>{r['delayed_lectures']}</td></tr>"
        for r in rows
    )
    empty = "" if rows else "<p class='sub'>No teaching staff linked for this period.</p>"
    body = (
        f"<h1>{ex._esc(brand)} — Daily Summary Report (Cumulative, Teachers)</h1>"
        f"<p class='sub'>{ex._period(start, end)}</p>"
        f"<table><tr>{ths}</tr>{body_rows}</table>{empty}"
    )
    return ex._doc(body, gen)


def _summary_xlsx(brand: str, start: date, end: date, rows: list[dict], gen: str) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Font
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = "Cumulative"
    ws["A1"] = brand
    ws["A1"].font = Font(bold=True, size=14)
    ws["A2"] = "Daily Summary Report (Cumulative, Teachers)"
    ws["A3"] = ex._period(start, end)
    ws["A4"] = gen
    head = 5
    for c, h in enumerate(_SUMMARY_HEADERS, start=1):
        ws.cell(row=head, column=c, value=h).font = Font(bold=True)
    for i, r in enumerate(rows, start=head + 1):
        ws.cell(row=i, column=1, value=r["emp_code"])
        ws.cell(row=i, column=2, value=r["teacher_name"])
        ws.cell(row=i, column=3, value=r["present_days"])
        ws.cell(row=i, column=4, value=r["work"])
        ws.cell(row=i, column=5, value=r["total_lectures"])
        ws.cell(row=i, column=6, value=r["delayed_lectures"])
    for c, w in enumerate((10, 24, 14, 12, 14, 10), start=1):
        ws.column_dimensions[get_column_letter(c)].width = w
    return ex._xlsx_bytes(wb)
