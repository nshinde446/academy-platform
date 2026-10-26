"""Monthly payroll attendance report and the per-staff ledger (§7/§4).

The report is a live preview while the month is OPEN (computed, nothing written)
and the frozen snapshot once it is CLOSED/LOCKED. One shared row shape feeds the
screen and every export so the numbers always match.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.payroll.models.payroll_models import (
    CarryForwardLedger,
    PayrollMonthSettings,
    PayrollStaffMonth,
)
from app.modules.payroll.services import ledger_service, payroll_service
from app.modules.staff.models.staff_models import Department, Staff


def _staff_name(s: Staff) -> str:
    return " ".join(p for p in (s.title, s.first_name, s.last_name) if p)


async def _staff_and_depts(
    session: AsyncSession,
    branch_id: uuid.UUID,
    *,
    department_id: uuid.UUID | None,
    staff_id: uuid.UUID | None,
) -> tuple[list[Staff], dict[uuid.UUID, str]]:
    q = select(Staff).where(
        Staff.branch_id == branch_id, Staff.is_deleted == False,  # noqa: E712
    )
    if department_id is not None:
        q = q.where(Staff.department_id == department_id)
    if staff_id is not None:
        q = q.where(Staff.id == staff_id)
    staff = list((await session.execute(q.order_by(Staff.emp_code))).scalars().all())
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


async def monthly_report(
    session: AsyncSession,
    *,
    branch_id: uuid.UUID,
    year: int,
    month: int,
    department_id: uuid.UUID | None = None,
    staff_id: uuid.UUID | None = None,
) -> dict:
    settings = (await session.execute(
        select(PayrollMonthSettings).where(
            PayrollMonthSettings.branch_id == branch_id,
            PayrollMonthSettings.year == year,
            PayrollMonthSettings.month == month,
            PayrollMonthSettings.is_deleted == False,  # noqa: E712
        )
    )).scalar_one_or_none()
    lifecycle = settings.lifecycle if settings else "NOT_SET"

    staff, depts = await _staff_and_depts(
        session, branch_id, department_id=department_id, staff_id=staff_id
    )
    staff_ids = {s.id for s in staff}

    # Frozen snapshot for a finalised month; live preview otherwise.
    data: dict[uuid.UUID, dict] = {}
    if lifecycle in ("CLOSED", "LOCKED"):
        snaps = (await session.execute(
            select(PayrollStaffMonth).where(
                PayrollStaffMonth.branch_id == branch_id,
                PayrollStaffMonth.year == year,
                PayrollStaffMonth.month == month,
            )
        )).scalars().all()
        for sn in snaps:
            if sn.staff_id in staff_ids:
                data[sn.staff_id] = {
                    "required_days": float(sn.required_days),
                    "present_days": float(sn.present_days),
                    "half_days": sn.half_days,
                    "paid_leave_days": float(sn.paid_leave_days),
                    "net_days": float(sn.net_days),
                    "balance_in": float(sn.balance_in),
                    "balance_out": float(sn.balance_out),
                    "uncovered_days": float(sn.uncovered_days),
                    "deferred_days": float(sn.deferred_days),
                    "late_fine_total": float(sn.late_fine_total),
                }
    else:
        for comp in await payroll_service.preview_month(
            session, branch_id=branch_id, year=year, month=month
        ):
            if comp.staff_id in staff_ids:
                data[comp.staff_id] = {
                    "required_days": comp.required_days,
                    "present_days": comp.present_days,
                    "half_days": comp.half_days,
                    "paid_leave_days": comp.paid_leave_days,
                    "net_days": comp.net_days,
                    "balance_in": comp.balance_in,
                    "balance_out": comp.balance_out,
                    "uncovered_days": comp.uncovered_days,
                    "deferred_days": 0.0,
                    "late_fine_total": comp.late_fine_total,
                }

    rows: list[dict] = []
    for s in staff:
        d = data.get(s.id, {})
        rows.append({
            "staff_id": str(s.id),
            "emp_code": s.emp_code,
            "name": _staff_name(s),
            "department": depts.get(s.department_id, "—"),
            "required_days": d.get("required_days", float(settings.required_days) if settings else 0.0),
            "present_days": d.get("present_days", 0.0),
            "half_days": d.get("half_days", 0),
            "paid_leave_days": d.get("paid_leave_days", 0.0),
            "net_days": d.get("net_days", 0.0),
            "balance_in": d.get("balance_in", 0.0),
            "balance_out": d.get("balance_out", 0.0),
            "uncovered_days": d.get("uncovered_days", 0.0),
            "deferred_days": d.get("deferred_days", 0.0),
            "late_fine_total": d.get("late_fine_total", 0.0),
        })

    totals = {
        "staff_count": len(rows),
        "present_days": round(sum(r["present_days"] for r in rows), 1),
        "uncovered_days": round(sum(r["uncovered_days"] for r in rows), 1),
        "late_fine_total": round(sum(r["late_fine_total"] for r in rows), 2),
    }
    return {"year": year, "month": month, "lifecycle": lifecycle, "rows": rows, "totals": totals}


async def staff_ledger(
    session: AsyncSession, *, branch_id: uuid.UUID, staff_id: uuid.UUID
) -> dict:
    staff = (await session.execute(
        select(Staff).where(Staff.id == staff_id, Staff.is_deleted == False)  # noqa: E712
    )).scalar_one_or_none()
    if staff is None or staff.branch_id != branch_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Staff not found in this branch")

    entries = (await session.execute(
        select(CarryForwardLedger).where(
            CarryForwardLedger.staff_id == staff_id,
            CarryForwardLedger.branch_id == branch_id,
        ).order_by(CarryForwardLedger.seq)
    )).scalars().all()

    # Resolve "who" names for the created_by column.
    names = await _user_names(session, {e.created_by for e in entries if e.created_by})

    return {
        "staff_id": str(staff.id),
        "emp_code": staff.emp_code,
        "name": _staff_name(staff),
        "current_balance": await ledger_service.current_balance(session, staff_id),
        "rows": [
            {
                "year": e.year, "month": e.month, "seq": e.seq,
                "entry_type": e.entry_type, "days": float(e.days),
                "running_balance": float(e.running_balance), "note": e.note,
                "created_by": names.get(e.created_by),
                "created_at": e.created_at,
            }
            for e in entries
        ],
    }


async def _user_names(
    session: AsyncSession, user_ids: set[uuid.UUID]
) -> dict[uuid.UUID, str]:
    if not user_ids:
        return {}
    from app.modules.auth.models.auth_models import User

    return {
        uid: f"{fn} {ln}".strip()
        for uid, fn, ln in (await session.execute(
            select(User.id, User.first_name, User.last_name).where(User.id.in_(user_ids))
        )).all()
    }
