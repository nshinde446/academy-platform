"""Staff Late Fine Report — fine calc + per-day rows + colored export + total."""

import io
import uuid
from datetime import date, datetime, timezone

import pytest
from fastapi import HTTPException
from openpyxl import load_workbook
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.attendance.models.attendance_models import (
    LateFineSlab,
    StaffDailyAttendance,
)
from app.modules.attendance.services import staff_late_fine_service as lf
from app.modules.staff.models.staff_models import Department, Staff

BRANCH = uuid.UUID("00000000-0000-0000-0000-000000000001")
UTC = timezone.utc


def _slab(mn, mx, amt, hx, lbl):
    return LateFineSlab(min_minutes=mn, max_minutes=mx, fine_amount=amt, color_hex=hx, label=lbl)


async def _seed(db: AsyncSession) -> Staff:
    db.add_all([
        _slab(1, 5, 200, "#BDD7EE", "1 to 5"),
        _slab(6, 10, 500, "#FFEB84", "6 to 10"),
        _slab(11, None, 1000, "#FF6B6B", "11 or more"),
    ])
    dept = Department(branch_id=BRANCH, name="MSA-Teachers", id_range_start=1, id_range_end=50)
    db.add(dept)
    await db.flush()
    staff = Staff(
        branch_id=BRANCH, emp_code="12", first_name="Rahul", last_name="Pawar",
        department_id=dept.id, shift_start="08:00",
    )
    db.add(staff)
    await db.flush()
    # IST = UTC+5:30, so local 08:04 = UTC 02:34 (matches the spec's example).
    for day, h, m in [(1, 2, 28), (2, 2, 34), (3, 2, 38), (4, 2, 46)]:  # 07:58, 08:04, 08:08, 08:16 IST
        db.add(StaffDailyAttendance(
            staff_id=staff.id, branch_id=BRANCH, attendance_date=date(2026, 10, day),
            first_in=datetime(2026, 10, day, h, m, tzinfo=UTC),
            day_status="PRESENT", signoff="COMPLETE", source="BIOMETRIC", work_minutes=400,
        ))
    await db.flush()
    return staff


def test_fine_calc_matches_spec_example():
    slabs = [_slab(1, 5, 200, "#BDD7EE", "a"), _slab(6, 10, 500, "#FFEB84", "b"),
             _slab(11, None, 1000, "#FF6B6B", "c")]
    for mins, exp_fine in [(0, 0), (4, 200), (5, 200), (8, 500), (10, 500), (11, 1000), (16, 1000)]:
        assert lf.fine_for(mins, slabs)[0] == exp_fine
    # early/on-time never negative
    assert lf.late_minutes("08:00", datetime(2026, 10, 2, 7, 58)) == 0
    assert lf.late_minutes("08:00", datetime(2026, 10, 2, 8, 16)) == 16


async def test_late_fine_xlsx_rows_colors_and_total(db_session: AsyncSession, seed_data):
    staff = await _seed(db_session)
    fn, data, mime = await lf.generate(
        db_session, branch_id=BRANCH, staff_id=staff.id,
        start=date(2026, 10, 1), end=date(2026, 10, 4), fmt="xlsx",
    )
    assert fn.startswith("LateFine_12_2026-10-01_to_2026-10-04") and mime == lf.XLSX_MIME
    ws = load_workbook(io.BytesIO(data)).active
    rows = list(ws.iter_rows(values_only=True))
    # locate the header, then the 4 data rows (Date, Start, IN, LateIN, LateMin, Fine)
    hdr = next(i for i, r in enumerate(rows) if r[0] == "Date")
    data_rows = rows[hdr + 1: hdr + 5]
    late_min = [r[4] for r in data_rows]
    fines = [r[5] for r in data_rows]
    assert late_min == [0, 4, 8, 16]
    assert fines == [0, 200, 500, 1000]
    # Late IN formatted hh:mm
    assert [r[3] for r in data_rows] == ["00:00", "00:04", "00:08", "00:16"]
    # Total Fine row
    total_row = rows[hdr + 5]
    assert total_row[3] == "Total Fine" and total_row[5] == 1700
    # Late Minutes cell is colored per slab (16 -> red #FF6B6B).
    ws2 = load_workbook(io.BytesIO(data)).active
    red_cell = ws2.cell(row=hdr + 1 + 4, column=5)  # 4th data row, col E
    assert red_cell.fill.fgColor.rgb.endswith("FF6B6B")


def test_late_fine_html_has_colored_cell_and_total():
    # The PDF is rendered from this HTML (Chromium isn't available in tests).
    report = {
        "brand": "Matrix", "emp_code": "12", "name": "Rahul Pawar",
        "period": "01-10-2026 to 04-10-2026", "total": 1700.0,
        "rows": [
            {"date": "02-10-2026", "start": "08:00", "in": "08:04", "late_in": "00:04",
             "late_minutes": 4, "fine": 200, "color": "#BDD7EE"},
            {"date": "04-10-2026", "start": "08:00", "in": "08:16", "late_in": "00:16",
             "late_minutes": 16, "fine": 1000, "color": "#FF6B6B"},
        ],
    }
    html = lf._html(report, "gen")
    assert "Staff Late Fine Report" in html
    assert "background:#FF6B6B" in html          # Late Minutes cell colored
    assert "Total Fine" in html and ">1700<" in html


async def test_late_fine_rejects_from_after_to(db_session: AsyncSession, seed_data):
    staff = await _seed(db_session)
    with pytest.raises(HTTPException) as ei:
        await lf.generate(db_session, branch_id=BRANCH, staff_id=staff.id,
                          start=date(2026, 10, 4), end=date(2026, 10, 1), fmt="pdf")
    assert ei.value.status_code == 422
