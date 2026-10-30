"""Teacher Portal — Changes 2/3/4 + WOF: leave types, balance, date rules, WOF.

Balance per type = Quota − Used(approved) − Pending (LWP unlimited). WOF balance
= seeded opening + Σ(present − 24) over whole elapsed months. Cancel keeps the
record (status 'cancelled'), not deleted.
"""

import uuid
from datetime import date, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.attendance.models.attendance_models import StaffDailyAttendance
from app.modules.teacher.models.teacher_models import (
    LeaveTypeQuota,
    Teacher,
    TeacherLeave,
    TeacherWofOpening,
)
from app.modules.teacher_portal.services import leave_service, wof_service
from app.modules.staff.models.staff_models import Department, Staff

BRANCH = uuid.UUID("00000000-0000-0000-0000-000000000001")
USER = uuid.UUID("00000000-0000-0000-0000-000000000100")


async def _teacher_staff(db: AsyncSession) -> Staff:
    t = Teacher(branch_id=BRANCH, first_name="Asha", last_name="Rao")
    db.add(t)
    await db.flush()
    dept = Department(branch_id=BRANCH, name="MSA-Teachers", id_range_start=91000, id_range_end=91999)
    db.add(dept)
    await db.flush()
    s = Staff(branch_id=BRANCH, emp_code="91000", first_name="Asha", last_name="Rao",
              department_id=dept.id, linked_teacher_id=t.id, weekly_off_days="6")
    db.add(s)
    await db.flush()
    return s


# ── leave balance ────────────────────────────────────────────────────────────

async def test_leave_balance_quota_used_pending(db_session: AsyncSession, seed_data):
    s = await _teacher_staff(db_session)
    yr = date.today().year
    db_session.add(LeaveTypeQuota(branch_id=BRANCH, year=yr, leave_type="casual", quota_days=12))
    await db_session.flush()
    t_id = s.linked_teacher_id
    # 2-day approved casual (Mon-Tue) + 1-day pending casual, this year.
    db_session.add(TeacherLeave(
        teacher_id=t_id, branch_id=BRANCH, start_date=date(yr, 1, 5), end_date=date(yr, 1, 6),
        leave_type="casual", approval_status="approved",
    ))
    db_session.add(TeacherLeave(
        teacher_id=t_id, branch_id=BRANCH, start_date=date(yr, 1, 8), end_date=date(yr, 1, 8),
        leave_type="casual", approval_status="pending",
    ))
    await db_session.flush()

    bal = await leave_service.balance(db_session, s.id, yr)
    casual = next(x for x in bal["types"] if x["leave_type"] == "casual")
    assert casual["quota"] == 12
    assert casual["used"] == 2
    assert casual["pending"] == 1
    assert casual["available"] == 9
    lwp = next(x for x in bal["types"] if x["leave_type"] == "lwp")
    assert lwp["quota"] is None and lwp["available"] is None


async def test_half_day_counts_half(db_session: AsyncSession, seed_data):
    s = await _teacher_staff(db_session)
    yr = date.today().year
    db_session.add(LeaveTypeQuota(branch_id=BRANCH, year=yr, leave_type="sick", quota_days=8))
    db_session.add(TeacherLeave(
        teacher_id=s.linked_teacher_id, branch_id=BRANCH,
        start_date=date(yr, 2, 3), end_date=date(yr, 2, 3),
        leave_type="sick", half_day=True, approval_status="approved",
    ))
    await db_session.flush()
    bal = await leave_service.balance(db_session, s.id, yr)
    sick = next(x for x in bal["types"] if x["leave_type"] == "sick")
    assert sick["used"] == 0.5 and sick["available"] == 7.5


# ── apply rules ──────────────────────────────────────────────────────────────

async def test_apply_backdate_limit(db_session: AsyncSession, seed_data):
    from fastapi import HTTPException
    s = await _teacher_staff(db_session)
    old = date.today() - timedelta(days=30)
    with pytest.raises(HTTPException) as e:
        await leave_service.apply_leave(
            db_session, staff_id=s.id, user_id=USER, leave_type="casual",
            start_date=old, end_date=old, half_day=False, reason=None,
        )
    assert e.value.status_code == 422


async def test_apply_within_backdate_ok(db_session: AsyncSession, seed_data):
    s = await _teacher_staff(db_session)
    db_session.add(LeaveTypeQuota(branch_id=BRANCH, year=date.today().year, leave_type="casual", quota_days=12))
    await db_session.flush()
    # 3 days back is within the 7-day window; pick a non-Sunday.
    d = date.today() - timedelta(days=3)
    if d.weekday() == 6:
        d -= timedelta(days=1)
    row = await leave_service.apply_leave(
        db_session, staff_id=s.id, user_id=USER, leave_type="casual",
        start_date=d, end_date=d, half_day=False, reason="personal",
    )
    assert row["status"] == "pending" and row["leave_type"] == "casual"


async def test_apply_blocks_when_quota_exceeded(db_session: AsyncSession, seed_data):
    from fastapi import HTTPException
    s = await _teacher_staff(db_session)
    db_session.add(LeaveTypeQuota(branch_id=BRANCH, year=date.today().year, leave_type="paid", quota_days=1))
    await db_session.flush()
    start = date.today() + timedelta(days=2)
    end = start + timedelta(days=4)  # several working days > 1 quota
    with pytest.raises(HTTPException) as e:
        await leave_service.apply_leave(
            db_session, staff_id=s.id, user_id=USER, leave_type="paid",
            start_date=start, end_date=end, half_day=False, reason=None,
        )
    assert e.value.status_code == 422
    assert "Without Pay" in e.value.detail


async def test_cancel_keeps_record_as_cancelled(db_session: AsyncSession, seed_data):
    s = await _teacher_staff(db_session)
    db_session.add(LeaveTypeQuota(branch_id=BRANCH, year=date.today().year, leave_type="casual", quota_days=12))
    await db_session.flush()
    start = date.today() + timedelta(days=3)
    row = await leave_service.apply_leave(
        db_session, staff_id=s.id, user_id=USER, leave_type="casual",
        start_date=start, end_date=start, half_day=False, reason=None,
    )
    await leave_service.cancel_leave(db_session, staff_id=s.id, leave_id=row["id"], user_id=USER)
    lv = (await db_session.execute(
        select(TeacherLeave).where(TeacherLeave.id == row["id"])
    )).scalar_one()
    assert lv.approval_status == "cancelled"
    assert lv.is_deleted is False  # kept in history


# ── WOF accrual ──────────────────────────────────────────────────────────────

async def test_wof_balance_accrues_extra_days(db_session: AsyncSession, seed_data):
    s = await _teacher_staff(db_session)
    # Opening 9.0 as of 2026-08-26; September 2026 present = 28 → +4 over 24.
    # (September is a fully-elapsed month; the running month is never accrued.)
    db_session.add(TeacherWofOpening(
        teacher_id=s.linked_teacher_id, branch_id=BRANCH,
        opening_balance=9, as_of_date=date(2026, 8, 26),
    ))
    for d in range(1, 29):
        db_session.add(StaffDailyAttendance(
            branch_id=BRANCH, staff_id=s.id, attendance_date=date(2026, 9, d),
            day_status="PRESENT", signoff="COMPLETE", source="BIOMETRIC",
        ))
    await db_session.flush()

    bal = await wof_service.balance(db_session, s)
    assert bal is not None
    assert bal["opening"] == 9
    assert bal["accrued"] == 4  # Sept: 28 present − 24
    assert bal["balance"] == 13


async def test_wof_none_when_not_seeded(db_session: AsyncSession, seed_data):
    s = await _teacher_staff(db_session)
    assert await wof_service.balance(db_session, s) is None
