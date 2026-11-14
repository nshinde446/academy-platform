"""Opening carry-forward balances (client Point 1 "opening balance entry").

The software is starting mid-life: staff already carry an off-day balance from
before it existed. This lets an admin seed each staff member's balance once,
before the first payroll month, by hand or from an Excel sheet. Each seed is a
single ``opening_balance`` ledger row dated to the month *before* the first
month, so it is read as that month's ``balance_in`` and carries forward from
there like any other movement.

Seeding is a pre-start step: it is refused once any month in the branch has been
CLOSED/LOCKED, because an opening row would then have to slot behind finalised
figures (which an append-only ledger cannot do cleanly). Correct history with
the normal reopen/recompute flow instead.
"""

from __future__ import annotations

import io
import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.payroll.models.payroll_models import PayrollMonthSettings
from app.modules.payroll.services import ledger_service
from app.modules.staff.models.staff_models import Department, Staff


def _prev_ym(year: int, month: int) -> tuple[int, int]:
    """The calendar month before (year, month)."""
    return (year - 1, 12) if month == 1 else (year, month - 1)


def _staff_name(s: Staff) -> str:
    return " ".join(p for p in (s.title, s.first_name, s.last_name) if p)


async def _branch_staff(
    session: AsyncSession, branch_id: uuid.UUID
) -> tuple[list[Staff], dict[uuid.UUID, str]]:
    staff = list((await session.execute(
        select(Staff).where(
            Staff.branch_id == branch_id, Staff.is_deleted == False,  # noqa: E712
        ).order_by(Staff.emp_code)
    )).scalars().all())
    depts = {
        d.id: d.name
        for d in (await session.execute(
            select(Department).where(
                Department.branch_id == branch_id,
                Department.is_deleted == False,  # noqa: E712
            )
        )).scalars().all()
    }
    return staff, depts


async def _finalised_month_exists(session: AsyncSession, branch_id: uuid.UUID) -> bool:
    row = (await session.execute(
        select(PayrollMonthSettings.id).where(
            PayrollMonthSettings.branch_id == branch_id,
            PayrollMonthSettings.is_deleted == False,  # noqa: E712
            PayrollMonthSettings.lifecycle.in_(("CLOSED", "LOCKED")),
        ).limit(1)
    )).scalar_one_or_none()
    return row is not None


async def list_opening_balances(
    session: AsyncSession,
    *,
    branch_id: uuid.UUID,
    effective_year: int,
    effective_month: int,
) -> dict:
    """Every staff member with the balance they currently carry into the effective
    month — the opening balance to review/edit."""
    staff, depts = await _branch_staff(session, branch_id)
    rows = []
    for s in staff:
        bal = await ledger_service.balance_before(
            session, s.id, effective_year, effective_month
        )
        rows.append({
            "staff_id": str(s.id),
            "emp_code": s.emp_code,
            "name": _staff_name(s),
            "department": depts.get(s.department_id, "—"),
            "opening_balance": bal,
        })
    return {
        "effective_year": effective_year,
        "effective_month": effective_month,
        "locked": await _finalised_month_exists(session, branch_id),
        "rows": rows,
    }


async def set_opening_balances(
    session: AsyncSession,
    *,
    branch_id: uuid.UUID,
    effective_year: int,
    effective_month: int,
    entries: list[tuple[uuid.UUID, float]],
    user_id: uuid.UUID | None,
) -> int:
    """Seed/adjust opening balances for the given staff. Returns the number of
    ledger rows written (unchanged balances are skipped)."""
    if not (1 <= effective_month <= 12):
        raise HTTPException(status_code=422, detail="effective_month must be 1–12")
    if await _finalised_month_exists(session, branch_id):
        raise HTTPException(
            status_code=409,
            detail=(
                "A payroll month is already closed/locked. Opening balances can "
                "only be set before the first month is finalised."
            ),
        )
    # Only staff that belong to this branch may be seeded.
    valid = {
        s.id for s in (await session.execute(
            select(Staff).where(
                Staff.branch_id == branch_id, Staff.is_deleted == False,  # noqa: E712
            )
        )).scalars().all()
    }
    py, pm = _prev_ym(effective_year, effective_month)
    written = 0
    for staff_id, balance in entries:
        if staff_id not in valid:
            continue
        row = await ledger_service.append_opening_balance(
            session, staff_id=staff_id, branch_id=branch_id,
            year=py, month=pm, target_balance=float(balance), user_id=user_id,
        )
        if row is not None:
            written += 1
    await session.flush()
    return written


async def parse_import(
    session: AsyncSession, *, branch_id: uuid.UUID, file_bytes: bytes
) -> dict:
    """Parse an uploaded .xlsx of opening balances into reviewable rows. Expects a
    header row with an employee-code column (``emp_code`` / ``code`` / ``empcode``)
    and a balance column (``opening_balance`` / ``balance`` / ``opening``). Returns
    matched rows (joined to staff) and unmatched codes for the admin to review
    before committing via the normal save."""
    try:
        from openpyxl import load_workbook

        wb = load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
    except Exception:  # noqa: BLE001
        raise HTTPException(status_code=422, detail="Could not read the Excel file")
    ws = wb.active
    rows_iter = ws.iter_rows(values_only=True)
    try:
        header = next(rows_iter)
    except StopIteration:
        raise HTTPException(status_code=422, detail="The sheet is empty")

    def _norm(v: object) -> str:
        return str(v).strip().lower().replace(" ", "_") if v is not None else ""

    cols = {_norm(h): i for i, h in enumerate(header)}
    code_col = next((cols[k] for k in ("emp_code", "empcode", "code", "employee_code") if k in cols), None)
    bal_col = next((cols[k] for k in ("opening_balance", "balance", "opening", "days") if k in cols), None)
    if code_col is None or bal_col is None:
        raise HTTPException(
            status_code=422,
            detail="Need an employee-code column and an opening-balance column.",
        )

    staff, _ = await _branch_staff(session, branch_id)
    by_code = {str(s.emp_code).strip(): s for s in staff}

    matched: list[dict] = []
    unmatched: list[str] = []
    for r in rows_iter:
        if r is None or code_col >= len(r):
            continue
        raw_code = r[code_col]
        if raw_code is None or str(raw_code).strip() == "":
            continue
        code = str(raw_code).strip()
        # Excel often stores codes as floats ("91000.0") — trim a trailing .0.
        if code.endswith(".0"):
            code = code[:-2]
        raw_bal = r[bal_col] if bal_col < len(r) else None
        try:
            balance = float(raw_bal) if raw_bal is not None and str(raw_bal).strip() != "" else 0.0
        except (TypeError, ValueError):
            balance = 0.0
        s = by_code.get(code)
        if s is None:
            unmatched.append(code)
            continue
        matched.append({
            "staff_id": str(s.id),
            "emp_code": s.emp_code,
            "name": _staff_name(s),
            "opening_balance": balance,
        })
    return {"matched": matched, "unmatched": unmatched}
