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


def _initials(name: str) -> str:
    """Auto-initials from a full name — "Bhagvat Dhesale" -> "BD". Letters only,
    so titles/punctuation ("Mr.", "Anish A.") don't leak in."""
    parts = [re.sub(r"[^A-Za-z]", "", p) for p in name.split()]
    return "".join(p[0].upper() for p in parts if p)


def _hours_words(minutes: int | None) -> str:
    """Minutes -> "H Hours M Mins" (the summary's Total Hours column)."""
    m = int(minutes or 0)
    return f"{m // 60} Hours {m % 60} Mins"


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
    # Lectures-per-subject, to label a teacher with the subject they teach most
    # in this range (the summary report's "Subject" column).
    subj_counts: dict[uuid.UUID, int] = {}
    for l in lectures:
        if l.actual_duration_min is not None:
            effective_min += l.actual_duration_min
        else:
            effective_min += _minutes(l.actual_start, l.actual_end)
        subj_counts[l.subject_id] = subj_counts.get(l.subject_id, 0) + 1
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

    # Resolve every subject id we saw (not just the delayed ones) so the summary
    # can label a teacher and drive the subject-wise pie.
    if subj_counts:
        missing = [sid for sid in subj_counts if not subj_names.get(sid)]
        if missing:
            for sid, name in (await session.execute(
                select(Subject.id, Subject.name).where(Subject.id.in_(missing))
            )).all():
                subj_names[sid] = name

    # Lecture counts keyed by subject NAME (per-course sibling subjects share a
    # name — collapsing by name matches the rest of the app's subject handling).
    subject_counts: dict[str, int] = {}
    for sid, cnt in subj_counts.items():
        name = subj_names.get(sid) or "—"
        subject_counts[name] = subject_counts.get(name, 0) + cnt

    # The teacher's dominant subject over the range (top by lecture count).
    top_subject = ""
    if subj_counts:
        top_id = max(subj_counts, key=lambda k: subj_counts[k])
        top_subject = subj_names.get(top_id) or ""

    return {
        "total_lectures": len(lectures),
        "delayed_lectures": delayed,
        "scheduled_min": scheduled_min,
        "effective_min": effective_min,
        "delay_min": delay_min,
        "delayed_detail": detail,
        "top_subject": top_subject,
        "subject_counts": subject_counts,
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


async def summary_data(
    session: AsyncSession, *, branch_id: uuid.UUID, start: date, end: date,
    teacher_ids: list[uuid.UUID] | None,
) -> dict:
    """Teacher Productivity summary (client document Sections 3 & 5): one row per
    teaching staff — emp_code, auto initials, teacher, subject, present days, total
    lectures, scheduled + delivered lecture minutes — plus subject-wise and
    teacher-wise (by initials) lecture counts for the two pie charts."""
    tz = await daily_service.branch_timezone(session, branch_id)
    staff_rows = await _teaching_staff(session, branch_id, teacher_ids)
    win_start, _ = day_bounds(start, tz)
    _, win_end = day_bounds(end, tz)

    rows: list[dict] = []
    subject_totals: dict[str, int] = {}
    teacher_totals: list[dict] = []
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
        stats = await _lecture_stats(
            session, branch_id, s.linked_teacher_id, win_start, win_end, tz
        )
        teacher = (await session.execute(
            select(Teacher).where(Teacher.id == s.linked_teacher_id)
        )).scalar_one_or_none()
        teacher_name = (
            f"{teacher.first_name} {teacher.last_name}".strip() if teacher
            else f"{s.first_name} {s.last_name}".strip()
        )
        initials = _initials(teacher_name)
        rows.append({
            "emp_code": s.emp_code,
            "initials": initials,
            "teacher_name": teacher_name,
            "subject": stats["top_subject"] or "—",
            "present_days": len(present_days),
            "total_lectures": stats["total_lectures"],
            "scheduled_minutes": stats["scheduled_min"],
            "delivered_minutes": stats["effective_min"],
        })
        for sname, cnt in stats["subject_counts"].items():
            subject_totals[sname] = subject_totals.get(sname, 0) + cnt
        if stats["total_lectures"] > 0:
            teacher_totals.append(
                {"initials": initials, "lectures": stats["total_lectures"]}
            )

    by_subject = [
        {"label": k, "lectures": v}
        for k, v in sorted(subject_totals.items(), key=lambda kv: kv[1], reverse=True)
    ]
    by_teacher = [
        {"label": t["initials"], "lectures": t["lectures"]}
        for t in sorted(teacher_totals, key=lambda r: r["lectures"], reverse=True)
    ]
    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "rows": rows,
        "by_subject": by_subject,
        "by_teacher": by_teacher,
    }


async def summary_report(
    session: AsyncSession, *, branch_id: uuid.UUID, start: date, end: date,
    teacher_ids: list[uuid.UUID] | None, fmt: str,
) -> tuple[str, bytes, str]:
    tz = await daily_service.branch_timezone(session, branch_id)
    data = await summary_data(
        session, branch_id=branch_id, start=start, end=end, teacher_ids=teacher_ids
    )
    brand = get_settings().ACADEMY_BRAND_NAME
    gen = ex.generated_stamp(tz)
    base = f"teacher-productivity-{start}-{end}"
    if fmt == "xlsx":
        return f"{base}.xlsx", _summary_xlsx(brand, start, end, data, gen), XLSX_MIME
    return f"{base}.pdf", await ex.render_html_to_pdf(
        _summary_html(brand, start, end, data, gen), landscape=True), PDF_MIME


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

    # Delayed Lectures detail table (mirrors the PDF) — batch, subject, times,
    # minutes delayed. Placed a row below the summary pairs.
    detail = d.get("delayed_detail") or []
    if detail:
        top = 6 + len(pairs) + 1
        ws.cell(row=top, column=1, value="Delayed Lecture Details").font = Font(bold=True)
        headers = ["Sr", "Batch", "Subject", "Scheduled", "Actual", "Delay"]
        for c, h in enumerate(headers, start=1):
            ws.cell(row=top + 1, column=c, value=h).font = Font(bold=True)
        for i, r in enumerate(detail, start=1):
            row = top + 1 + i
            ws.cell(row=row, column=1, value=i)
            ws.cell(row=row, column=2, value=r["batch"])
            ws.cell(row=row, column=3, value=r["subject"])
            ws.cell(row=row, column=4, value=r["scheduled"])
            ws.cell(row=row, column=5, value=r["actual"])
            ws.cell(row=row, column=6, value=ex.fmt_minutes(r["delay_min"]))

    ws.column_dimensions["A"].width = 26
    ws.column_dimensions["B"].width = 20
    for col in ("C", "D", "E", "F"):
        ws.column_dimensions[col].width = 16
    return ex._xlsx_bytes(wb)


_SUMMARY_HEADERS = [
    "Sr No", "Employee Code", "Initials", "Teacher", "Subject",
    "Present Days", "Total Lectures", "Scheduled Hours", "Delivered Hours",
]

# Pie-slice palette, mirrored on the frontend charts.
_PALETTE = [
    "#2563eb", "#f59e0b", "#10b981", "#ef4444", "#8b5cf6", "#06b6d4",
    "#ec4899", "#84cc16", "#f97316", "#14b8a6", "#a855f7", "#eab308",
]


def _pie_html(title: str, items: list[dict]) -> str:
    """A conic-gradient pie + legend (count and %) — Chromium renders it in PDF."""
    total = sum(it["lectures"] for it in items) or 1
    stops: list[str] = []
    legend: list[str] = []
    acc = 0.0
    for i, it in enumerate(items):
        color = _PALETTE[i % len(_PALETTE)]
        a = acc / total * 360
        acc += it["lectures"]
        b = acc / total * 360
        stops.append(f"{color} {a:.2f}deg {b:.2f}deg")
        pct = it["lectures"] / total * 100
        legend.append(
            f"<li><span class='sw' style='background:{color}'></span>"
            f"{ex._esc(it['label'])} — {it['lectures']} ({pct:.0f}%)</li>"
        )
    grad = ", ".join(stops) or "#e5e7eb 0deg 360deg"
    return (
        f"<div class='pie-block'><h2 class='pie-title'>{ex._esc(title)}</h2>"
        f"<div class='pie-row'>"
        f"<div class='pie' style='background:conic-gradient({grad})'></div>"
        f"<ul class='legend'>{''.join(legend)}</ul></div></div>"
    )


_PIE_CSS = (
    "<style>"
    ".pies{display:flex;gap:28px;flex-wrap:wrap;margin-top:8px}"
    ".pie-block{min-width:280px}"
    ".pie-title{font-size:12px;margin:0 0 6px}"
    ".pie-row{display:flex;gap:14px;align-items:center}"
    ".pie{width:130px;height:130px;border-radius:50%;flex:none}"
    ".legend{list-style:none;margin:0;padding:0;font-size:10.5px}"
    ".legend li{margin:2px 0;white-space:nowrap}"
    ".sw{display:inline-block;width:9px;height:9px;border-radius:2px;margin-right:5px}"
    "</style>"
)


def _summary_html(brand: str, start: date, end: date, data: dict, gen: str) -> str:
    rows = data["rows"]
    ths = "".join(f"<th>{ex._esc(h)}</th>" for h in _SUMMARY_HEADERS)
    body_rows = "".join(
        f"<tr><td class='c'>{i}</td><td class='c'>{ex._esc(r['emp_code'])}</td>"
        f"<td class='c'>{ex._esc(r['initials'])}</td><td>{ex._esc(r['teacher_name'])}</td>"
        f"<td>{ex._esc(r['subject'])}</td><td class='c'>{r['present_days']}</td>"
        f"<td class='c'>{r['total_lectures']}</td>"
        f"<td class='c'>{ex._esc(_hours_words(r['scheduled_minutes']))}</td>"
        f"<td class='c'>{ex._esc(_hours_words(r['delivered_minutes']))}</td></tr>"
        for i, r in enumerate(rows, start=1)
    )
    empty = "" if rows else "<p class='sub'>No teaching staff linked for this period.</p>"
    charts = (
        f"<div class='pies'>{_pie_html('Subject-wise Lectures', data['by_subject'])}"
        f"{_pie_html('Teacher-wise Lectures', data['by_teacher'])}</div>"
        if rows else ""
    )
    body = (
        f"{_PIE_CSS}"
        f"<h1>{ex._esc(brand)} — Teacher Productivity Report</h1>"
        f"<p class='sub'>{ex._period(start, end)}</p>"
        f"<table><tr>{ths}</tr>{body_rows}</table>{empty}{charts}"
    )
    return ex._doc(body, gen)


def _summary_xlsx(brand: str, start: date, end: date, data: dict, gen: str) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Font
    from openpyxl.utils import get_column_letter

    rows = data["rows"]
    wb = Workbook()
    ws = wb.active
    ws.title = "Productivity"
    ws["A1"] = brand
    ws["A1"].font = Font(bold=True, size=14)
    ws["A2"] = "Teacher Productivity Report"
    ws["A3"] = ex._period(start, end)
    ws["A4"] = gen
    head = 5
    for c, h in enumerate(_SUMMARY_HEADERS, start=1):
        ws.cell(row=head, column=c, value=h).font = Font(bold=True)
    for i, r in enumerate(rows, start=1):
        row = head + i
        ws.cell(row=row, column=1, value=i)
        ws.cell(row=row, column=2, value=r["emp_code"])
        ws.cell(row=row, column=3, value=r["initials"])
        ws.cell(row=row, column=4, value=r["teacher_name"])
        ws.cell(row=row, column=5, value=r["subject"])
        ws.cell(row=row, column=6, value=r["present_days"])
        ws.cell(row=row, column=7, value=r["total_lectures"])
        ws.cell(row=row, column=8, value=_hours_words(r["scheduled_minutes"]))
        ws.cell(row=row, column=9, value=_hours_words(r["delivered_minutes"]))
    for c, w in enumerate((7, 14, 9, 24, 12, 12, 14, 16, 16), start=1):
        ws.column_dimensions[get_column_letter(c)].width = w

    # Two pie charts on a Charts sheet (Section 5).
    cs = wb.create_sheet("Charts")
    _xlsx_pie(cs, "Subject-wise Lectures", "Subject", data["by_subject"], 1)
    _xlsx_pie(cs, "Teacher-wise Lectures", "Initials", data["by_teacher"], 5)
    return ex._xlsx_bytes(wb)


def _xlsx_pie(ws, title: str, label_hdr: str, items: list[dict], col: int) -> None:
    from openpyxl.chart import PieChart, Reference
    from openpyxl.styles import Font
    from openpyxl.utils import get_column_letter

    ws.cell(row=1, column=col, value=label_hdr).font = Font(bold=True)
    ws.cell(row=1, column=col + 1, value="Lectures").font = Font(bold=True)
    for i, it in enumerate(items, start=2):
        ws.cell(row=i, column=col, value=it["label"])
        ws.cell(row=i, column=col + 1, value=it["lectures"])
    ws.column_dimensions[get_column_letter(col)].width = 16
    n = len(items)
    if n == 0:
        return
    chart = PieChart()
    chart.title = title
    labels = Reference(ws, min_col=col, min_row=2, max_row=n + 1)
    values = Reference(ws, min_col=col + 1, min_row=1, max_row=n + 1)
    chart.add_data(values, titles_from_data=True)
    chart.set_categories(labels)
    chart.height = 8
    chart.width = 12
    ws.add_chart(chart, f"{get_column_letter(col)}{n + 4}")
