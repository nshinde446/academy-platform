"""Weekend Plan (teacher-initiated) workflow — SRD §5.1.

Draft/submit/withdraw/resubmit, the weekend/holiday day-type rule (BR-02), total
planned hours (WP04), approver resolution + notification (WP05/AP07), one-plan-
per-date, decision-log history (WP09), and own-only access (BR-05)."""

import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from app.modules.auth.models.auth_models import User
from app.modules.lectures.models.lecture_models import Holiday
from app.modules.staff.models.staff_models import Department, Staff
from app.modules.teacher.models.teacher_models import WeekendWork
from app.modules.teacher_portal.models.workflow_models import (
    ApproverLog,
    ApproverMapping,
    PortalNotification,
)
from app.modules.teacher_portal.schemas.portal_schemas import (
    WeekendPlanItemIn,
    WeekendPlanWrite,
)
from app.modules.teacher_portal.services import weekend_plan_service as svc
from sqlalchemy import select

BRANCH = uuid.UUID("00000000-0000-0000-0000-000000000001")
USER = uuid.UUID("00000000-0000-0000-0000-000000000100")  # admin_user (approver)


def _next(weekday: int) -> date:
    d = date(2026, 12, 1)
    while d.weekday() != weekday:
        d += timedelta(days=1)
    return d


_SUN = _next(6)
_SAT = _next(5)
_MON = _next(0)


async def _staff(db, emp_code="93000") -> Staff:
    dept = Department(
        branch_id=BRANCH, name=f"WP-{emp_code}", id_range_start=93000, id_range_end=93999)
    db.add(dept)
    await db.flush()
    s = Staff(branch_id=BRANCH, emp_code=emp_code, first_name="Asha", last_name="M",
              department_id=dept.id)
    db.add(s)
    await db.flush()
    return s


def _item(start="09:00", end="11:00", wt="Lecture") -> WeekendPlanItemIn:
    return WeekendPlanItemIn(
        work_type=wt, batch_id=None, task_description="Revision", start_time=start, end_time=end)


def _write(plan_date=_SUN, items=None, approver_id=None, remarks=None) -> WeekendPlanWrite:
    return WeekendPlanWrite(
        plan_date=plan_date, approver_id=approver_id, remarks=remarks,
        items=items if items is not None else [_item()])


@pytest.mark.usefixtures("seed_data")
async def test_weekday_rejected(db_session, seed_data):
    s = await _staff(db_session)
    with pytest.raises(HTTPException) as ei:
        await svc.create_plan(db_session, staff_id=s.id, user_id=USER,
                              data=_write(plan_date=_MON), submit=False)
    assert ei.value.status_code == 400


@pytest.mark.usefixtures("seed_data")
async def test_create_draft_computes_total_minutes(db_session, seed_data):
    s = await _staff(db_session, "93001")
    out = await svc.create_plan(
        db_session, staff_id=s.id, user_id=USER,
        data=_write(items=[_item("09:00", "11:00"), _item("12:00", "12:30")]),
        submit=False)
    assert out["status"] == "DRAFT"
    assert out["total_planned_minutes"] == 150  # 120 + 30
    assert out["can_edit"] is True
    assert out["day_type"] == "SUNDAY"
    assert len(out["items"]) == 2


@pytest.mark.usefixtures("seed_data")
async def test_end_before_start_and_submit_without_items_rejected(db_session, seed_data):
    s = await _staff(db_session, "93002")
    with pytest.raises(HTTPException):
        await svc.create_plan(db_session, staff_id=s.id, user_id=USER,
                              data=_write(items=[_item("11:00", "09:00")]), submit=False)
    with pytest.raises(HTTPException) as ei:
        await svc.create_plan(db_session, staff_id=s.id, user_id=USER,
                              data=_write(items=[]), submit=True)
    assert ei.value.status_code == 400


@pytest.mark.usefixtures("seed_data")
async def test_submit_assigns_mapped_approver_logs_and_notifies(db_session, seed_data):
    s = await _staff(db_session, "93003")
    db_session.add(ApproverMapping(
        branch_id=BRANCH, staff_id=s.id, approver_user_id=USER, is_default=True))
    await db_session.flush()

    out = await svc.create_plan(db_session, staff_id=s.id, user_id=USER,
                                data=_write(), submit=True)
    assert out["status"] == "PENDING"
    assert out["approver_id"] == USER
    assert out["submitted_at"] is not None

    logs = (await db_session.execute(
        select(ApproverLog).where(ApproverLog.record_id == out["id"]))).scalars().all()
    assert [lg.action for lg in logs] == ["SUBMIT"]
    notes = (await db_session.execute(
        select(PortalNotification).where(PortalNotification.user_id == USER))).scalars().all()
    assert any(n.record_id == out["id"] for n in notes)


@pytest.mark.usefixtures("seed_data")
async def test_duplicate_date_conflict(db_session, seed_data):
    s = await _staff(db_session, "93004")
    await svc.create_plan(db_session, staff_id=s.id, user_id=USER, data=_write(), submit=False)
    with pytest.raises(HTTPException) as ei:
        await svc.create_plan(db_session, staff_id=s.id, user_id=USER, data=_write(), submit=False)
    assert ei.value.status_code == 409


@pytest.mark.usefixtures("seed_data")
async def test_withdraw_pending_back_to_draft(db_session, seed_data):
    s = await _staff(db_session, "93005")
    out = await svc.create_plan(db_session, staff_id=s.id, user_id=USER, data=_write(), submit=True)
    wd = await svc.withdraw_plan(db_session, staff_id=s.id, plan_id=out["id"], user_id=USER)
    assert wd["status"] == "DRAFT"
    assert wd["approver_id"] is None
    actions = [h["action"] for h in wd["history"]]
    assert actions == ["SUBMIT", "WITHDRAW"]


@pytest.mark.usefixtures("seed_data")
async def test_reject_then_edit_resubmit_keeps_history(db_session, seed_data):
    s = await _staff(db_session, "93006")
    out = await svc.create_plan(db_session, staff_id=s.id, user_id=USER, data=_write(), submit=True)
    # Simulate an approver rejection (approver side is Slice 3).
    plan = (await db_session.execute(
        select(WeekendWork).where(WeekendWork.id == out["id"]))).scalar_one()
    plan.approval_status = "REJECTED"
    plan.approval_note = "Please add the batch."
    await db_session.flush()

    edited = await svc.update_plan(
        db_session, staff_id=s.id, plan_id=out["id"], user_id=USER,
        data=_write(items=[_item("09:00", "10:00"), _item("10:00", "11:00")]), submit=True)
    assert edited["status"] == "PENDING"
    assert edited["total_planned_minutes"] == 120
    actions = [h["action"] for h in edited["history"]]
    assert actions == ["SUBMIT", "RESUBMIT"]  # earlier decision history preserved


@pytest.mark.usefixtures("seed_data")
async def test_holiday_is_eligible(db_session, seed_data):
    s = await _staff(db_session, "93007")
    db_session.add(Holiday(branch_id=BRANCH, holiday_date=_MON, name="Founders Day"))
    await db_session.flush()
    out = await svc.create_plan(db_session, staff_id=s.id, user_id=USER,
                                data=_write(plan_date=_MON), submit=False)
    assert out["day_type"] == "HOLIDAY"
    assert out["holiday_name"] == "Founders Day"


@pytest.mark.usefixtures("seed_data")
async def test_access_is_own_only(db_session, seed_data):
    a = await _staff(db_session, "93008")
    b = await _staff(db_session, "93009")
    out = await svc.create_plan(db_session, staff_id=a.id, user_id=USER, data=_write(), submit=False)
    with pytest.raises(HTTPException) as ei:
        await svc.get_plan(db_session, staff_id=b.id, plan_id=out["id"])
    assert ei.value.status_code == 404


@pytest.mark.usefixtures("seed_data")
async def test_plan_meta(db_session, seed_data):
    s = await _staff(db_session, "93010")
    db_session.add(Holiday(branch_id=BRANCH, holiday_date=_MON, name="Founders Day"))
    db_session.add(ApproverMapping(
        branch_id=BRANCH, staff_id=s.id, approver_user_id=USER, is_default=True))
    await db_session.flush()
    meta = await svc.plan_meta(db_session, staff_id=s.id, start=date(2026, 12, 1), end=date(2026, 12, 31))
    assert any(h["name"] == "Founders Day" for h in meta["holidays"])
    assert "Lecture" in meta["work_types"]
    assert meta["default_approver"]["id"] == USER
