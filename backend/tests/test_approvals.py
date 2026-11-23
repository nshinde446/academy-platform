"""Approver inbox + decision engine — SRD §5.3.

Approve/Reject/Mark-ABSENT with a mandatory comment (AP03/AP04), self-approval
block (BR-07/AP09), decision finality + reject-only resubmit (AP08), teacher
notification (AP07), and the filterable inbox (AP01)."""

import uuid
from datetime import date, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.modules.auth.models.auth_models import User
from app.modules.auth.services.auth_service import hash_password
from app.modules.staff.models.staff_models import Department, Staff
from app.modules.teacher_portal.models.workflow_models import (
    ApproverLog,
    PortalNotification,
)
from app.modules.teacher_portal.schemas.portal_schemas import (
    WeekendPlanItemIn,
    WeekendPlanWrite,
)
from app.modules.teacher_portal.services import approvals_service as appr
from app.modules.teacher_portal.services import weekend_plan_service as svc
from app.modules.teacher_portal.services import workflow_common as wf

BRANCH = uuid.UUID("00000000-0000-0000-0000-000000000001")
APPROVER = uuid.UUID("00000000-0000-0000-0000-000000000100")  # admin_user (staff_id None)


def _next_sunday() -> date:
    d = date(2026, 12, 1)
    while d.weekday() != 6:
        d += timedelta(days=1)
    return d


_SUN = _next_sunday()


async def _teacher(db, emp_code="94000"):
    dept = Department(branch_id=BRANCH, name=f"AP-{emp_code}",
                      id_range_start=94000, id_range_end=94999)
    db.add(dept)
    await db.flush()
    s = Staff(branch_id=BRANCH, emp_code=emp_code, first_name="Nita", last_name="R",
              department_id=dept.id)
    db.add(s)
    await db.flush()
    # A login account linked to the staff, so decision notifications have a target.
    u = User(email=f"{emp_code}@t.com", password_hash=hash_password("x"),
             first_name="Nita", last_name="R", username=emp_code, staff_id=s.id,
             primary_branch_id=BRANCH)
    db.add(u)
    await db.flush()
    return s, u


async def _pending_plan(db, staff):
    data = WeekendPlanWrite(plan_date=_SUN, items=[
        WeekendPlanItemIn(work_type="Lecture", task_description="Revision",
                          start_time="09:00", end_time="11:00")])
    return await svc.create_plan(db, staff_id=staff.id, user_id=APPROVER, data=data, submit=True)


@pytest.mark.usefixtures("seed_data")
async def test_approve_sets_status_logs_and_notifies(db_session, seed_data):
    s, u = await _teacher(db_session)
    plan = await _pending_plan(db_session, s)
    out = await appr.decide(
        db_session, branch_id=BRANCH, record_type=wf.RECORD_WEEKEND_PLAN,
        record_id=plan["id"], approver_user_id=APPROVER, action="APPROVE",
        comment="Looks good, approved for Sunday.")
    assert out["status"] == "APPROVED"
    assert out["latest_approver_comment"].startswith("Looks good")
    logs = (await db_session.execute(
        select(ApproverLog).where(ApproverLog.record_id == plan["id"]))).scalars().all()
    assert [lg.action for lg in logs] == ["SUBMIT", "APPROVE"]
    # Teacher's own account gets the in-app notification.
    notes = (await db_session.execute(
        select(PortalNotification).where(PortalNotification.user_id == u.id))).scalars().all()
    assert any("approved" in n.message for n in notes)


@pytest.mark.usefixtures("seed_data")
async def test_comment_minimum_enforced(db_session, seed_data):
    s, _ = await _teacher(db_session, "94001")
    plan = await _pending_plan(db_session, s)
    with pytest.raises(HTTPException) as ei:
        await appr.decide(db_session, branch_id=BRANCH, record_type=wf.RECORD_WEEKEND_PLAN,
                          record_id=plan["id"], approver_user_id=APPROVER,
                          action="APPROVE", comment="too short")
    assert ei.value.status_code == 400


@pytest.mark.usefixtures("seed_data")
async def test_decision_is_final(db_session, seed_data):
    s, _ = await _teacher(db_session, "94002")
    plan = await _pending_plan(db_session, s)
    await appr.decide(db_session, branch_id=BRANCH, record_type=wf.RECORD_WEEKEND_PLAN,
                      record_id=plan["id"], approver_user_id=APPROVER,
                      action="APPROVE", comment="Approved for the weekend.")
    with pytest.raises(HTTPException) as ei:
        await appr.decide(db_session, branch_id=BRANCH, record_type=wf.RECORD_WEEKEND_PLAN,
                          record_id=plan["id"], approver_user_id=APPROVER,
                          action="REJECT", comment="Changed my mind here.")
    assert ei.value.status_code == 409


@pytest.mark.usefixtures("seed_data")
async def test_reject_then_teacher_can_resubmit(db_session, seed_data):
    s, _ = await _teacher(db_session, "94003")
    plan = await _pending_plan(db_session, s)
    await appr.decide(db_session, branch_id=BRANCH, record_type=wf.RECORD_WEEKEND_PLAN,
                      record_id=plan["id"], approver_user_id=APPROVER,
                      action="REJECT", comment="Please add the batch name.")
    again = await svc.submit_plan(db_session, staff_id=s.id, plan_id=plan["id"], user_id=APPROVER)
    assert again["status"] == "PENDING"
    actions = [h["action"] for h in again["history"]]
    assert actions == ["SUBMIT", "REJECT", "RESUBMIT"]


@pytest.mark.usefixtures("seed_data")
async def test_mark_absent(db_session, seed_data):
    s, _ = await _teacher(db_session, "94004")
    plan = await _pending_plan(db_session, s)
    out = await appr.decide(db_session, branch_id=BRANCH, record_type=wf.RECORD_WEEKEND_PLAN,
                            record_id=plan["id"], approver_user_id=APPROVER,
                            action="MARK_ABSENT", comment="No biometric punch on the day.")
    assert out["status"] == "ABSENT"


@pytest.mark.usefixtures("seed_data")
async def test_cannot_approve_own_submission(db_session, seed_data):
    # An approver who is also the submitting teacher (their user.staff_id matches).
    s, u = await _teacher(db_session, "94005")
    plan = await _pending_plan(db_session, s)
    with pytest.raises(HTTPException) as ei:
        await appr.decide(db_session, branch_id=BRANCH, record_type=wf.RECORD_WEEKEND_PLAN,
                          record_id=plan["id"], approver_user_id=u.id,
                          action="APPROVE", comment="Approving my own plan here.")
    assert ei.value.status_code == 403


@pytest.mark.usefixtures("seed_data")
async def test_inbox_lists_pending_and_filters(db_session, seed_data):
    s1, _ = await _teacher(db_session, "94006")
    s2, _ = await _teacher(db_session, "94007")
    await _pending_plan(db_session, s1)
    await _pending_plan(db_session, s2)
    allp = await appr.inbox(db_session, branch_id=BRANCH, record_type=wf.RECORD_WEEKEND_PLAN)
    assert len({r["record_id"] for r in allp}) >= 2
    only1 = await appr.inbox(db_session, branch_id=BRANCH, teacher_staff_id=s1.id)
    assert all(r["teacher_staff_id"] == s1.id for r in only1)


@pytest.mark.usefixtures("seed_data")
async def test_detail_has_items_and_history(db_session, seed_data):
    s, _ = await _teacher(db_session, "94008")
    plan = await _pending_plan(db_session, s)
    d = await appr.detail(db_session, branch_id=BRANCH,
                          record_type=wf.RECORD_WEEKEND_PLAN, record_id=plan["id"])
    assert d["items"][0]["work_type"] == "Lecture"
    assert d["history"][0]["action"] == "SUBMIT"
    assert d["emp_code"] == "94008"
