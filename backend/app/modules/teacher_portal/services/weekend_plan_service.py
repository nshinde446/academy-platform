"""Teacher-initiated Weekend Plan workflow (Weekend & Star-System SRD §5.1).

The teacher picks a Saturday/Sunday/holiday, adds work-breakdown lines, optionally
chooses an approver, and submits for approval. The plan reuses the reconciled
``weekend_work`` table (``origin=TEACHER_PLAN``) with its lines in
``weekend_plan_items``. Approver decisions live in Slice 3 (the approver inbox).

Lifecycle: DRAFT -> PENDING -> (approver) APPROVED | REJECTED | ABSENT. A REJECTED
plan is editable and resubmittable; a PENDING plan can be withdrawn to DRAFT
before the approver acts. All reads/writes are scoped to the teacher's own
``staff_id`` from the session (BR-05), enforced here, not only in the UI.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.attendance.time_utils import normalize_hhmm, parse_hhmm
from app.modules.teacher.models.teacher_models import WeekendPlanItem, WeekendWork
from app.modules.teacher_portal.schemas.portal_schemas import (
    WeekendPlanItemIn,
    WeekendPlanWrite,
)
from app.modules.teacher_portal.services import workflow_common as wf

_EDITABLE = ("DRAFT", "REJECTED")


def _minutes(start: str, end: str) -> int:
    s, e = parse_hhmm(start), parse_hhmm(end)
    if s is None or e is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid time: {start!r}–{end!r}.",
        )
    total = (e[0] * 60 + e[1]) - (s[0] * 60 + s[1])
    if total <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="End time must be after start time.",
        )
    return total


def _validate_items(items: list[WeekendPlanItemIn]) -> int:
    """Validate the lines and return the total planned minutes (WP04)."""
    total = 0
    for it in items:
        total += _minutes(it.start_time, it.end_time)
    return total


async def _serialize(
    session: AsyncSession, plan: WeekendWork, *, with_history: bool = True
) -> dict:
    items = list((await session.execute(
        select(WeekendPlanItem).where(
            WeekendPlanItem.weekend_work_id == plan.id,
            WeekendPlanItem.is_deleted == False,  # noqa: E712
        ).order_by(WeekendPlanItem.sort_order.asc())
    )).scalars().all())
    out = {
        "id": plan.id,
        "plan_date": plan.work_date,
        "day_type": plan.day_type,
        "holiday_name": plan.holiday_name,
        "status": plan.approval_status,
        "approver_id": plan.approver_id,
        "total_planned_minutes": plan.total_planned_minutes,
        "remarks": plan.remarks,
        "submitted_at": plan.submitted_at,
        "latest_approver_comment": plan.approval_note,
        "can_edit": plan.approval_status in _EDITABLE,
        "items": [
            {
                "id": it.id,
                "work_type": it.work_type,
                "batch_id": it.batch_id,
                "task_description": it.task_description,
                "start_time": it.start_time,
                "end_time": it.end_time,
                "sort_order": it.sort_order,
            }
            for it in items
        ],
    }
    if with_history:
        out["history"] = await wf.history_for(
            session, record_type=wf.RECORD_WEEKEND_PLAN, record_id=plan.id)
    return out


async def _get_own(
    session: AsyncSession, *, staff_id: uuid.UUID, plan_id: uuid.UUID
) -> WeekendWork:
    plan = (await session.execute(
        select(WeekendWork).where(
            WeekendWork.id == plan_id,
            WeekendWork.staff_id == staff_id,
            WeekendWork.origin == "TEACHER_PLAN",
            WeekendWork.is_deleted == False,  # noqa: E712
        )
    )).scalar_one_or_none()
    if plan is None:
        # 404 (not 403) so a probe can't distinguish "not yours" from "absent".
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found.")
    return plan


async def _replace_items(
    session: AsyncSession,
    *,
    plan: WeekendWork,
    branch_id: uuid.UUID,
    items: list[WeekendPlanItemIn],
    user_id: uuid.UUID,
) -> None:
    """Soft-delete existing lines and insert the new set."""
    existing = list((await session.execute(
        select(WeekendPlanItem).where(
            WeekendPlanItem.weekend_work_id == plan.id,
            WeekendPlanItem.is_deleted == False,  # noqa: E712
        )
    )).scalars().all())
    for row in existing:
        row.is_deleted = True
        row.updated_by = user_id
    for i, it in enumerate(items):
        session.add(WeekendPlanItem(
            branch_id=branch_id,
            weekend_work_id=plan.id,
            work_type=it.work_type,
            batch_id=it.batch_id,
            task_description=it.task_description,
            start_time=normalize_hhmm(it.start_time) or it.start_time,
            end_time=normalize_hhmm(it.end_time) or it.end_time,
            sort_order=i,
            created_by=user_id,
        ))
    await session.flush()


async def create_plan(
    session: AsyncSession,
    *,
    staff_id: uuid.UUID,
    user_id: uuid.UUID,
    data: WeekendPlanWrite,
    submit: bool,
    ip: str | None = None,
) -> dict:
    """Create a new plan as DRAFT, or submit it straight away. One live plan per
    teacher per date (the partial unique index enforces it; we pre-check for a
    friendly error)."""
    branch_id = await wf.resolve_branch_id(session, staff_id)
    day_type, holiday_name = await wf.resolve_day_type(
        session, branch_id=branch_id, plan_date=data.plan_date)

    dup = (await session.execute(
        select(WeekendWork).where(
            WeekendWork.branch_id == branch_id,
            WeekendWork.staff_id == staff_id,
            WeekendWork.work_date == data.plan_date,
            WeekendWork.is_deleted == False,  # noqa: E712
        )
    )).scalar_one_or_none()
    if dup is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You already have a weekend entry for this date.",
        )

    total = _validate_items(data.items)
    if submit and not data.items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Add at least one work line before submitting.",
        )

    plan = WeekendWork(
        branch_id=branch_id,
        staff_id=staff_id,
        work_date=data.plan_date,
        origin="TEACHER_PLAN",
        day_type=day_type,
        holiday_name=holiday_name,
        remarks=(data.remarks or None),
        total_planned_minutes=total,
        approval_status="DRAFT",
        created_by=user_id,
    )
    session.add(plan)
    await session.flush()
    await _replace_items(
        session, plan=plan, branch_id=branch_id, items=data.items, user_id=user_id)

    if submit:
        await _do_submit(session, plan=plan, branch_id=branch_id,
                         chosen_approver_id=data.approver_id, user_id=user_id)
    return await _serialize(session, plan)


async def update_plan(
    session: AsyncSession,
    *,
    staff_id: uuid.UUID,
    plan_id: uuid.UUID,
    user_id: uuid.UUID,
    data: WeekendPlanWrite,
    submit: bool,
) -> dict:
    """Edit a DRAFT or REJECTED plan (WP09). Optionally resubmit in the same call."""
    plan = await _get_own(session, staff_id=staff_id, plan_id=plan_id)
    if plan.approval_status not in _EDITABLE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"A {plan.approval_status} plan can't be edited.",
        )
    branch_id = plan.branch_id
    # The date itself can change (still must be a valid weekend/holiday).
    if data.plan_date != plan.work_date:
        day_type, holiday_name = await wf.resolve_day_type(
            session, branch_id=branch_id, plan_date=data.plan_date)
        plan.work_date = data.plan_date
        plan.day_type = day_type
        plan.holiday_name = holiday_name

    total = _validate_items(data.items)
    if submit and not data.items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Add at least one work line before submitting.",
        )
    plan.remarks = (data.remarks or None)
    plan.total_planned_minutes = total
    plan.updated_by = user_id
    await _replace_items(
        session, plan=plan, branch_id=branch_id, items=data.items, user_id=user_id)

    if submit:
        resubmit = plan.approval_status == "REJECTED"
        await _do_submit(session, plan=plan, branch_id=branch_id,
                         chosen_approver_id=data.approver_id, user_id=user_id,
                         resubmit=resubmit)
    await session.flush()
    return await _serialize(session, plan)


async def _do_submit(
    session: AsyncSession,
    *,
    plan: WeekendWork,
    branch_id: uuid.UUID,
    chosen_approver_id: uuid.UUID | None,
    user_id: uuid.UUID,
    resubmit: bool = False,
) -> None:
    approver_id = await wf.resolve_approver(
        session, staff_id=plan.staff_id, branch_id=branch_id,
        chosen_approver_id=chosen_approver_id)
    plan.approver_id = approver_id
    plan.approval_status = "PENDING"
    plan.submitted_at = datetime.now(timezone.utc)
    plan.updated_by = user_id
    await session.flush()
    await wf.log_action(
        session, branch_id=branch_id, record_type=wf.RECORD_WEEKEND_PLAN,
        record_id=plan.id, actor_user_id=user_id,
        action="RESUBMIT" if resubmit else "SUBMIT")
    await wf.notify(
        session, branch_id=branch_id, user_id=approver_id,
        record_type=wf.RECORD_WEEKEND_PLAN, record_id=plan.id,
        message=f"Weekend plan for {plan.work_date} submitted for your approval.",
        actor_user_id=user_id)


async def submit_plan(
    session: AsyncSession, *, staff_id: uuid.UUID, plan_id: uuid.UUID,
    user_id: uuid.UUID, approver_id: uuid.UUID | None = None,
) -> dict:
    """Submit an existing DRAFT/REJECTED plan without re-sending its body."""
    plan = await _get_own(session, staff_id=staff_id, plan_id=plan_id)
    if plan.approval_status not in _EDITABLE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"A {plan.approval_status} plan can't be submitted.",
        )
    has_item = (await session.execute(
        select(WeekendPlanItem.id).where(
            WeekendPlanItem.weekend_work_id == plan.id,
            WeekendPlanItem.is_deleted == False,  # noqa: E712
        ).limit(1)
    )).scalar_one_or_none()
    if has_item is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Add at least one work line before submitting.",
        )
    resubmit = plan.approval_status == "REJECTED"
    await _do_submit(session, plan=plan, branch_id=plan.branch_id,
                     chosen_approver_id=approver_id, user_id=user_id, resubmit=resubmit)
    return await _serialize(session, plan)


async def withdraw_plan(
    session: AsyncSession, *, staff_id: uuid.UUID, plan_id: uuid.UUID, user_id: uuid.UUID,
) -> dict:
    """Withdraw a PENDING plan back to DRAFT before the approver acts (WP10)."""
    plan = await _get_own(session, staff_id=staff_id, plan_id=plan_id)
    if plan.approval_status != "PENDING":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only a pending plan can be withdrawn.",
        )
    prev_approver = plan.approver_id
    plan.approval_status = "DRAFT"
    plan.submitted_at = None
    plan.approver_id = None
    plan.updated_by = user_id
    await session.flush()
    await wf.log_action(
        session, branch_id=plan.branch_id, record_type=wf.RECORD_WEEKEND_PLAN,
        record_id=plan.id, actor_user_id=user_id, action="WITHDRAW")
    await wf.notify(
        session, branch_id=plan.branch_id, user_id=prev_approver,
        record_type=wf.RECORD_WEEKEND_PLAN, record_id=plan.id,
        message=f"Weekend plan for {plan.work_date} was withdrawn by the teacher.",
        actor_user_id=user_id)
    return await _serialize(session, plan)


async def delete_plan(
    session: AsyncSession, *, staff_id: uuid.UUID, plan_id: uuid.UUID, user_id: uuid.UUID,
) -> None:
    """Soft-delete a DRAFT plan (only a draft; submitted plans keep their record)."""
    plan = await _get_own(session, staff_id=staff_id, plan_id=plan_id)
    if plan.approval_status != "DRAFT":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only a draft plan can be deleted.",
        )
    plan.is_deleted = True
    plan.updated_by = user_id
    await session.flush()


async def list_plans(
    session: AsyncSession, *, staff_id: uuid.UUID, start: date, end: date,
) -> list[dict]:
    """The teacher's own plans in a date range, newest first (WP08)."""
    plans = list((await session.execute(
        select(WeekendWork).where(
            WeekendWork.staff_id == staff_id,
            WeekendWork.origin == "TEACHER_PLAN",
            WeekendWork.work_date >= start,
            WeekendWork.work_date <= end,
            WeekendWork.is_deleted == False,  # noqa: E712
        ).order_by(WeekendWork.work_date.desc())
    )).scalars().all())
    return [await _serialize(session, p, with_history=False) for p in plans]


async def get_plan(
    session: AsyncSession, *, staff_id: uuid.UUID, plan_id: uuid.UUID,
) -> dict:
    plan = await _get_own(session, staff_id=staff_id, plan_id=plan_id)
    return await _serialize(session, plan)


async def plan_meta(
    session: AsyncSession, *, staff_id: uuid.UUID, start: date, end: date,
) -> dict:
    """Date-picker + dropdown data for the plan form (WP02/WP03/WP05): the branch
    holidays in the window, the allowed work types, and the teacher's mapped
    default approver (if any). Weekends are computed client-side."""
    from app.modules.auth.models.auth_models import User
    from app.modules.lectures.models.lecture_models import Holiday
    from app.modules.teacher_portal.models.workflow_models import ApproverMapping
    from app.modules.teacher_portal.schemas.portal_schemas import WEEKEND_WORK_TYPES

    branch_id = await wf.resolve_branch_id(session, staff_id)
    holidays = list((await session.execute(
        select(Holiday).where(
            Holiday.branch_id == branch_id,
            Holiday.holiday_date >= start,
            Holiday.holiday_date <= end,
            Holiday.is_deleted == False,  # noqa: E712
        ).order_by(Holiday.holiday_date.asc())
    )).scalars().all())

    mapping = (await session.execute(
        select(ApproverMapping).where(
            ApproverMapping.staff_id == staff_id,
            ApproverMapping.branch_id == branch_id,
            ApproverMapping.is_deleted == False,  # noqa: E712
        ).order_by(ApproverMapping.is_default.desc())
    )).scalars().first()
    default_approver = None
    if mapping is not None:
        u = (await session.execute(
            select(User).where(User.id == mapping.approver_user_id)
        )).scalar_one_or_none()
        if u is not None:
            default_approver = {
                "id": u.id, "name": f"{u.first_name} {u.last_name}".strip()}

    return {
        "holidays": [{"date": h.holiday_date, "name": h.name} for h in holidays],
        "work_types": sorted(WEEKEND_WORK_TYPES),
        "default_approver": default_approver,
    }
