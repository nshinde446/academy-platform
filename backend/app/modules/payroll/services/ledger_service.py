"""Carry-forward ledger (§4) — the only place balance rows are written.

Append-only: this module only ever INSERTs. A correction is a ``reversal`` row,
never an edit or delete (enforced at the DB level by a trigger on Postgres,
migration 0069). The running balance is stored on every row and can never go
below zero (unless ``allow_negative`` is explicitly enabled in settings).
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.payroll.models.payroll_models import CarryForwardLedger
from app.modules.payroll.services.calc_service import MonthComputation


def _ym_key(year: int, month: int) -> int:
    return year * 12 + (month - 1)


async def _next_seq(session: AsyncSession, staff_id: uuid.UUID) -> int:
    cur = (await session.execute(
        select(func.max(CarryForwardLedger.seq)).where(
            CarryForwardLedger.staff_id == staff_id
        )
    )).scalar_one_or_none()
    return (cur or 0) + 1


async def current_balance(session: AsyncSession, staff_id: uuid.UUID) -> float:
    """The latest running balance for a staff member (0 if the ledger is empty)."""
    row = (await session.execute(
        select(CarryForwardLedger.running_balance)
        .where(CarryForwardLedger.staff_id == staff_id)
        .order_by(CarryForwardLedger.seq.desc())
        .limit(1)
    )).scalar_one_or_none()
    return float(row) if row is not None else 0.0


async def balance_before(
    session: AsyncSession, staff_id: uuid.UUID, year: int, month: int
) -> float:
    """The running balance carried into (year, month) — the running balance of
    the most recent ledger row belonging to an earlier month."""
    rows = (await session.execute(
        select(CarryForwardLedger.year, CarryForwardLedger.month,
               CarryForwardLedger.seq, CarryForwardLedger.running_balance)
        .where(CarryForwardLedger.staff_id == staff_id)
        .order_by(CarryForwardLedger.seq)
    )).all()
    target = _ym_key(year, month)
    bal = 0.0
    for y, m, _seq, rb in rows:
        if _ym_key(y, m) < target:
            bal = float(rb)
    return bal


async def _append(
    session: AsyncSession,
    *,
    staff_id: uuid.UUID,
    branch_id: uuid.UUID,
    year: int,
    month: int,
    entry_type: str,
    days: float,
    running_balance: float,
    note: str | None,
    user_id: uuid.UUID | None,
) -> CarryForwardLedger:
    row = CarryForwardLedger(
        branch_id=branch_id,
        staff_id=staff_id,
        year=year,
        month=month,
        seq=await _next_seq(session, staff_id),
        entry_type=entry_type,
        days=days,
        running_balance=running_balance,
        note=note,
        created_by=user_id,
    )
    session.add(row)
    await session.flush()
    return row


async def month_entries(
    session: AsyncSession, staff_id: uuid.UUID, year: int, month: int
) -> list[CarryForwardLedger]:
    return list((await session.execute(
        select(CarryForwardLedger).where(
            CarryForwardLedger.staff_id == staff_id,
            CarryForwardLedger.year == year,
            CarryForwardLedger.month == month,
        ).order_by(CarryForwardLedger.seq)
    )).scalars().all())


async def apply_computation(
    session: AsyncSession,
    comp: MonthComputation,
    *,
    branch_id: uuid.UUID,
    user_id: uuid.UUID | None,
) -> list[CarryForwardLedger]:
    """Write the ledger rows implied by a computed month (§3).

    - net > 0: ``extra_added`` (+added) brings the balance up toward the cap;
      if some was trimmed, a ``cap_trim`` row records it (no balance change).
    - net < 0: ``compensation_used`` (−balance_used) consumes the balance; the
      uncovered remainder gets no ledger row (it is handled by the request flow).
    - net == 0: nothing (§3 Example 3)."""
    created: list[CarryForwardLedger] = []
    bal = comp.balance_in
    if comp.added > 0:
        bal += comp.added
        created.append(await _append(
            session, staff_id=comp.staff_id, branch_id=branch_id,
            year=comp.year, month=comp.month, entry_type="extra_added",
            days=comp.added, running_balance=bal,
            note=None, user_id=user_id,
        ))
    if comp.trimmed > 0:
        created.append(await _append(
            session, staff_id=comp.staff_id, branch_id=branch_id,
            year=comp.year, month=comp.month, entry_type="cap_trim",
            days=comp.trimmed, running_balance=bal,
            note=f"cap trimmed {comp.trimmed:g} day(s) over cap", user_id=user_id,
        ))
    if comp.balance_used > 0:
        bal -= comp.balance_used
        created.append(await _append(
            session, staff_id=comp.staff_id, branch_id=branch_id,
            year=comp.year, month=comp.month, entry_type="compensation_used",
            days=-comp.balance_used, running_balance=bal,
            note=None, user_id=user_id,
        ))
    return created


async def reverse_to(
    session: AsyncSession,
    *,
    staff_id: uuid.UUID,
    branch_id: uuid.UUID,
    year: int,
    month: int,
    target_balance: float,
    user_id: uuid.UUID | None,
) -> CarryForwardLedger | None:
    """Undo a month's prior balance movement with a single ``reversal`` row that
    returns the running balance to ``target_balance`` — the balance the staff
    carried into the month before the correction (§4 / §12 "corrected punch
    later"). Returns None when the balance is already there (nothing to undo)."""
    cur = await current_balance(session, staff_id)
    delta = target_balance - cur
    if delta == 0:
        return None
    return await _append(
        session, staff_id=staff_id, branch_id=branch_id, year=year, month=month,
        entry_type="reversal", days=delta, running_balance=target_balance,
        note="reversal of recomputed month", user_id=user_id,
    )
