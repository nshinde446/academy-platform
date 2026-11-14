"""Excel export for the Saturday/Sunday Work Report (Point 5).

Mirrors the client's sheet (SUNDAY … PRE APPROVED WORK STATUS): one row per staff
per weekend day, then the numbered rules as a NOTE at the bottom.
"""

from __future__ import annotations

import io

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

_HEAD_FILL = PatternFill("solid", fgColor="0F2947")
_HEAD_FONT = Font(bold=True, color="FFFFFF")
_WARN_FILL = PatternFill("solid", fgColor="FDE2E1")

_HEADERS = [
    "Empcode", "Name", "Date", "Status", "Time IN", "Time OUT",
    "Hours", "Work Content", "Work Approved Status",
]


def _hours(minutes: int) -> str:
    h, m = divmod(int(minutes or 0), 60)
    return f"{h}:{m:02d}"


def _approved_label(row: dict) -> str:
    st = row.get("approval_status") or "PENDING"
    note = row.get("approval_note")
    if st == "APPROVED":
        return f"Approved — {note}" if note else "Approved"
    if st == "REJECTED":
        return f"Rejected — {note}" if note else "Rejected"
    return "Pending"


def weekend_report_xlsx(*, brand: str, title: str, rows: list[dict], rules: list[str]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Weekend Work"

    ws["A1"] = brand
    ws["A1"].font = Font(bold=True, size=14, color="003464")
    ws["A2"] = title
    ws["A2"].font = Font(bold=True)

    head = 4
    for c, h in enumerate(_HEADERS, start=1):
        cell = ws.cell(row=head, column=c, value=h)
        cell.font = _HEAD_FONT
        cell.fill = _HEAD_FILL

    r = head
    for row in rows:
        r += 1
        warn = bool(row.get("warning"))
        values = [
            row.get("emp_code") or "",
            row.get("name") or "",
            str(row.get("work_date") or ""),
            row.get("day_code") or "",
            row.get("time_in") or "—",
            row.get("time_out") or "—",
            _hours(row.get("work_minutes", 0)),
            row.get("work_content") or "",
            _approved_label(row),
        ]
        for c, v in enumerate(values, start=1):
            cell = ws.cell(row=r, column=c, value=v)
            # Highlight a row that breaks a rule (under 5h or a missing punch).
            if warn:
                cell.fill = _WARN_FILL

    # NOTE block — the rules, verbatim, below the table.
    r += 2
    note = ws.cell(row=r, column=1, value="NOTE")
    note.font = Font(bold=True)
    for i, rule in enumerate(rules, start=1):
        r += 1
        ws.cell(row=r, column=1, value=i)
        c2 = ws.cell(row=r, column=2, value=rule)
        c2.alignment = Alignment(wrap_text=True)

    ws.column_dimensions["B"].width = 24
    ws.column_dimensions["H"].width = 40
    ws.column_dimensions["I"].width = 26

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
