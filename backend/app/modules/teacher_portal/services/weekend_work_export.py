"""Excel export for the Saturday/Sunday Work Report (Point 5).

Reproduces the client's sheet (e.g. "SUNDAY 1 Nov 2026 - PRE APPROVED WORK
STATUS"): a merged title with the weekend date, then
Empcode | Name | <Weekday> | Time IN | Time OUT | Work Content | Work Approved
Status, then the numbered rules as a NOTE block.

For a single date the day column is headed by the weekday and the date lives in
the title (exactly like the sheet). For a multi-day range a Date column is added
and the day column is headed "Status", so the same export still works end to end.
"""

from __future__ import annotations

import io
from datetime import date

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

_HEAD_FILL = PatternFill("solid", fgColor="D9D9D9")
_HEAD_FONT = Font(bold=True)
_TITLE_FONT = Font(bold=True, size=12)
_WARN_FILL = PatternFill("solid", fgColor="FDE2E1")
_WRAP_TOP = Alignment(wrap_text=True, vertical="top")
_CENTER = Alignment(horizontal="center", vertical="center")
_thin = Side(style="thin", color="999999")
_BORDER = Border(left=_thin, right=_thin, top=_thin, bottom=_thin)

_WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
_MONTHS = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _fmt_date(d: date) -> str:
    return f"{d.day} {_MONTHS[d.month]} {d.year}"


def _approved_label(row: dict) -> str:
    """Work Approved Status cell — the note verbatim when decided (that's what the
    client types, e.g. 'Approved by Ravi Sir, Screenshot is shared'); blank while
    still pending, exactly like the sheet."""
    st = row.get("approval_status") or "PENDING"
    note = (row.get("approval_note") or "").strip()
    if st == "APPROVED":
        return note or "Approved"
    if st == "REJECTED":
        return f"Rejected — {note}" if note else "Rejected"
    return ""  # pending → blank


def weekend_report_xlsx(*, brand: str, title: str, rows: list[dict], rules: list[str]) -> bytes:
    # Single-date report → weekday column header + date in the title (the sheet);
    # a range → a Date column and a generic "Status" header.
    dates = {r["work_date"] for r in rows if r.get("work_date")}
    single = len(dates) == 1
    only_date = next(iter(dates)) if single else None

    if single and only_date is not None:
        weekday = _WEEKDAYS[only_date.weekday()]
        sheet_title = f"{weekday.upper()} {_fmt_date(only_date)}  -  PRE APPROVED WORK STATUS"
        headers = ["Empcode", "Name", weekday, "Time IN", "Time OUT", "Work Content", "Work Approved Status"]
    else:
        sheet_title = (title or "WEEKEND WORK").upper()
        headers = ["Empcode", "Name", "Date", "Status", "Time IN", "Time OUT", "Work Content", "Work Approved Status"]

    ncols = len(headers)
    wb = Workbook()
    ws = wb.active
    ws.title = "Weekend Work"

    # Merged title row across all columns.
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=ncols)
    tcell = ws.cell(row=1, column=1, value=sheet_title)
    tcell.font = _TITLE_FONT
    tcell.alignment = _CENTER

    head = 2
    for c, h in enumerate(headers, start=1):
        cell = ws.cell(row=head, column=c, value=h)
        cell.font = _HEAD_FONT
        cell.fill = _HEAD_FILL
        cell.alignment = _CENTER
        cell.border = _BORDER

    r = head
    for row in rows:
        r += 1
        warn = bool(row.get("warning"))
        if single:
            values = [
                row.get("emp_code") or "",
                row.get("name") or "",
                row.get("day_code") or "",
                row.get("time_in") or "",
                row.get("time_out") or "",
                row.get("work_content") or "",
                _approved_label(row),
            ]
        else:
            values = [
                row.get("emp_code") or "",
                row.get("name") or "",
                str(row.get("work_date") or ""),
                row.get("day_code") or "",
                row.get("time_in") or "",
                row.get("time_out") or "",
                row.get("work_content") or "",
                _approved_label(row),
            ]
        for c, v in enumerate(values, start=1):
            cell = ws.cell(row=r, column=c, value=v)
            cell.border = _BORDER
            cell.alignment = _WRAP_TOP
            # A faint highlight flags a day that breaks a rule (under 5h or a
            # missing punch) — an aid the client sheet does by hand.
            if warn:
                cell.fill = _WARN_FILL

    # NOTE block — the rules, verbatim, below the table (as on the sheet).
    r += 2
    ws.cell(row=r, column=1, value="NOTE:").font = Font(bold=True)
    for i, rule in enumerate(rules, start=1):
        r += 1
        ws.cell(row=r, column=1, value=i)
        c2 = ws.cell(row=r, column=2, value=rule)
        c2.alignment = _WRAP_TOP

    # Column widths — wide Content + Approved columns like the sheet.
    name_col = 2
    content_col = ncols - 1
    approved_col = ncols
    ws.column_dimensions[get_column_letter(1)].width = 10
    ws.column_dimensions[get_column_letter(name_col)].width = 22
    ws.column_dimensions[get_column_letter(content_col)].width = 34
    ws.column_dimensions[get_column_letter(approved_col)].width = 34

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
