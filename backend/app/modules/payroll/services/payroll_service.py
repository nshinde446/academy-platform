"""Payroll orchestration (§2/§6) — ties the engine to the ledger and the stored
per-staff monthly snapshot.

- :func:`preview_month` computes every staff member's figures without writing
  anything (the OPEN-month preview).
- :func:`close_month` freezes the month: it writes the ledger rows and the
  ``payroll_staff_month`` snapshots and flips the month to CLOSED. Safe to repeat
  (§12 double-click) — a month already CLOSED is left alone.
- :func:`recompute_from` re-runs a month and every later CLOSED month with
  ``reversal`` rows after a past attendance correction (§12).
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.payroll.models.payroll_models import (
    PayrollMonthSettings,
    PayrollStaffMonth,
)
from app.modules.payroll.services import calc_service, config_service, ledger_service
from app.modules.payroll.services.calc_service import MonthComputation
from app.modules.staff.models.staff_models import Staff


async def _branch_staff(session: AsyncSession, branch_id: uuid.UUID) -> list[Staff]:
    return list((await session.execute(
        select(Staff).where(
            Staff.branch_id == branch_id,
            Staff.is_deleted == False,  # noqa: E712
        ).order_by(Staff.emp_code)
    )).scalars().all())


async def _settings(
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


async def _calc_params(session: AsyncSession) -> dict:
    cfg = await config_service.get_config(session)
    return {
        "cap": float(cfg.get("carry_forward_cap", 5) or 0),
        "holiday_treatment": str(cfg.get("holiday_treatment", "credited")),
        "allow_negative": bool(cfg.get("allow_negative_balance", False)),
    }


async def preview_month(
    session: AsyncSession, *, branch_id: uuid.UUID, year: int, month: int
) -> list[MonthComputation]:
    """Compute every staff member's figures for the month without writing
    anything — the OPEN-month draft (§6). Uses the balance each staff carries in
    from the ledger as it stands now."""
    params = await _calc_params(session)
    out: list[MonthComputation] = []
    for staff in await _branch_staff(session, branch_id):
        bal = await ledger_service.balance_before(session, staff.id, year, month)
        out.append(await calc_service.compute_month(
            session, staff=staff, branch_id=branch_id, year=year, month=month,
            balance_in=bal, **params,
        ))
    return out


async def _upsert_snapshot(
    session: AsyncSession,
    comp: MonthComputation,
    *,
    branch_id: uuid.UUID,
    lifecycle: str,
    user_id: uuid.UUID | None,
) -> PayrollStaffMonth:
    row = (await session.execute(
        select(PayrollStaffMonth).where(
            PayrollStaffMonth.staff_id == comp.staff_id,
            PayrollStaffMonth.year == comp.year,
            PayrollStaffMonth.month == comp.month,
        )
    )).scalar_one_or_none()
    if row is None:
        row = PayrollStaffMonth(
            branch_id=branch_id, staff_id=comp.staff_id,
            year=comp.year, month=comp.month,
        )
        session.add(row)
    row.required_days = comp.required_days
    row.makeup_days = comp.makeup_days
    row.effective_required = comp.effective_required
    row.present_days = comp.present_days
    row.half_days = comp.half_days
    row.paid_leave_days = comp.paid_leave_days
    row.credited_days = comp.credited_days
    row.net_days = comp.net_days
    row.extra_days = comp.extra_days
    row.shortfall_days = comp.shortfall_days
    row.balance_in = comp.balance_in
    row.balance_out = comp.balance_out
    row.uncovered_days = comp.uncovered_days
    row.late_fine_total = comp.late_fine_total
    row.lifecycle = lifecycle
    row.updated_by = user_id
    await session.flush()
    return row


async def close_month(
    session: AsyncSession,
    *,
    branch_id: uuid.UUID,
    year: int,
    month: int,
    user_id: uuid.UUID | None,
) -> list[PayrollStaffMonth]:
    """Freeze the month (§6): write ledger rows + snapshots and set CLOSED.

    Idempotent: a month already CLOSED or LOCKED returns its snapshots without
    writing new ledger rows (§12 double-click safety)."""
    from fastapi import HTTPException

    settings = await _settings(session, branch_id, year, month)
    if settings is None:
        raise HTTPException(status_code=404, detail="Month is not set up")
    if settings.lifecycle != "OPEN":
        # Already closed/locked — return the stored snapshots unchanged.
        return list((await session.execute(
            select(PayrollStaffMonth).where(
                PayrollStaffMonth.branch_id == branch_id,
                PayrollStaffMonth.year == year,
                PayrollStaffMonth.month == month,
            )
        )).scalars().all())

    params = await _calc_params(session)
    snapshots: list[PayrollStaffMonth] = []
    for staff in await _branch_staff(session, branch_id):
        bal = await ledger_service.balance_before(session, staff.id, year, month)
        comp = await calc_service.compute_month(
            session, staff=staff, branch_id=branch_id, year=year, month=month,
            balance_in=bal, **params,
        )
        await ledger_service.apply_computation(
            session, comp, branch_id=branch_id, user_id=user_id
        )
        snapshots.append(await _upsert_snapshot(
            session, comp, branch_id=branch_id, lifecycle="CLOSED", user_id=user_id
        ))

    settings.lifecycle = "CLOSED"
    settings.updated_by = user_id
    await session.flush()
    return snapshots


async def recompute_from(
    session: AsyncSession,
    *,
    branch_id: uuid.UUID,
    year: int,
    month: int,
    user_id: uuid.UUID | None,
) -> list[PayrollStaffMonth]:
    """Recompute the given month and every later CLOSED/LOCKED month after a past
    attendance correction (§12). Prior balance movements are undone with
    ``reversal`` rows and fresh entries written, so the ledger stays append-only
    and the running balance threads through correctly."""
    params = await _calc_params(session)
    # The CLOSED/LOCKED months at or after (year, month), in chronological order.
    rows = (await session.execute(
        select(PayrollMonthSettings).where(
            PayrollMonthSettings.branch_id == branch_id,
            PayrollMonthSettings.is_deleted == False,  # noqa: E712
            PayrollMonthSettings.lifecycle.in_(("CLOSED", "LOCKED")),
        )
    )).scalars().all()
    months = sorted(
        ((s.year, s.month) for s in rows if (s.year, s.month) >= (year, month))
    )

    touched: list[PayrollStaffMonth] = []
    for staff in await _branch_staff(session, branch_id):
        for (y, m) in months:
            # Balance entering this month, corrected (earlier months in this loop
            # were already reprocessed and thread the right balance here).
            bal = await ledger_service.balance_before(session, staff.id, y, m)
            await ledger_service.reverse_to(
                session, staff_id=staff.id, branch_id=branch_id,
                year=y, month=m, target_balance=bal, user_id=user_id,
            )
            comp = await calc_service.compute_month(
                session, staff=staff, branch_id=branch_id, year=y, month=m,
                balance_in=bal, **params,
            )
            await ledger_service.apply_computation(
                session, comp, branch_id=branch_id, user_id=user_id
            )
            # Keep the snapshot's lifecycle as it was (CLOSED/LOCKED).
            s = next(x for x in rows if (x.year, x.month) == (y, m))
            touched.append(await _upsert_snapshot(
                session, comp, branch_id=branch_id, lifecycle=s.lifecycle,
                user_id=user_id,
            ))
    return touched
