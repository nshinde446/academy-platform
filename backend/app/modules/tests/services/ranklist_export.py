"""Rank-list exporters — branded PDF (notice-board / parents) and Excel.

Pure builders over the ``get_ranklist`` dict; reuses the attendance module's
headless-Chromium PDF renderer and the embedded MSA crest so the look matches
the day-attendance report.

Client change requests (31 Oct 2026):
  * subject / total headers carry the max marks in brackets, taken automatically
    from the test setup — e.g. ``Physics (50)``, ``Total (200)``;
  * a Google-Sheets-style colour scale is applied *per marks column* (each
    column compared within itself, absentees ignored) and must survive into the
    downloaded PDF and Excel;
  * the ``%`` column is removed everywhere.
"""

from __future__ import annotations

import html
import io
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

from app.modules.attendance.services.attendance_export_service import (
    _logo_data_uri,
    render_html_to_pdf,
)

_HEAD_FILL = PatternFill("solid", fgColor="0F2947")
_HEAD_FONT = Font(bold=True, color="FFFFFF")
_BOLD = Font(bold=True)

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
PDF_MIME = "application/pdf"

# Google-Sheets "Green–White–Red" colour-scale endpoints. Lowest = red, middle
# (the average of the column's min and max) = white, highest = green. Kept light
# enough that the default dark cell text stays readable.
_RED = (0xE6, 0x7C, 0x73)
_WHITE = (0xFF, 0xFF, 0xFF)
_GREEN = (0x57, 0xBB, 0x8A)


def _esc(v: Any) -> str:
    return html.escape(str(v))


def _fmt_marks(m: float | None, total: float) -> str:
    if m is None:
        return "—"
    return f"{m:g} / {total:g}"


def _subjects(ranklist: dict) -> list[dict]:
    return ranklist.get("subjects") or []


def _subject_names(ranklist: dict) -> list[str]:
    return [s["subject_name"] for s in _subjects(ranklist)]


def _header(label: str, total: float | None) -> str:
    """``Physics (50)`` — the max marks come from the test setup, not typed by
    hand, so a 25- or 120-mark subject shows correctly. Falls back to the bare
    label when a total is unknown."""
    return f"{label} ({total:g})" if total is not None else label


def _fmt_cell(v: float | None) -> str:
    return "—" if v is None else f"{v:g}"


def _lerp(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))  # type: ignore[return-value]


def _scale_rgb(value: float, vmin: float, vmax: float) -> tuple[int, int, int] | None:
    """Colour for ``value`` on the column's own red→white→green scale, or None
    when there is nothing to scale (no spread, so every cell would be identical)."""
    if value is None or vmax <= vmin:
        return None
    mid = (vmin + vmax) / 2
    if value >= mid:
        t = (value - mid) / (vmax - mid) if vmax > mid else 0.0
        return _lerp(_WHITE, _GREEN, t)
    t = (value - vmin) / (mid - vmin) if mid > vmin else 1.0
    return _lerp(_RED, _WHITE, t)


def _hex(rgb: tuple[int, int, int]) -> str:
    return "{:02X}{:02X}{:02X}".format(*rgb)


def _column_bounds(ranklist: dict) -> dict[str, tuple[float, float]]:
    """Min/max of each marks column across *appeared* students only (absentees are
    ignored, otherwise their blank/zero would drag the scale). Keyed by subject
    name, plus the synthetic ``"__total__"`` column."""
    ranked = ranklist["ranked"]
    bounds: dict[str, tuple[float, float]] = {}
    totals = [r["marks_obtained"] for r in ranked if r.get("marks_obtained") is not None]
    if totals:
        bounds["__total__"] = (min(totals), max(totals))
    for name in _subject_names(ranklist):
        vals = [
            r["subject_marks"].get(name)
            for r in ranked
            if r.get("subject_marks", {}).get(name) is not None
        ]
        if vals:
            bounds[name] = (min(vals), max(vals))
    return bounds


def ranklist_xlsx(*, brand: str, ranklist: dict) -> bytes:
    total = ranklist["total_marks"] or 0.0
    subjects = _subjects(ranklist)
    bounds = _column_bounds(ranklist)
    wb = Workbook()
    ws = wb.active
    ws.title = "Rank list"

    ws["A1"] = brand
    ws["A1"].font = Font(bold=True, size=14, color="003464")
    ws["A2"] = ranklist["test_name"]
    ws["A3"] = (
        f"Ranked {len(ranklist['ranked'])} · Absent {len(ranklist['absentees'])}"
        f" · Total marks {total:g}"
    )

    # Per-subject columns sit between Student Name and Total (per-subject flow);
    # an OMR test (no subjects) keeps the single "Marks" column. No "%" column.
    marks_label = "Total" if subjects else "Marks"
    headers = [
        "Rank",
        "PRN",
        "Student Name",
        *[_header(s["subject_name"], s.get("total_marks")) for s in subjects],
        _header(marks_label, total),
    ]
    head = 5
    for c, h in enumerate(headers, start=1):
        cell = ws.cell(row=head, column=c, value=h)
        cell.font = _HEAD_FONT
        cell.fill = _HEAD_FILL

    def _paint(cell, column_key: str, value: float | None) -> None:
        if value is None or column_key not in bounds:
            return
        rgb = _scale_rgb(value, *bounds[column_key])
        if rgb is not None:
            cell.fill = PatternFill("solid", fgColor=_hex(rgb))

    r = head
    for row in ranklist["ranked"]:
        r += 1
        ws.cell(row=r, column=1, value=row["rank"])
        ws.cell(row=r, column=2, value=row.get("prn") or "")
        ws.cell(row=r, column=3, value=row["name"])
        col = 4
        for name in _subject_names(ranklist):
            v = row.get("subject_marks", {}).get(name)
            cell = ws.cell(row=r, column=col, value=_fmt_cell(v))
            _paint(cell, name, v)
            col += 1
        total_cell = ws.cell(row=r, column=col, value=_fmt_marks(row["marks_obtained"], total))
        _paint(total_cell, "__total__", row["marks_obtained"])
    for row in ranklist["absentees"]:
        r += 1
        ws.cell(row=r, column=1, value="—")
        ws.cell(row=r, column=2, value=row.get("prn") or "")
        ws.cell(row=r, column=3, value=row["name"])
        col = 4
        for _name in _subject_names(ranklist):
            ws.cell(row=r, column=col, value="—")
            col += 1
        ws.cell(row=r, column=col, value="ABSENT")

    ws.column_dimensions["B"].width = 14
    ws.column_dimensions["C"].width = 26

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


_CSS = """
@page { margin: 12mm 10mm; }
* { box-sizing: border-box; }
body { font-family: -apple-system, "Segoe UI", Arial, sans-serif; color:#111; font-size:10pt; margin:0; }
.brandbar { display:flex; align-items:center; gap:12px; border-bottom:2px solid #003464; padding-bottom:10px; }
.brandbar img { width:48px; height:48px; }
.brandbar h1 { font-size:18pt; margin:0; color:#003464; font-weight:800; }
.sub { color:#555; font-size:9.5pt; margin:8px 0 12px; }
table { border-collapse:collapse; width:100%; }
th, td { border:1px solid #d7dde4; padding:4pt 6pt; font-size:9.5pt; text-align:left; }
th { background:#0f2947; color:#fff; font-weight:700; }
td.c { text-align:center; }
.absent td { color:#c0392b; font-weight:700; }
.credit { text-align:right; color:#888; font-size:8pt; font-style:italic; margin-top:8px; }
"""


def _cell_style(column_key: str, value: float | None, bounds: dict) -> str:
    if value is None or column_key not in bounds:
        return ""
    rgb = _scale_rgb(value, *bounds[column_key])
    return f" style='background:#{_hex(rgb)}'" if rgb is not None else ""


def ranklist_html(*, brand: str, ranklist: dict) -> str:
    total = ranklist["total_marks"] or 0.0
    subjects = _subjects(ranklist)
    bounds = _column_bounds(ranklist)
    logo = _logo_data_uri()
    logo_html = f"<img src='{logo}' alt=''>" if logo else ""
    marks_label = "Total" if subjects else "Marks"
    subject_ths = "".join(
        f"<th class='c'>{_esc(_header(s['subject_name'], s.get('total_marks')))}</th>"
        for s in subjects
    )
    body = [
        f"<div class='brandbar'>{logo_html}<h1>{_esc(brand)}</h1></div>",
        f"<p class='sub'><b>{_esc(ranklist['test_name'])}</b><br>"
        f"Ranked {len(ranklist['ranked'])} · Absent {len(ranklist['absentees'])}"
        f" · Total marks {total:g}</p>",
        "<table><tr><th>Rank</th><th>PRN</th><th>Student Name</th>"
        f"{subject_ths}<th class='c'>{_esc(_header(marks_label, total))}</th></tr>",
    ]
    for row in ranklist["ranked"]:
        if row["percentage"] is None:
            continue
        subj_tds = "".join(
            f"<td class='c'{_cell_style(s['subject_name'], row.get('subject_marks', {}).get(s['subject_name']), bounds)}>"
            f"{_esc(_fmt_cell(row.get('subject_marks', {}).get(s['subject_name'])))}</td>"
            for s in subjects
        )
        body.append(
            f"<tr><td class='c'>{row['rank']}</td>"
            f"<td>{_esc(row.get('prn') or '—')}</td>"
            f"<td>{_esc(row['name'])}</td>"
            f"{subj_tds}"
            f"<td class='c'{_cell_style('__total__', row['marks_obtained'], bounds)}>"
            f"{_esc(_fmt_marks(row['marks_obtained'], total))}</td></tr>"
        )
    for row in ranklist["absentees"]:
        subj_tds = "".join("<td class='c'>—</td>" for _ in subjects)
        body.append(
            f"<tr class='absent'><td class='c'>—</td>"
            f"<td>{_esc(row.get('prn') or '—')}</td>"
            f"<td>{_esc(row['name'])}</td>"
            f"{subj_tds}"
            f"<td class='c'>ABSENT</td></tr>"
        )
    body.append("</table>")
    body.append("<div class='credit'>Powered by EduPulse Technologies</div>")
    return (
        f"<!DOCTYPE html><html><head><meta charset='utf-8'>"
        f"<style>{_CSS}</style></head><body>{''.join(body)}</body></html>"
    )


async def ranklist_pdf(*, brand: str, ranklist: dict) -> bytes:
    return await render_html_to_pdf(ranklist_html(brand=brand, ranklist=ranklist))
