"""Teacher leave — self-service apply + admin approve/reject (Slice 8).

A teacher applies for leave from the portal; the request starts ``pending`` and
only blocks scheduling once an academic head / branch admin approves it. The
teacher id is resolved from the session's staff link (``staff.linked_teacher_id``)
so a teacher can only ever file/cancel their own leave.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.services import audit_service
from app.modules.staff.models.staff_models import Staff
from app.modules.teacher.models.teacher_models import Teacher, TeacherLeave
from app.modules.teacher.repositories import teacher_repository


async def _staff(session: AsyncSession, staff_id: uuid.UUID) -> Staff:
    s = (await session.execute(
        select(Staff).where(Staff.id == staff_id, Staff.is_deleted == False)  # noqa: E712
    )).scalar_one_or_none()
    if s is None:
        raise HTTPException(status_code=404, detail="Staff record not found")
    return s


async def _teacher_for_staff(session: AsyncSession, staff_id: uuid.UUID) -> Teacher:
    """The teachers-row this portal account maps to. Leave is keyed by teacher,
    so an account whose staff record isn't linked to a teacher can't use it."""
    s = await _staff(session, staff_id)
    if s.linked_teacher_id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This account is not linked to a teaching record, so leave "
                   "cannot be applied here. Please contact the office.",
        )
    t = await teacher_repository.get_by_id(session, s.linked_teacher_id)
    if t is None:
        raise HTTPException(status_code=404, detail="Teacher record not found")
    return t


def _row(leave: TeacherLeave) -> dict:
    return {
        "id": leave.id,
        "start_date": leave.start_date,
        "end_date": leave.end_date,
        "reason": leave.reason,
        "status": leave.status,
        "decided_at": leave.decided_at.isoformat() if leave.decided_at else None,
        "decision_note": leave.decision_note,
    }


async def apply_leave(
    session: AsyncSession,
    *,
    staff_id: uuid.UUID,
    user_id: uuid.UUID,
    start_date: date,
    end_date: date,
    reason: str | None,
    ip: str | None = None,
) -> dict:
    if end_date < start_date:
        raise HTTPException(status_code=422, detail="End date must not be before start date.")
    if start_date < date.today():
        raise HTTPException(status_code=422, detail="Leave cannot start in the past.")

    t = await _teacher_for_staff(session, staff_id)

    # Reject a request that overlaps an existing pending/approved leave.
    existing = await teacher_repository.list_leaves(session, t.branch_id, teacher_id=t.id)
    for e in existing:
        if e.status != "rejected" and e.start_date <= end_date and e.end_date >= start_date:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="You already have a leave request overlapping these dates.",
            )

    leave = await teacher_repository.create_leave(
        session, teacher_id=t.id, branch_id=t.branch_id,
        start_date=start_date, end_date=end_date, reason=reason,
        status="pending", requested_by=user_id,
    )
    await audit_service.log_action(
        session, user_id=user_id, action="CREATE", table_name="teacher_leaves",
        record_id=leave.id, new_values={"leave_request": True, "status": "pending"},
        ip_address=ip, branch_id=t.branch_id,
    )
    return _row(leave)


async def my_leaves(session: AsyncSession, staff_id: uuid.UUID) -> list[dict]:
    t = await _teacher_for_staff(session, staff_id)
    rows = await teacher_repository.list_leaves(session, t.branch_id, teacher_id=t.id)
    # Most recent first for the portal list.
    rows.sort(key=lambda r: r.start_date, reverse=True)
    return [_row(r) for r in rows]


async def cancel_leave(
    session: AsyncSession, *, staff_id: uuid.UUID, leave_id: uuid.UUID, user_id: uuid.UUID,
    ip: str | None = None,
) -> None:
    t = await _teacher_for_staff(session, staff_id)
    leave = await teacher_repository.get_leave_by_id(session, leave_id)
    # Must be the teacher's own leave, and only a still-pending request may be
    # withdrawn (an approved/rejected decision is the admin's to change).
    if leave is None or leave.teacher_id != t.id:
        raise HTTPException(status_code=404, detail="Leave request not found")
    if leave.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only a pending request can be withdrawn.",
        )
    await teacher_repository.soft_delete_leave(session, leave)
    await audit_service.log_action(
        session, user_id=user_id, action="DELETE", table_name="teacher_leaves",
        record_id=leave.id, new_values={"withdrawn": True}, ip_address=ip,
        branch_id=t.branch_id,
    )


# ── admin: approve / reject ──────────────────────────────────────────────────

async def list_requests(
    session: AsyncSession, *, branch_id: uuid.UUID, status_filter: str | None = None,
) -> list[dict]:
    """Leave requests for the admin queue, newest first, with teacher name."""
    rows = await teacher_repository.list_leaves(session, branch_id, status=status_filter)
    out: list[dict] = []
    for r in rows:
        t = await teacher_repository.get_by_id(session, r.teacher_id)
        name = f"{t.first_name} {t.last_name}".strip() if t else "—"
        out.append({**_row(r), "teacher_id": r.teacher_id, "teacher_name": name})
    out.sort(key=lambda x: x["start_date"], reverse=True)
    return out


async def decide(
    session: AsyncSession, *, leave_id: uuid.UUID, approve: bool, actor_id: uuid.UUID,
    branch_id: uuid.UUID, note: str | None = None, ip: str | None = None,
) -> dict:
    leave = await teacher_repository.get_leave_by_id(session, leave_id)
    if leave is None or leave.branch_id != branch_id:
        raise HTTPException(status_code=404, detail="Leave request not found")
    if leave.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"This request is already {leave.status}.",
        )
    leave.status = "approved" if approve else "rejected"
    leave.decided_by = actor_id
    leave.decided_at = datetime.now(timezone.utc)
    leave.decision_note = note
    await session.flush()
    await audit_service.log_action(
        session, user_id=actor_id, action="UPDATE", table_name="teacher_leaves",
        record_id=leave.id, new_values={"status": leave.status}, ip_address=ip,
        branch_id=branch_id,
    )
    return _row(leave)
