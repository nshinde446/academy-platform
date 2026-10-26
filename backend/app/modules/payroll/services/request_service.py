"""Extra-day request flow (§5).

When a month closes with an uncovered shortfall, HR / Accounts / Branch Admin
raise a request to work the missing days next month; the Super Admin approves or
rejects it. On approval the target month's required days rise by the shortfall
(the engine reads APPROVED requests as make-up) and the source month's shortfall
is flagged *deferred* — no longer counted as unpaid (§5, Example 2).

State machine:  PENDING → APPROVED | REJECTED | CANCELLED,  and an active request
auto-EXPIRES if the balance later covers the shortfall. Every transition is
written to ``extra_day_request_history`` (who / when / note) and the audit log.
"""

from __future__ import annotations

import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.services import audit_service
from app.modules.payroll.models.payroll_models import (
    ExtraDayRequest,
    ExtraDayRequestHistory,
    PayrollStaffMonth,
)
from app.modules.payroll.services import config_service, payroll_service
from app.modules.staff.models.staff_models import Staff


def _next_month(year: int, month: int) -> tuple[int, int]:
    return (year + 1, 1) if month == 12 else (year, month + 1)


async def _roles_can_raise(session: AsyncSession, roles: list[str]) -> bool:
    if "super_admin" in roles:
        return True
    allowed = set(await config_service.get_value(session, "request_raiser_roles") or [])
    if await config_service.get_value(session, "allow_manager_approver"):
        allowed.add("manager")
    return bool(allowed & set(roles))


async def _roles_can_approve(session: AsyncSession, roles: list[str]) -> bool:
    if "super_admin" in roles:
        return True
    if await config_service.get_value(session, "allow_manager_approver") and "manager" in roles:
        return True
    approver = await config_service.get_value(session, "request_approver_role")
    return approver in roles


async def _history(
    session: AsyncSession,
    req: ExtraDayRequest,
    *,
    from_status: str | None,
    to_status: str,
    user_id: uuid.UUID | None,
    note: str | None,
) -> None:
    session.add(ExtraDayRequestHistory(
        request_id=req.id, from_status=from_status, to_status=to_status,
        changed_by=user_id, note=note,
    ))
    await session.flush()


async def _snapshot(
    session: AsyncSession, staff_id: uuid.UUID, year: int, month: int
) -> PayrollStaffMonth | None:
    return (await session.execute(
        select(PayrollStaffMonth).where(
            PayrollStaffMonth.staff_id == staff_id,
            PayrollStaffMonth.year == year,
            PayrollStaffMonth.month == month,
        )
    )).scalar_one_or_none()


async def _get(session: AsyncSession, request_id: uuid.UUID, branch_id: uuid.UUID) -> ExtraDayRequest:
    req = (await session.execute(
        select(ExtraDayRequest).where(
            ExtraDayRequest.id == request_id,
            ExtraDayRequest.is_deleted == False,  # noqa: E712
        )
    )).scalar_one_or_none()
    if req is None or req.branch_id != branch_id:
        raise HTTPException(status_code=404, detail="Request not found")
    return req


def _serialize(req: ExtraDayRequest) -> dict:
    return {
        "id": str(req.id), "staff_id": str(req.staff_id),
        "source_year": req.source_year, "source_month": req.source_month,
        "target_year": req.target_year, "target_month": req.target_month,
        "shortfall_days": float(req.shortfall_days),
        "request_status": req.request_status,
        "requested_by": str(req.requested_by),
        "decided_by": str(req.decided_by) if req.decided_by else None,
        "note": req.note,
    }


async def raise_request(
    session: AsyncSession,
    *,
    branch_id: uuid.UUID,
    staff_id: uuid.UUID,
    source_year: int,
    source_month: int,
    shortfall_days: float,
    note: str | None,
    roles: list[str],
    user_id: uuid.UUID,
    ip: str | None,
) -> dict:
    if not await _roles_can_raise(session, roles):
        raise HTTPException(status_code=403, detail="Not allowed to raise requests")
    if shortfall_days <= 0:
        raise HTTPException(status_code=422, detail="shortfall_days must be positive")

    staff = (await session.execute(
        select(Staff).where(Staff.id == staff_id, Staff.is_deleted == False)  # noqa: E712
    )).scalar_one_or_none()
    if staff is None or staff.branch_id != branch_id:
        raise HTTPException(status_code=404, detail="Staff not found in this branch")

    # There must actually be an uncovered shortfall to make up (§5).
    snap = await _snapshot(session, staff_id, source_year, source_month)
    uncovered = float(snap.uncovered_days) if snap else 0.0
    if uncovered <= 0:
        raise HTTPException(
            status_code=422,
            detail="No uncovered shortfall for that staff/month to make up",
        )
    if shortfall_days > uncovered:
        raise HTTPException(
            status_code=422,
            detail=f"shortfall_days exceeds the uncovered shortfall ({uncovered:g})",
        )

    # One active (PENDING/APPROVED) request per staff per source month (§5).
    active = (await session.execute(
        select(ExtraDayRequest).where(
            ExtraDayRequest.staff_id == staff_id,
            ExtraDayRequest.source_year == source_year,
            ExtraDayRequest.source_month == source_month,
            ExtraDayRequest.request_status.in_(("PENDING", "APPROVED")),
            ExtraDayRequest.is_deleted == False,  # noqa: E712
        )
    )).scalar_one_or_none()
    if active is not None:
        raise HTTPException(
            status_code=409, detail="An active request already exists for this month"
        )

    ty, tm = _next_month(source_year, source_month)
    req = ExtraDayRequest(
        branch_id=branch_id, staff_id=staff_id,
        source_year=source_year, source_month=source_month,
        target_year=ty, target_month=tm, shortfall_days=shortfall_days,
        request_status="PENDING", requested_by=user_id, note=note,
        created_by=user_id,
    )
    session.add(req)
    await session.flush()
    await _history(session, req, from_status=None, to_status="PENDING",
                   user_id=user_id, note=note)
    await audit_service.log_action(
        session, user_id=user_id, action="Raise Extra-Day Request",
        table_name="extra_day_requests", record_id=req.id,
        new_values=_serialize(req), ip_address=ip, branch_id=branch_id,
    )
    return _serialize(req)


async def _decide(
    session: AsyncSession,
    *,
    branch_id: uuid.UUID,
    request_id: uuid.UUID,
    to_status: str,
    roles: list[str],
    user_id: uuid.UUID,
    note: str | None,
    ip: str | None,
) -> dict:
    if not await _roles_can_approve(session, roles):
        raise HTTPException(status_code=403, detail="Not allowed to decide requests")
    req = await _get(session, request_id, branch_id)
    if req.request_status != "PENDING":
        raise HTTPException(status_code=422, detail=f"Request is {req.request_status}")
    if req.requested_by == user_id:
        raise HTTPException(status_code=422, detail="The raiser cannot decide their own request")

    old = req.request_status
    req.request_status = to_status
    req.decided_by = user_id
    if note:
        req.note = note
    req.updated_by = user_id
    await session.flush()
    await _history(session, req, from_status=old, to_status=to_status,
                   user_id=user_id, note=note)

    if to_status == "APPROVED":
        # Source month's shortfall becomes deferred (not unpaid, §5 Example 2).
        snap = await _snapshot(session, req.staff_id, req.source_year, req.source_month)
        if snap is not None:
            move = min(float(snap.uncovered_days), float(req.shortfall_days))
            snap.uncovered_days = float(snap.uncovered_days) - move
            snap.deferred_days = float(snap.deferred_days) + move
            await session.flush()
        # If the target month is already finalised, recompute it so the raised
        # required days take effect.
        from app.modules.payroll.models.payroll_models import PayrollMonthSettings
        tgt = (await session.execute(
            select(PayrollMonthSettings).where(
                PayrollMonthSettings.branch_id == branch_id,
                PayrollMonthSettings.year == req.target_year,
                PayrollMonthSettings.month == req.target_month,
                PayrollMonthSettings.is_deleted == False,  # noqa: E712
            )
        )).scalar_one_or_none()
        if tgt and tgt.lifecycle in ("CLOSED", "LOCKED"):
            await payroll_service.recompute_from(
                session, branch_id=branch_id, year=req.target_year,
                month=req.target_month, user_id=user_id,
            )

    await audit_service.log_action(
        session, user_id=user_id, action=f"Extra-Day Request {to_status.title()}",
        table_name="extra_day_requests", record_id=req.id,
        old_values={"request_status": old},
        new_values={"request_status": to_status, "note": note},
        ip_address=ip, branch_id=branch_id,
    )
    return _serialize(req)


async def approve(session, **kw) -> dict:
    return await _decide(session, to_status="APPROVED", **kw)


async def reject(session, **kw) -> dict:
    return await _decide(session, to_status="REJECTED", **kw)


async def cancel(
    session: AsyncSession,
    *,
    branch_id: uuid.UUID,
    request_id: uuid.UUID,
    user_id: uuid.UUID,
    note: str | None,
    ip: str | None,
) -> dict:
    """The raiser cancels their own still-pending request (§5)."""
    req = await _get(session, request_id, branch_id)
    if req.request_status != "PENDING":
        raise HTTPException(status_code=422, detail=f"Request is {req.request_status}")
    if req.requested_by != user_id:
        raise HTTPException(status_code=403, detail="Only the raiser can cancel")
    old = req.request_status
    req.request_status = "CANCELLED"
    req.updated_by = user_id
    await session.flush()
    await _history(session, req, from_status=old, to_status="CANCELLED",
                   user_id=user_id, note=note)
    await audit_service.log_action(
        session, user_id=user_id, action="Extra-Day Request Cancelled",
        table_name="extra_day_requests", record_id=req.id,
        old_values={"request_status": old}, new_values={"request_status": "CANCELLED"},
        ip_address=ip, branch_id=branch_id,
    )
    return _serialize(req)


async def expire_covered(
    session: AsyncSession,
    *,
    branch_id: uuid.UUID,
    year: int,
    month: int,
    user_id: uuid.UUID | None,
) -> int:
    """Auto-expire active requests whose source month no longer has an uncovered
    shortfall — the balance covered it after the fact (§5). Called after a
    close/recompute. Returns how many were expired."""
    active = (await session.execute(
        select(ExtraDayRequest).where(
            ExtraDayRequest.branch_id == branch_id,
            ExtraDayRequest.source_year == year,
            ExtraDayRequest.source_month == month,
            ExtraDayRequest.request_status.in_(("PENDING", "APPROVED")),
            ExtraDayRequest.is_deleted == False,  # noqa: E712
        )
    )).scalars().all()
    expired = 0
    for req in active:
        snap = await _snapshot(session, req.staff_id, year, month)
        if snap is not None and float(snap.uncovered_days) <= 0 and float(snap.deferred_days) <= 0:
            old = req.request_status
            req.request_status = "EXPIRED"
            await session.flush()
            await _history(session, req, from_status=old, to_status="EXPIRED",
                           user_id=user_id, note="balance covered the shortfall")
            expired += 1
    return expired


async def list_requests(
    session: AsyncSession,
    *,
    branch_id: uuid.UUID,
    status: str | None = None,
    staff_id: uuid.UUID | None = None,
) -> list[dict]:
    q = select(ExtraDayRequest).where(
        ExtraDayRequest.branch_id == branch_id,
        ExtraDayRequest.is_deleted == False,  # noqa: E712
    )
    if status is not None:
        q = q.where(ExtraDayRequest.request_status == status)
    if staff_id is not None:
        q = q.where(ExtraDayRequest.staff_id == staff_id)
    rows = (await session.execute(
        q.order_by(ExtraDayRequest.created_at.desc())
    )).scalars().all()
    return [_serialize(r) for r in rows]


async def history(
    session: AsyncSession, *, branch_id: uuid.UUID, request_id: uuid.UUID
) -> list[dict]:
    await _get(session, request_id, branch_id)  # 404 if not in branch
    rows = (await session.execute(
        select(ExtraDayRequestHistory)
        .where(ExtraDayRequestHistory.request_id == request_id)
        .order_by(ExtraDayRequestHistory.changed_at)
    )).scalars().all()
    return [
        {
            "to_status": h.to_status, "from_status": h.from_status,
            "changed_by": str(h.changed_by) if h.changed_by else None,
            "note": h.note, "changed_at": h.changed_at,
        }
        for h in rows
    ]
