"""Point 5 — Saturday/Sunday work flow: pre-approval → work content → report +
approval, biometric IN/OUT, the ≥5h / missing-punch warning, the management
ABSENT override, and the payroll-credit derivation (1.0 full / 0.5 half)."""

import io
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from openpyxl import load_workbook

from app.modules.attendance.models.attendance_models import StaffDailyAttendance
from app.modules.staff.models.staff_models import Department, Staff
from app.modules.teacher_portal.services import weekend_work_service as wws
from app.modules.teacher_portal.services import weekend_work_export as export

BRANCH = uuid.UUID("00000000-0000-0000-0000-000000000001")
USER = uuid.UUID("00000000-0000-0000-0000-000000000100")


def _next_sunday() -> date:
    d = date(2026, 11, 1)
    while d.weekday() != 6:  # Sunday
        d += timedelta(days=1)
    return d


async def _staff(db, emp_code="92000") -> Staff:
    dept = Department(
        branch_id=BRANCH, name=f"WW-{emp_code}", id_range_start=92000, id_range_end=92999
    )
    db.add(dept)
    await db.flush()
    s = Staff(
        branch_id=BRANCH, emp_code=emp_code, first_name="Ravi", last_name="K",
        department_id=dept.id,
    )
    db.add(s)
    await db.flush()
    return s


async def _attendance(db, staff, day, *, status="PRESENT", minutes=360, punched=True):
    row = StaffDailyAttendance(
        branch_id=BRANCH, staff_id=staff.id, attendance_date=day,
        day_status=status, signoff="COMPLETE", source="BIOMETRIC",
        work_minutes=minutes,
        first_in=datetime(day.year, day.month, day.day, 9, 0, tzinfo=timezone.utc) if punched else None,
        last_out=datetime(day.year, day.month, day.day, 15, 0, tzinfo=timezone.utc) if punched else None,
    )
    db.add(row)
    await db.flush()
    return row


@pytest.mark.usefixtures("seed_data")
async def test_preapprove_rejects_a_weekday(db_session, seed_data):
    s = await _staff(db_session)
    weekday = date(2026, 11, 2)  # a Monday
    with pytest.raises(Exception):
        await wws.preapprove(
            db_session, branch_id=BRANCH, staff_ids=[s.id],
            work_date=weekday, user_id=USER,
        )


@pytest.mark.usefixtures("seed_data")
async def test_full_flow_preapprove_content_approve_credits_one(db_session, seed_data):
    s = await _staff(db_session)
    sun = _next_sunday()
    await _attendance(db_session, s, sun, status="PRESENT", minutes=360)

    res = await wws.preapprove(
        db_session, branch_id=BRANCH, staff_ids=[s.id], work_date=sun, user_id=USER,
    )
    assert res["created"] == 1
    # Idempotent: second pre-approval for the same staff+date is skipped.
    res2 = await wws.preapprove(
        db_session, branch_id=BRANCH, staff_ids=[s.id], work_date=sun, user_id=USER,
    )
    assert res2["created"] == 0

    rep = await wws.report(db_session, branch_id=BRANCH, start=sun, end=sun)
    assert len(rep["rules"]) == 5
    row = rep["rows"][0]
    assert row["emp_code"] == "92000"
    assert row["day_code"] == "P"
    # IN/OUT come through (formatted in the branch's local timezone).
    assert row["time_in"] is not None and row["time_out"] is not None
    assert row["warning"] is False  # 6h ≥ 5h, both punches present
    assert row["approval_status"] == "PENDING"

    # Teacher writes content.
    updated = await wws.submit_work_content(
        db_session, staff_id=s.id, work_id=row["id"],
        content="3h lecture, 2h prep, 1h doubts", user_id=USER,
    )
    assert updated["work_content"] == "3h lecture, 2h prep, 1h doubts"

    # Approve → credits a full extra day.
    decided = await wws.decide(
        db_session, work_id=row["id"], branch_id=BRANCH, approve=True,
        note="Approved by Ravi Sir", user_id=USER,
    )
    assert decided["approval_status"] == "APPROVED"
    assert decided["credit_days"] == 1.0


@pytest.mark.usefixtures("seed_data")
async def test_half_day_credits_half(db_session, seed_data):
    s = await _staff(db_session, emp_code="92001")
    sun = _next_sunday()
    await _attendance(db_session, s, sun, status="HALF_DAY", minutes=180)
    await wws.preapprove(db_session, branch_id=BRANCH, staff_ids=[s.id], work_date=sun, user_id=USER)
    row = (await wws.report(db_session, branch_id=BRANCH, start=sun, end=sun))["rows"][0]
    assert row["day_code"] == "HD"
    assert row["warning"] is True  # 3h < 5h
    decided = await wws.decide(
        db_session, work_id=row["id"], branch_id=BRANCH, approve=True, note=None, user_id=USER,
    )
    assert decided["credit_days"] == 0.5


@pytest.mark.usefixtures("seed_data")
async def test_missing_punch_warns_and_marks_absent_zeroes_credit(db_session, seed_data):
    s = await _staff(db_session, emp_code="92002")
    sun = _next_sunday()
    # Punched IN but no OUT, under 5h → warning.
    await _attendance(db_session, s, sun, status="PRESENT", minutes=120, punched=False)
    await wws.preapprove(db_session, branch_id=BRANCH, staff_ids=[s.id], work_date=sun, user_id=USER)
    row = (await wws.report(db_session, branch_id=BRANCH, start=sun, end=sun))["rows"][0]
    assert row["warning"] is True

    await wws.decide(db_session, work_id=row["id"], branch_id=BRANCH, approve=True, note=None, user_id=USER)
    # Management forces ABSENT (Rule 5) → code A, no credit.
    out = await wws.set_marked_absent(
        db_session, work_id=row["id"], branch_id=BRANCH, absent=True, user_id=USER,
    )
    assert out["day_code"] == "A"
    assert out["credit_days"] == 0.0


@pytest.mark.usefixtures("seed_data")
async def test_report_filters_and_export(db_session, seed_data):
    s = await _staff(db_session, emp_code="92003")
    sun = _next_sunday()
    await _attendance(db_session, s, sun, status="PRESENT", minutes=360)
    await wws.preapprove(db_session, branch_id=BRANCH, staff_ids=[s.id], work_date=sun, user_id=USER)

    # Filter by a PENDING status returns it; APPROVED returns nothing yet.
    pend = await wws.report(db_session, branch_id=BRANCH, start=sun, end=sun, approval_status="PENDING")
    assert len(pend["rows"]) == 1
    appr = await wws.report(db_session, branch_id=BRANCH, start=sun, end=sun, approval_status="APPROVED")
    assert appr["rows"] == []

    data = export.weekend_report_xlsx(
        brand="Matrix Science Academy", title="Weekend Work", rows=pend["rows"], rules=pend["rules"],
    )
    assert data[:2] == b"PK"  # a real .xlsx


@pytest.mark.usefixtures("seed_data")
async def test_no_attendance_is_leave_and_sheet_layout(db_session, seed_data):
    """A pre-approved teacher who didn't work shows 'L' (Leave), and the export
    matches the client sheet: a weekday-headed day column + the dated title."""
    worked = await _staff(db_session, emp_code="92010")
    noshow = await _staff(db_session, emp_code="92011")
    sun = _next_sunday()
    await _attendance(db_session, worked, sun, status="PRESENT", minutes=360)
    # noshow: no StaffDailyAttendance row at all.
    await wws.preapprove(
        db_session, branch_id=BRANCH, staff_ids=[worked.id, noshow.id],
        work_date=sun, user_id=USER,
    )

    rep = await wws.report(db_session, branch_id=BRANCH, start=sun, end=sun)
    codes = {r["emp_code"]: r["day_code"] for r in rep["rows"]}
    assert codes["92010"] == "P"
    assert codes["92011"] == "L"   # pre-approved, didn't work → Leave

    data = export.weekend_report_xlsx(
        brand="MSA", title="Weekend Work", rows=rep["rows"], rules=rep["rules"],
    )
    wb = load_workbook(io.BytesIO(data))
    ws = wb.active
    assert "PRE APPROVED WORK STATUS" in str(ws["A1"].value)
    # Single-date report → the day column is headed by the weekday name.
    header_row = [ws.cell(row=2, column=c).value for c in range(1, 8)]
    assert header_row[0] == "Empcode" and header_row[1] == "Name"
    assert header_row[2] == "Sunday"
    assert "Work Approved Status" in header_row
    assert "Hours" not in header_row  # dropped to match the sheet
