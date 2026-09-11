"""Staff attendance report builders — Excel (openpyxl) + PDF (headless Chromium).

Pure builders: take already-queried rows and return file bytes. Two shapes cover
the whole requirement grid:

* **grid** — the TeamOffice-style monthly/weekly performance block: one staff
  section with a day column per date carrying IN/OUT/WORK/OT and a Status line.
* **list** — a flat, filtered projection (Date · EmpCode · Name · Dept · In ·
  Out · Work · OT · Status) that serves every typed report (Present, Absent,
  Late-IN, Early-OUT, OT, Half-Day, Mis-Punch, In/Out, …); the caller pre-filters
  the rows and passes the title.

Reuses the student export scaffolding (PDF render, generation stamp, crest, CSS).
"""

from __future__ import annotations

import html
from datetime import date
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from app.modules.attendance.services.attendance_export_service import (
    _period,
    _xlsx_bytes,
    generated_stamp,  # noqa: F401 — re-exported for the report service
    render_html_to_pdf,  # noqa: F401 — re-exported for the report service
)
from app.modules.attendance.services.attendance_export_service import (
    _logo_data_uri,
)

_BOLD = Font(bold=True)
_CENTER = Alignment(horizontal="center")
_HEAD_FILL = PatternFill("solid", fgColor="EEF1F5")
_STATUS_FILL = {
    "PRESENT": PatternFill("solid", fgColor="D7F0DB"),
    "LATE": PatternFill("solid", fgColor="FCEFC7"),
    "HALF_DAY": PatternFill("solid", fgColor="FCEFC7"),
    "ABSENT": PatternFill("solid", fgColor="F8D7DA"),
    "WO": PatternFill("solid", fgColor="E7E7EF"),
    "HOLIDAY": PatternFill("solid", fgColor="E7E7EF"),
}

# Short status codes for the grid (mirrors the e-TimeOffice P/A/WO glyphs).
STATUS_CODE = {
    "PRESENT": "P", "LATE": "L", "HALF_DAY": "½", "ABSENT": "A",
    "WO": "WO", "HOLIDAY": "H",
}

_LIST_HEADERS = ["Date", "Emp Code", "Name", "Department", "In", "Out", "Work", "OT", "Status"]


def _esc(v: Any) -> str:
    return html.escape("" if v is None else str(v))


def fmt_minutes(minutes: int | None) -> str:
    """Minutes -> H:MM (0 -> 0:00), matching the report's Work/OT columns."""
    m = int(minutes or 0)
    return f"{m // 60}:{m % 60:02d}"


# ── PDF document shell (self-contained; crest embedded) ─────────────────────

_PDF_CSS = """
* { box-sizing: border-box; }
body { font: 12px -apple-system, Segoe UI, Roboto, sans-serif; color: #1a1a1a; margin: 0; }
h1 { font-size: 16px; margin: 0 0 2px; }
.sub { color: #555; font-size: 11px; margin: 0 0 10px; }
.genstamp { color: #888; margin-top: 12px; }
table { border-collapse: collapse; width: 100%; margin-bottom: 14px; }
th, td { border: 1px solid #cfd6df; padding: 3px 6px; font-size: 10.5px; }
th { background: #eef1f5; text-align: left; }
td.c, th.c { text-align: center; }
.staff-hd { background: #f5f7fa; font-weight: bold; padding: 4px 6px; border: 1px solid #cfd6df; }
.P { background: #d7f0db; } .L { background: #fcefc7; } .A { background: #f8d7da; }
.WO { background: #e7e7ef; } .H { background: #e7e7ef; }
"""


def _doc(body: str, generated: str = "") -> str:
    logo = _logo_data_uri()
    crest = f"<img src='{logo}' style='height:34px;float:right'>" if logo else ""
    foot = f"<p class='sub genstamp'>{_esc(generated)}</p>" if generated else ""
    return (
        f"<!DOCTYPE html><html><head><meta charset='utf-8'>"
        f"<style>{_PDF_CSS}</style></head><body>{crest}{body}{foot}</body></html>"
    )


# ── List report (every typed report) ───────────────────────────────────────

def list_html(
    *, brand: str, title: str, subtitle: str, rows: list[dict], generated: str = "",
) -> str:
    ths = "".join(f"<th>{_esc(h)}</th>" for h in _LIST_HEADERS)
    body_rows = "".join(
        "<tr>"
        f"<td>{_esc(r['date'])}</td>"
        f"<td class='c'>{_esc(r['emp_code'])}</td>"
        f"<td>{_esc(r['name'])}</td>"
        f"<td>{_esc(r['department'])}</td>"
        f"<td class='c'>{_esc(r['in'])}</td>"
        f"<td class='c'>{_esc(r['out'])}</td>"
        f"<td class='c'>{_esc(r['work'])}</td>"
        f"<td class='c'>{_esc(r['ot'])}</td>"
        f"<td class='c {_esc(STATUS_CODE.get(r['status'], ''))}'>{_esc(r['status'])}</td>"
        "</tr>"
        for r in rows
    )
    empty = "" if rows else "<p class='sub'>No matching records for this period.</p>"
    body = (
        f"<h1>{_esc(brand)} — {_esc(title)}</h1>"
        f"<p class='sub'>{_esc(subtitle)}</p>"
        f"<table><tr>{ths}</tr>{body_rows}</table>{empty}"
    )
    return _doc(body, generated)


def list_xlsx(
    *, brand: str, title: str, subtitle: str, rows: list[dict], generated: str = "",
) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Report"
    ws["A1"] = brand
    ws["A1"].font = Font(bold=True, size=14)
    ws["A2"] = title
    ws["A2"].font = Font(bold=True, size=12)
    ws["A3"] = subtitle
    ws["A4"] = generated

    head = 5
    for c, h in enumerate(_LIST_HEADERS, start=1):
        cell = ws.cell(row=head, column=c, value=h)
        cell.font = _BOLD
        cell.fill = _HEAD_FILL
    for i, r in enumerate(rows, start=head + 1):
        ws.cell(row=i, column=1, value=r["date"])
        ws.cell(row=i, column=2, value=r["emp_code"]).alignment = _CENTER
        ws.cell(row=i, column=3, value=r["name"])
        ws.cell(row=i, column=4, value=r["department"])
        ws.cell(row=i, column=5, value=r["in"]).alignment = _CENTER
        ws.cell(row=i, column=6, value=r["out"]).alignment = _CENTER
        ws.cell(row=i, column=7, value=r["work"]).alignment = _CENTER
        ws.cell(row=i, column=8, value=r["ot"]).alignment = _CENTER
        cell = ws.cell(row=i, column=9, value=r["status"])
        cell.alignment = _CENTER
        if r["status"] in _STATUS_FILL:
            cell.fill = _STATUS_FILL[r["status"]]
    for c, w in enumerate((12, 10, 22, 20, 8, 8, 8, 8, 12), start=1):
        ws.column_dimensions[get_column_letter(c)].width = w
    return _xlsx_bytes(wb)


# ── Performance grid (TeamOffice-style monthly/weekly block) ────────────────

def grid_html(
    *, brand: str, title: str, subtitle: str, dates: list[date],
    staff_blocks: list[dict], generated: str = "",
) -> str:
    """One block per staff member: totals line + a table with a column per date
    carrying IN / OUT / WORK / OT / Status."""
    day_ths = "".join(f"<th class='c'>{d.day}/{d.month}</th>" for d in dates)
    blocks = []
    for b in staff_blocks:
        cells = b["cells"]  # aligned to dates
        def _row(field: str) -> str:
            return "".join(f"<td class='c'>{_esc(c.get(field, ''))}</td>" for c in cells)
        status_row = "".join(
            f"<td class='c {_esc(STATUS_CODE.get(c.get('status'), ''))}'>"
            f"{_esc(STATUS_CODE.get(c.get('status'), ''))}</td>"
            for c in cells
        )
        blocks.append(
            f"<div class='staff-hd'>{_esc(b['emp_code'])} · {_esc(b['name'])} · "
            f"{_esc(b['department'])}"
            f" — Present {b['present']} · Absent {b['absent']} · WO {b['wo']} · "
            f"Work+OT {b['work_ot']}</div>"
            f"<table><tr><th>Field</th>{day_ths}</tr>"
            f"<tr><th>In</th>{_row('in')}</tr>"
            f"<tr><th>Out</th>{_row('out')}</tr>"
            f"<tr><th>Work</th>{_row('work')}</tr>"
            f"<tr><th>OT</th>{_row('ot')}</tr>"
            f"<tr><th>Status</th>{status_row}</tr>"
            f"</table>"
        )
    empty = "" if staff_blocks else "<p class='sub'>No staff match the selection.</p>"
    body = (
        f"<h1>{_esc(brand)} — {_esc(title)}</h1>"
        f"<p class='sub'>{_esc(subtitle)}</p>{''.join(blocks)}{empty}"
    )
    return _doc(body, generated)


def grid_xlsx(
    *, brand: str, title: str, subtitle: str, dates: list[date],
    staff_blocks: list[dict], generated: str = "",
) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Performance"
    ws["A1"] = brand
    ws["A1"].font = Font(bold=True, size=14)
    ws["A2"] = title
    ws["A2"].font = Font(bold=True, size=12)
    ws["A3"] = subtitle
    ws["A4"] = generated

    row = 6
    for b in staff_blocks:
        ws.cell(
            row=row, column=1,
            value=(
                f"{b['emp_code']} · {b['name']} · {b['department']} — "
                f"Present {b['present']} · Absent {b['absent']} · WO {b['wo']} · "
                f"Work+OT {b['work_ot']}"
            ),
        ).font = _BOLD
        row += 1
        ws.cell(row=row, column=1, value="Field").font = _BOLD
        for j, d in enumerate(dates):
            c = ws.cell(row=row, column=2 + j, value=f"{d.day}/{d.month}")
            c.font = _BOLD
            c.fill = _HEAD_FILL
            c.alignment = _CENTER
        for field in ("in", "out", "work", "ot", "status"):
            row += 1
            ws.cell(row=row, column=1, value=field.capitalize()).font = _BOLD
            for j, cell in enumerate(b["cells"]):
                val = STATUS_CODE.get(cell.get("status"), "") if field == "status" else cell.get(field, "")
                out = ws.cell(row=row, column=2 + j, value=val)
                out.alignment = _CENTER
                if field == "status" and cell.get("status") in _STATUS_FILL:
                    out.fill = _STATUS_FILL[cell["status"]]
        row += 2  # blank spacer between staff blocks

    ws.column_dimensions["A"].width = 10
    for j in range(len(dates)):
        ws.column_dimensions[get_column_letter(2 + j)].width = 6
    return _xlsx_bytes(wb)
