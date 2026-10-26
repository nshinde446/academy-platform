"""Month setup and lifecycle (§1/§6/§12).

Super Admin sets the required days and declares paid holidays, and moves a month
OPEN → CLOSED → LOCKED (with Super-Admin-only reopen). Every change to days,
settings or lifecycle is written to the existing audit log with who/what/when and
the old/new values; editing a CLOSED/LOCKED month (or reopening) recomputes that
month and every later one (§12).
"""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.services import audit_service
from app.modules.payroll.models.payroll_models import (
    PayrollMonthHoliday,
    PayrollMonthSettings,
)
from app.modules.payroll.services import payroll_service, request_service


async def _recompute_and_expire(
    session: AsyncSession,
    *,
    branch_id: uuid.UUID,
    year: int,
    month: int,
    user_id: uuid.UUID,
) -> None:
    """Recompute this month and every later CLOSED/LOCKED month, then auto-expire
    any active request whose shortfall the balance now covers (§5/§12)."""
    await payroll_service.recompute_from(
        session, branch_id=branch_id, year=year, month=month, user_id=user_id
    )
    rows = (await session.execute(
        select(PayrollMonthSettings).where(
            PayrollMonthSettings.branch_id == branch_id,
            PayrollMonthSettings.is_deleted == False,  # noqa: E712
            PayrollMonthSettings.lifecycle.in_(("CLOSED", "LOCKED")),
        )
    )).scalars().all()
    for s in rows:
        if (s.year, s.month) >= (year, month):
            await request_service.expire_covered(
                session, branch_id=branch_id, year=s.year, month=s.month, user_id=user_id
            )


async def _get(
    session: AsyncSession, branch_id: uuid.UUID, year: int, month: int
) -> PayrollMonthSettings | None:
    return (await session.execute(
        select(PayrollMonthSettings).where(
            PayrollMonthSettings.branch_id == branch_id,
            PayrollMonthSettings.year == year,
            PayrollMonthSettings.month == month,
            PayrollMonthSettings.is_deleted == False,  # noqa: E712
        )
    )).scalar_one_or_none()


async def _holidays(
    session: AsyncSession, branch_id: uuid.UUID, year: int, month: int
) -> list[PayrollMonthHoliday]:
    return list((await session.execute(
        select(PayrollMonthHoliday).where(
            PayrollMonthHoliday.branch_id == branch_id,
            PayrollMonthHoliday.year == year,
            PayrollMonthHoliday.month == month,
            PayrollMonthHoliday.is_deleted == False,  # noqa: E712
        ).order_by(PayrollMonthHoliday.holiday_date)
    )).scalars().all())


async def get_month(
    session: AsyncSession, branch_id: uuid.UUID, year: int, month: int
) -> dict:
    s = await _get(session, branch_id, year, month)
    holidays = await _holidays(session, branch_id, year, month)
    return {
        "year": year,
        "month": month,
        "required_days": float(s.required_days) if s else 0.0,
        "lifecycle": s.lifecycle if s else "NOT_SET",
        "notes": s.notes if s else None,
        "holidays": [
            {
                "id": str(h.id), "holiday_date": h.holiday_date, "title": h.title,
                "kind": h.kind, "credit_days": float(h.credit_days),
            }
            for h in holidays
        ],
    }


async def list_months(
    session: AsyncSession, branch_id: uuid.UUID, year: int | None = None
) -> list[dict]:
    q = select(PayrollMonthSettings).where(
        PayrollMonthSettings.branch_id == branch_id,
        PayrollMonthSettings.is_deleted == False,  # noqa: E712
    )
    if year is not None:
        q = q.where(PayrollMonthSettings.year == year)
    rows = (await session.execute(
        q.order_by(PayrollMonthSettings.year.desc(), PayrollMonthSettings.month.desc())
    )).scalars().all()
    return [
        {
            "year": r.year, "month": r.month,
            "required_days": float(r.required_days),
            "lifecycle": r.lifecycle, "notes": r.notes, "holidays": [],
        }
        for r in rows
    ]


async def upsert_month(
    session: AsyncSession,
    *,
    branch_id: uuid.UUID,
    year: int,
    month: int,
    required_days: float,
    notes: str | None,
    reason: str | None,
    user_id: uuid.UUID,
    ip: str | None,
) -> dict:
    """Create or update a month's required days (§1). Editing a CLOSED/LOCKED
    month needs a reason and triggers a recompute of that month and later ones
    (§12). All changes are audited."""
    if not 1 <= month <= 12:
        raise HTTPException(status_code=422, detail="month must be 1–12")
    s = await _get(session, branch_id, year, month)
    old = None
    if s is None:
        s = PayrollMonthSettings(
            branch_id=branch_id, year=year, month=month,
            required_days=required_days, notes=notes, lifecycle="OPEN",
            created_by=user_id,
        )
        session.add(s)
        action = "Create Payroll Month"
    else:
        if s.lifecycle in ("CLOSED", "LOCKED") and not reason:
            raise HTTPException(
                status_code=422,
                detail="A reason is required to change a closed or locked month",
            )
        old = {"required_days": float(s.required_days), "notes": s.notes}
        s.required_days = required_days
        s.notes = notes
        s.updated_by = user_id
        action = "Update Payroll Month"
    await session.flush()

    recomputed = False
    if s.lifecycle in ("CLOSED", "LOCKED"):
        await _recompute_and_expire(
            session, branch_id=branch_id, year=year, month=month, user_id=user_id
        )
        recomputed = True

    await audit_service.log_action(
        session, user_id=user_id, action=action,
        table_name="payroll_month_settings", record_id=s.id,
        old_values=old,
        new_values={
            "required_days": required_days, "notes": notes,
            "reason": reason, "recomputed": recomputed,
        },
        ip_address=ip, branch_id=branch_id,
    )
    return await get_month(session, branch_id, year, month)


async def add_holiday(
    session: AsyncSession,
    *,
    branch_id: uuid.UUID,
    year: int,
    month: int,
    holiday_date: date,
    title: str,
    kind: str,
    credit_days: float,
    user_id: uuid.UUID,
    ip: str | None,
) -> dict:
    if holiday_date.year != year or holiday_date.month != month:
        raise HTTPException(
            status_code=422, detail="Holiday date must fall in the given month"
        )
    h = PayrollMonthHoliday(
        branch_id=branch_id, year=year, month=month, holiday_date=holiday_date,
        title=title, kind=kind, credit_days=credit_days, created_by=user_id,
    )
    session.add(h)
    await session.flush()
    await audit_service.log_action(
        session, user_id=user_id, action="Add Payroll Holiday",
        table_name="payroll_month_holidays", record_id=h.id,
        new_values={"date": str(holiday_date), "title": title, "kind": kind,
                    "credit_days": credit_days},
        ip_address=ip, branch_id=branch_id,
    )
    # A closed month that gains a holiday must be recomputed.
    s = await _get(session, branch_id, year, month)
    if s and s.lifecycle in ("CLOSED", "LOCKED"):
        await _recompute_and_expire(
            session, branch_id=branch_id, year=year, month=month, user_id=user_id
        )
    return await get_month(session, branch_id, year, month)


async def remove_holiday(
    session: AsyncSession,
    *,
    branch_id: uuid.UUID,
    holiday_id: uuid.UUID,
    user_id: uuid.UUID,
    ip: str | None,
) -> dict:
    h = (await session.execute(
        select(PayrollMonthHoliday).where(
            PayrollMonthHoliday.id == holiday_id,
            PayrollMonthHoliday.is_deleted == False,  # noqa: E712
        )
    )).scalar_one_or_none()
    if h is None or h.branch_id != branch_id:
        raise HTTPException(status_code=404, detail="Holiday not found")
    h.is_deleted = True
    h.updated_by = user_id
    await session.flush()
    await audit_service.log_action(
        session, user_id=user_id, action="Remove Payroll Holiday",
        table_name="payroll_month_holidays", record_id=h.id,
        old_values={"date": str(h.holiday_date), "title": h.title},
        ip_address=ip, branch_id=branch_id,
    )
    s = await _get(session, branch_id, h.year, h.month)
    if s and s.lifecycle in ("CLOSED", "LOCKED"):
        await _recompute_and_expire(
            session, branch_id=branch_id, year=h.year, month=h.month, user_id=user_id
        )
    return await get_month(session, branch_id, h.year, h.month)


# Allowed lifecycle transitions (§6).
_TRANSITIONS = {
    ("OPEN", "close"): "CLOSED",
    ("CLOSED", "lock"): "LOCKED",
    ("CLOSED", "reopen"): "OPEN",
    ("LOCKED", "reopen"): "OPEN",
}


async def change_lifecycle(
    session: AsyncSession,
    *,
    branch_id: uuid.UUID,
    year: int,
    month: int,
    verb: str,  # close | lock | reopen
    reason: str | None,
    user_id: uuid.UUID,
    ip: str | None,
) -> dict:
    s = await _get(session, branch_id, year, month)
    if s is None:
        raise HTTPException(status_code=404, detail="Month is not set up")
    target = _TRANSITIONS.get((s.lifecycle, verb))
    if target is None:
        raise HTTPException(
            status_code=422,
            detail=f"Cannot {verb} a month that is {s.lifecycle}",
        )
    if verb == "reopen" and not reason:
        raise HTTPException(status_code=422, detail="Reopening needs a reason")

    old_status = s.lifecycle
    if verb == "close":
        # close_month writes the ledger + snapshots and sets CLOSED.
        await payroll_service.close_month(
            session, branch_id=branch_id, year=year, month=month, user_id=user_id
        )
        # A freshly closed month may already be covered by the balance.
        await request_service.expire_covered(
            session, branch_id=branch_id, year=year, month=month, user_id=user_id
        )
    else:
        s.lifecycle = target
        s.updated_by = user_id
        await session.flush()
        if verb == "reopen":
            # Recompute later months now that this one is editable again (§6).
            await _recompute_and_expire(
                session, branch_id=branch_id, year=year, month=month, user_id=user_id
            )

    await audit_service.log_action(
        session, user_id=user_id, action=f"Payroll Month {verb.title()}",
        table_name="payroll_month_settings", record_id=s.id,
        old_values={"lifecycle": old_status},
        new_values={"lifecycle": target, "reason": reason},
        ip_address=ip, branch_id=branch_id,
    )
    return await get_month(session, branch_id, year, month)
