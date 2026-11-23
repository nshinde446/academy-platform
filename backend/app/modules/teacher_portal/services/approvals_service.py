"""Approver inbox + decision engine (Weekend & Star-System SRD §5.3).

One engine serves both record types — teacher-initiated Weekend Plans and
daily Self-Assessments — because they share the lifecycle, the mandatory-comment
rule, the permanent log and the teacher notification. The approver:

  - sees a filterable inbox of PENDING submissions (AP01),
  - opens one in read-only detail with its history (AP02),
  - Approves / Rejects / Marks ABSENT, always with a comment ≥10 chars (AP03/AP04),
  - cannot act on their own submission (AP09/BR-07),
  - and the decision is final; only REJECT allows resubmission (AP08).

Everything is scoped to the approver's branch.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models.auth_models import User
from app.modules.staff.models.staff_models import Staff
from app.modules.teacher.models.teacher_models import WeekendPlanItem, WeekendWork
from app.modules.teacher_portal.models.workflow_models import (
    AssessmentCategory,
    AssessmentItemMaster,
    SelfAssessment,
    SelfAssessmentItem,
    SelfAssessmentStar,
)
from app.modules.teacher_portal.services import workflow_common as wf

_ACTION_TO_STATUS = {"APPROVE": "APPROVED", "REJECT": "REJECTED", "MARK_ABSENT": "ABSENT"}


async def _teacher_display(
    session: AsyncSession, staff_ids: list[uuid.UUID]
) -> dict[uuid.UUID, dict]:
    if not staff_ids:
        return {}
    rows = (await session.execute(
        select(Staff).where(Staff.id.in_(staff_ids))
    )).scalars().all()
    return {
        s.id: {"name": f"{s.first_name} {s.last_name}".strip(), "emp_code": s.emp_code}
        for s in rows
    }


async def _user_for_staff(
    session: AsyncSession, staff_id: uuid.UUID
) -> uuid.UUID | None:
    """The login account tied to a teacher's staff record, for notifications."""
    return (await session.execute(
        select(User.id).where(User.staff_id == staff_id, User.is_deleted == False)  # noqa: E712
    )).scalar_one_or_none()


async def inbox(
    session: AsyncSession,
    *,
    branch_id: uuid.UUID,
    record_type: str | None = None,
    teacher_staff_id: uuid.UUID | None = None,
    start: date | None = None,
    end: date | None = None,
    status_filter: str = "PENDING",
) -> list[dict]:
    """Filterable list of submissions (AP01). Defaults to PENDING across both
    types; pass ``record_type`` / ``teacher_staff_id`` / date range to narrow."""
    out: list[dict] = []

    if record_type in (None, wf.RECORD_WEEKEND_PLAN):
        q = select(WeekendWork).where(
            WeekendWork.branch_id == branch_id,
            WeekendWork.origin == "TEACHER_PLAN",
            WeekendWork.approval_status == status_filter,
            WeekendWork.is_deleted == False,  # noqa: E712
        )
        if teacher_staff_id:
            q = q.where(WeekendWork.staff_id == teacher_staff_id)
        if start:
            q = q.where(WeekendWork.work_date >= start)
        if end:
            q = q.where(WeekendWork.work_date <= end)
        plans = list((await session.execute(q)).scalars().all())
        names = await _teacher_display(session, [p.staff_id for p in plans])
        for p in plans:
            info = names.get(p.staff_id, {})
            out.append({
                "record_type": wf.RECORD_WEEKEND_PLAN,
                "record_id": p.id,
                "teacher_staff_id": p.staff_id,
                "teacher_name": info.get("name"),
                "emp_code": info.get("emp_code"),
                "date": p.work_date,
                "status": p.approval_status,
                "submitted_at": p.submitted_at,
                "summary": f"{p.total_planned_minutes} min planned",
            })

    if record_type in (None, wf.RECORD_SELF_ASSESSMENT):
        q = select(SelfAssessment).where(
            SelfAssessment.branch_id == branch_id,
            SelfAssessment.status_code == status_filter,
            SelfAssessment.is_deleted == False,  # noqa: E712
        )
        if teacher_staff_id:
            q = q.where(SelfAssessment.staff_id == teacher_staff_id)
        if start:
            q = q.where(SelfAssessment.assess_date >= start)
        if end:
            q = q.where(SelfAssessment.assess_date <= end)
        assessments = list((await session.execute(q)).scalars().all())
        names = await _teacher_display(session, [a.staff_id for a in assessments])
        for a in assessments:
            info = names.get(a.staff_id, {})
            out.append({
                "record_type": wf.RECORD_SELF_ASSESSMENT,
                "record_id": a.id,
                "teacher_staff_id": a.staff_id,
                "teacher_name": info.get("name"),
                "emp_code": info.get("emp_code"),
                "date": a.assess_date,
                "status": a.status_code,
                "submitted_at": a.submitted_at,
                "summary": f"{float(a.final_total_star):g} / 20 stars",
            })

    out.sort(key=lambda r: (r["submitted_at"] or datetime.min.replace(tzinfo=timezone.utc)))
    return out


async def _weekend_plan_detail(
    session: AsyncSession, *, branch_id: uuid.UUID, record_id: uuid.UUID
) -> dict:
    plan = (await session.execute(
        select(WeekendWork).where(
            WeekendWork.id == record_id,
            WeekendWork.branch_id == branch_id,
            WeekendWork.origin == "TEACHER_PLAN",
            WeekendWork.is_deleted == False,  # noqa: E712
        )
    )).scalar_one_or_none()
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found.")
    items = list((await session.execute(
        select(WeekendPlanItem).where(
            WeekendPlanItem.weekend_work_id == plan.id,
            WeekendPlanItem.is_deleted == False,  # noqa: E712
        ).order_by(WeekendPlanItem.sort_order.asc())
    )).scalars().all())
    from app.modules.batch.models.batch_models import Batch
    batch_ids = [it.batch_id for it in items if it.batch_id]
    batch_names = {
        b.id: b.name
        for b in (await session.execute(
            select(Batch).where(Batch.id.in_(batch_ids))
        )).scalars().all()
    } if batch_ids else {}
    info = (await _teacher_display(session, [plan.staff_id])).get(plan.staff_id, {})
    return {
        "record_type": wf.RECORD_WEEKEND_PLAN,
        "record_id": plan.id,
        "teacher_staff_id": plan.staff_id,
        "teacher_name": info.get("name"),
        "emp_code": info.get("emp_code"),
        "date": plan.work_date,
        "day_type": plan.day_type,
        "holiday_name": plan.holiday_name,
        "status": plan.approval_status,
        "total_planned_minutes": plan.total_planned_minutes,
        "remarks": plan.remarks,
        "submitted_at": plan.submitted_at,
        "latest_approver_comment": plan.approval_note,
        "items": [
            {
                "work_type": it.work_type, "batch_id": it.batch_id,
                "batch_name": batch_names.get(it.batch_id),
                "task_description": it.task_description,
                "start_time": it.start_time, "end_time": it.end_time,
            }
            for it in items
        ],
        "history": await wf.history_for(
            session, record_type=wf.RECORD_WEEKEND_PLAN, record_id=plan.id),
    }


async def _self_assessment_detail(
    session: AsyncSession, *, branch_id: uuid.UUID, record_id: uuid.UUID
) -> dict:
    a = (await session.execute(
        select(SelfAssessment).where(
            SelfAssessment.id == record_id,
            SelfAssessment.branch_id == branch_id,
            SelfAssessment.is_deleted == False,  # noqa: E712
        )
    )).scalar_one_or_none()
    if a is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found.")
    items = list((await session.execute(
        select(SelfAssessmentItem).where(
            SelfAssessmentItem.self_assessment_id == a.id,
            SelfAssessmentItem.is_deleted == False,  # noqa: E712
        )
    )).scalars().all())
    stars = list((await session.execute(
        select(SelfAssessmentStar).where(
            SelfAssessmentStar.self_assessment_id == a.id,
            SelfAssessmentStar.is_deleted == False,  # noqa: E712
        )
    )).scalars().all())
    # Resolve item + category names so the approver sees a readable form.
    item_names = {
        it.id: (it.item_name, it.category_id)
        for it in (await session.execute(
            select(AssessmentItemMaster).where(AssessmentItemMaster.branch_id == branch_id)
        )).scalars().all()
    }
    cat_names = {
        c.id: c.name
        for c in (await session.execute(
            select(AssessmentCategory).where(AssessmentCategory.branch_id == branch_id)
        )).scalars().all()
    }
    info = (await _teacher_display(session, [a.staff_id])).get(a.staff_id, {})
    return {
        "record_type": wf.RECORD_SELF_ASSESSMENT,
        "record_id": a.id,
        "teacher_staff_id": a.staff_id,
        "teacher_name": info.get("name"),
        "emp_code": info.get("emp_code"),
        "date": a.assess_date,
        "status": a.status_code,
        "final_total_star": float(a.final_total_star),
        "miscellaneous_text": a.miscellaneous_text,
        "submitted_at": a.submitted_at,
        "latest_approver_comment": a.latest_approver_comment,
        "items": [
            {
                "item_master_id": i.item_master_id,
                "item_name": item_names.get(i.item_master_id, ("?", None))[0],
                "category_name": cat_names.get(item_names.get(i.item_master_id, ("?", None))[1]),
                "selected_value": i.selected_value,
            }
            for i in items
        ],
        "stars": [
            {"category_id": s.category_id, "category_name": cat_names.get(s.category_id),
             "stars": s.stars}
            for s in stars
        ],
        "history": await wf.history_for(
            session, record_type=wf.RECORD_SELF_ASSESSMENT, record_id=a.id),
    }


async def detail(
    session: AsyncSession, *, branch_id: uuid.UUID, record_type: str, record_id: uuid.UUID
) -> dict:
    """Read-only full view of a submission with its decision history (AP02)."""
    if record_type == wf.RECORD_WEEKEND_PLAN:
        return await _weekend_plan_detail(session, branch_id=branch_id, record_id=record_id)
    if record_type == wf.RECORD_SELF_ASSESSMENT:
        return await _self_assessment_detail(session, branch_id=branch_id, record_id=record_id)
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown record type.")


async def decide(
    session: AsyncSession,
    *,
    branch_id: uuid.UUID,
    record_type: str,
    record_id: uuid.UUID,
    approver_user_id: uuid.UUID,
    action: str,
    comment: str,
) -> dict:
    """Approve / Reject / Mark ABSENT with a mandatory comment (AP03–AP09)."""
    if action not in _ACTION_TO_STATUS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="action must be APPROVE, REJECT or MARK_ABSENT.",
        )
    comment = (comment or "").strip()
    if len(comment) < wf.MIN_COMMENT_LEN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"A comment of at least {wf.MIN_COMMENT_LEN} characters is required.",
        )
    new_status = _ACTION_TO_STATUS[action]
    now = datetime.now(timezone.utc)

    # The approver's own staff link, to block self-approval (BR-07/AP09).
    approver_staff_id = (await session.execute(
        select(User.staff_id).where(User.id == approver_user_id)
    )).scalar_one_or_none()

    if record_type == wf.RECORD_WEEKEND_PLAN:
        rec = (await session.execute(
            select(WeekendWork).where(
                WeekendWork.id == record_id,
                WeekendWork.branch_id == branch_id,
                WeekendWork.origin == "TEACHER_PLAN",
                WeekendWork.is_deleted == False,  # noqa: E712
            )
        )).scalar_one_or_none()
        if rec is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found.")
        current, rec_staff = rec.approval_status, rec.staff_id
    elif record_type == wf.RECORD_SELF_ASSESSMENT:
        rec = (await session.execute(
            select(SelfAssessment).where(
                SelfAssessment.id == record_id,
                SelfAssessment.branch_id == branch_id,
                SelfAssessment.is_deleted == False,  # noqa: E712
            )
        )).scalar_one_or_none()
        if rec is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found.")
        current, rec_staff = rec.status_code, rec.staff_id
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown record type.")

    if approver_staff_id is not None and approver_staff_id == rec_staff:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot act on your own submission.",
        )
    if current != "PENDING":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"This submission is already {current} and can't be changed.",
        )

    # Apply the decision.
    if record_type == wf.RECORD_WEEKEND_PLAN:
        rec.approval_status = new_status
        rec.approved_by = approver_user_id
        rec.approved_at = now
        rec.approval_note = comment
    else:
        rec.status_code = new_status
        rec.approved_by = approver_user_id
        rec.approved_at = now
        rec.latest_approver_comment = comment
    rec.updated_by = approver_user_id
    await session.flush()

    await wf.log_action(
        session, branch_id=branch_id, record_type=record_type, record_id=record_id,
        actor_user_id=approver_user_id, action=action, comment=comment)

    teacher_user_id = await _user_for_staff(session, rec_staff)
    verb = {"APPROVED": "approved", "REJECTED": "rejected", "ABSENT": "marked absent"}[new_status]
    label = "weekend plan" if record_type == wf.RECORD_WEEKEND_PLAN else "self-assessment"
    await wf.notify(
        session, branch_id=branch_id, user_id=teacher_user_id,
        record_type=record_type, record_id=record_id,
        message=f"Your {label} was {verb}: {comment}",
        actor_user_id=approver_user_id)

    return await detail(session, branch_id=branch_id, record_type=record_type, record_id=record_id)
