"""Attendance report builders — Excel (openpyxl) and PDF (headless Chromium).

Pure builders: they take already-queried data (see daily_service) plus a
timezone for local time display, and return file bytes. The DB work lives in
the route. Three report scopes — individual student, single batch (register
matrix), all batches (summary + sheet per batch) — each in both formats.
"""

from __future__ import annotations

import html
import io
from datetime import date, datetime, timezone
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from app.modules.attendance.time_utils import get_tz

# Cell fills for the register matrix (light, print-friendly).
_FILL = {
    "P": PatternFill("solid", fgColor="D7F0DB"),  # green
    "L": PatternFill("solid", fgColor="FCEFC7"),  # amber
    "A": PatternFill("solid", fgColor="F8D7DA"),  # red
}
_HEAD_FILL = PatternFill("solid", fgColor="EEF1F5")
_BOLD = Font(bold=True)
_CENTER = Alignment(horizontal="center")


def _fmt_time(dt: datetime | None, tz_name: str) -> str:
    if dt is None:
        return "—"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(get_tz(tz_name)).strftime("%H:%M")


def _period(start: date, end: date) -> str:
    return f"{start.isoformat()} to {end.isoformat()}"


def _xlsx_bytes(wb: Workbook) -> bytes:
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ── Excel ──────────────────────────────────────────────────────────────────


def student_xlsx(
    *, brand: str, student_name: str, start: date, end: date,
    summary: dict, timeline: list[Any], tz_name: str,
) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Attendance"

    ws["A1"] = brand
    ws["A1"].font = Font(bold=True, size=14)
    ws["A2"] = f"Attendance report — {student_name}"
    ws["A3"] = _period(start, end)
    ws["A4"] = (
        f"Working days {summary['working_days']} · "
        f"Present {summary['present_days']} · "
        f"Absent {summary['absent_days']} · "
        f"{summary['attendance_pct']}%"
    )

    header_row = 6
    headers = ["Date", "In", "Out", "Status", "Sign-off"]
    for c, h in enumerate(headers, start=1):
        cell = ws.cell(row=header_row, column=c, value=h)
        cell.font = _BOLD
        cell.fill = _HEAD_FILL

    rows = sorted(timeline, key=lambda r: r.attendance_date)
    for i, r in enumerate(rows, start=header_row + 1):
        ws.cell(row=i, column=1, value=r.attendance_date.isoformat())
        ws.cell(row=i, column=2, value=_fmt_time(r.first_in, tz_name))
        ws.cell(row=i, column=3, value=_fmt_time(r.last_out, tz_name))
        ws.cell(row=i, column=4, value=r.day_status)
        ws.cell(row=i, column=5, value=r.signoff)

    for c in range(1, 6):
        ws.column_dimensions[get_column_letter(c)].width = 14
    return _xlsx_bytes(wb)


def _write_matrix_sheet(ws, *, title_lines: list[str], matrix: dict) -> None:
    dates: list[date] = matrix["dates"]
    for i, line in enumerate(title_lines, start=1):
        ws.cell(row=i, column=1, value=line)
    ws.cell(row=1, column=1).font = Font(bold=True, size=13)

    head = len(title_lines) + 2
    ws.cell(row=head, column=1, value="#").font = _BOLD
    ws.cell(row=head, column=2, value="Student").font = _BOLD
    ws.cell(row=head, column=3, value="Enroll").font = _BOLD
    for j, d in enumerate(dates):
        cell = ws.cell(row=head, column=4 + j, value=f"{d.day}/{d.month}")
        cell.font = _BOLD
        cell.alignment = _CENTER
        cell.fill = _HEAD_FILL
    pct_col = 4 + len(dates)
    ws.cell(row=head, column=pct_col, value="Present").font = _BOLD
    ws.cell(row=head, column=pct_col + 1, value="%").font = _BOLD

    for r, srow in enumerate(matrix["students"], start=head + 1):
        ws.cell(row=r, column=1, value=r - head)
        ws.cell(row=r, column=2, value=srow["name"])
        ws.cell(row=r, column=3, value=srow["enrollment_number"] or "")
        for j, code in enumerate(srow["cells"]):
            cell = ws.cell(row=r, column=4 + j, value=code)
            cell.alignment = _CENTER
            if code in _FILL:
                cell.fill = _FILL[code]
        ws.cell(row=r, column=pct_col, value=srow["present"])
        ws.cell(row=r, column=pct_col + 1, value=srow["attendance_pct"])

    totals_row = head + 1 + len(matrix["students"])
    ws.cell(row=totals_row, column=2, value="Present / day").font = _BOLD
    for j, n in enumerate(matrix["day_present"]):
        cell = ws.cell(row=totals_row, column=4 + j, value=n)
        cell.alignment = _CENTER
        cell.font = _BOLD

    ws.column_dimensions["B"].width = 22
    ws.column_dimensions["C"].width = 12
    for j in range(len(dates)):
        ws.column_dimensions[get_column_letter(4 + j)].width = 4.5


def batch_xlsx(
    *, brand: str, batch_name: str, start: date, end: date, matrix: dict,
) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Register"
    _write_matrix_sheet(
        ws,
        title_lines=[
            f"{brand} — {batch_name}",
            f"Attendance register · {_period(start, end)}",
            f"{matrix['student_count']} students · {len(matrix['dates'])} working days · P present / L late / A absent",
        ],
        matrix=matrix,
    )
    return _xlsx_bytes(wb)


def _safe_sheet_title(name: str, used: set[str]) -> str:
    # Excel sheet titles: <=31 chars, no []:*?/\
    clean = "".join(c for c in name if c not in '[]:*?/\\')[:31] or "Batch"
    base, n = clean, 1
    while clean in used:
        suffix = f" {n}"
        clean = base[: 31 - len(suffix)] + suffix
        n += 1
    used.add(clean)
    return clean


def all_batches_xlsx(
    *, brand: str, start: date, end: date,
    summaries: list[dict], matrices: dict[str, dict], batch_names: dict[str, str],
) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Summary"
    ws["A1"] = f"{brand} — all batches"
    ws["A1"].font = Font(bold=True, size=14)
    ws["A2"] = f"Attendance summary · {_period(start, end)}"

    head = 4
    cols = ["Batch", "Code", "Students", "Working days", "Present", "Total", "Avg %"]
    for c, h in enumerate(cols, start=1):
        cell = ws.cell(row=head, column=c, value=h)
        cell.font = _BOLD
        cell.fill = _HEAD_FILL
    for i, s in enumerate(summaries, start=head + 1):
        ws.cell(row=i, column=1, value=s["batch_name"])
        ws.cell(row=i, column=2, value=s["batch_code"])
        ws.cell(row=i, column=3, value=s["student_count"])
        ws.cell(row=i, column=4, value=s["working_days"])
        ws.cell(row=i, column=5, value=s["present"])
        ws.cell(row=i, column=6, value=s["total_slots"])
        ws.cell(row=i, column=7, value=s["avg_pct"])
    ws.column_dimensions["A"].width = 24
    for c in range(2, 8):
        ws.column_dimensions[get_column_letter(c)].width = 13

    used = {"Summary"}
    for batch_id, matrix in matrices.items():
        name = batch_names.get(batch_id, "Batch")
        sheet = wb.create_sheet(_safe_sheet_title(name, used))
        _write_matrix_sheet(
            sheet,
            title_lines=[name, f"Register · {_period(start, end)}"],
            matrix=matrix,
        )
    return _xlsx_bytes(wb)


# ── PDF (HTML -> headless Chromium) ─────────────────────────────────────────

_PDF_CSS = """
@page { margin: 12mm 10mm; }
* { box-sizing: border-box; }
body { font-family: -apple-system, "Segoe UI", Arial, sans-serif; color:#111; font-size: 10pt; margin:0; }
h1 { font-size: 15pt; margin: 0; }
.sub { color:#555; font-size: 9pt; margin: 2pt 0 10pt; }
table { border-collapse: collapse; width: 100%; }
th, td { border: 1px solid #ccc; padding: 3pt 5pt; font-size: 8.5pt; text-align: left; }
th { background: #eef1f5; }
td.c { text-align: center; }
.P { background:#d7f0db; } .L { background:#fcefc7; } .A { background:#f8d7da; }
.tot td { font-weight: 700; background:#f4f6f9; }
"""


def _doc(body: str) -> str:
    return (
        f"<!DOCTYPE html><html><head><meta charset='utf-8'>"
        f"<style>{_PDF_CSS}</style></head><body>{body}</body></html>"
    )


def _esc(v: Any) -> str:
    return html.escape(str(v))


def student_html(
    *, brand: str, student_name: str, start: date, end: date,
    summary: dict, timeline: list[Any], tz_name: str,
) -> str:
    rows = sorted(timeline, key=lambda r: r.attendance_date)
    body = [
        f"<h1>{_esc(brand)}</h1>",
        f"<p class='sub'>Attendance — {_esc(student_name)} · {_period(start, end)}<br>"
        f"Working days {summary['working_days']} · Present {summary['present_days']} · "
        f"Absent {summary['absent_days']} · <b>{summary['attendance_pct']}%</b></p>",
        "<table><tr><th>Date</th><th>In</th><th>Out</th><th>Status</th><th>Sign-off</th></tr>",
    ]
    for r in rows:
        body.append(
            f"<tr><td>{_esc(r.attendance_date.isoformat())}</td>"
            f"<td>{_esc(_fmt_time(r.first_in, tz_name))}</td>"
            f"<td>{_esc(_fmt_time(r.last_out, tz_name))}</td>"
            f"<td>{_esc(r.day_status)}</td><td>{_esc(r.signoff)}</td></tr>"
        )
    body.append("</table>")
    return _doc("".join(body))


def _matrix_table_html(matrix: dict) -> str:
    dates = matrix["dates"]
    head = "".join(f"<th class='c'>{d.day}/{d.month}</th>" for d in dates)
    parts = [
        f"<table><tr><th>#</th><th>Student</th>{head}<th>P</th><th>%</th></tr>"
    ]
    for i, s in enumerate(matrix["students"], start=1):
        cells = "".join(
            f"<td class='c {c}'>{c}</td>" for c in s["cells"]
        )
        parts.append(
            f"<tr><td>{i}</td><td>{_esc(s['name'])}</td>{cells}"
            f"<td class='c'>{s['present']}</td><td class='c'>{s['attendance_pct']}</td></tr>"
        )
    tot = "".join(f"<td class='c'>{n}</td>" for n in matrix["day_present"])
    parts.append(
        f"<tr class='tot'><td></td><td>Present / day</td>{tot}<td></td><td></td></tr>"
    )
    parts.append("</table>")
    return "".join(parts)


def batch_html(
    *, brand: str, batch_name: str, start: date, end: date, matrix: dict,
) -> str:
    body = (
        f"<h1>{_esc(brand)} — {_esc(batch_name)}</h1>"
        f"<p class='sub'>Attendance register · {_period(start, end)} · "
        f"{matrix['student_count']} students · {len(matrix['dates'])} working days "
        f"(P present / L late / A absent)</p>"
        f"{_matrix_table_html(matrix)}"
    )
    return _doc(body)


def all_batches_html(
    *, brand: str, start: date, end: date, summaries: list[dict],
) -> str:
    rows = "".join(
        f"<tr><td>{_esc(s['batch_name'])}</td><td>{_esc(s['batch_code'])}</td>"
        f"<td class='c'>{s['student_count']}</td><td class='c'>{s['working_days']}</td>"
        f"<td class='c'>{s['present']}</td><td class='c'>{s['total_slots']}</td>"
        f"<td class='c'>{s['avg_pct']}</td></tr>"
        for s in summaries
    )
    body = (
        f"<h1>{_esc(brand)} — all batches</h1>"
        f"<p class='sub'>Attendance summary · {_period(start, end)}</p>"
        f"<table><tr><th>Batch</th><th>Code</th><th>Students</th><th>Working days</th>"
        f"<th>Present</th><th>Total</th><th>Avg %</th></tr>{rows}</table>"
    )
    return _doc(body)


async def render_html_to_pdf(doc_html: str, *, landscape: bool = False) -> bytes:
    """Headless Chromium HTML -> PDF (same engine as the paper PDFs)."""
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(args=["--no-sandbox"])
        try:
            page = await browser.new_page()
            await page.set_content(doc_html, wait_until="networkidle")
            return await page.pdf(
                format="A4",
                landscape=landscape,
                print_background=True,
                margin={"top": "12mm", "right": "10mm", "bottom": "12mm", "left": "10mm"},
            )
        finally:
            await browser.close()
