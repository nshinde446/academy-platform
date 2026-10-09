"""Accounts / Fees — collection forecast (spec §5) + staff performance (spec §8).

Manager-only reporting. "Expected" means expected *collection* — the still-unpaid
balance of installments due in the window, so already-paid installments count 0.
"""

import uuid
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models.auth_models import User
from app.modules.fees.models.fee_models import (
    PAID,
    FeeRemark,
    Installment,
    PaymentRecord,
    StudentFeeProfile,
)

_CENTS = 0.01


def _pct(collected: float, agreed: float) -> float:
    return round(collected / agreed * 100, 1) if agreed > 0 else 0.0


async def forecast_range(
    session: AsyncSession, branch_id: uuid.UUID, from_date: date, to_date: date,
) -> dict:
    """Day-wise expected collection over [from_date, to_date] (spec §5 reports 1-2).
    A single date is the range from==to. Expected = unpaid balance of installments
    due that day; count = how many such installments."""
    rows = (await session.execute(
        select(Installment).where(
            Installment.branch_id == branch_id,
            Installment.is_deleted == False,  # noqa: E712
            Installment.installment_status != PAID,
            Installment.due_date >= from_date,
            Installment.due_date <= to_date,
        )
    )).scalars().all()

    by_day: dict[date, dict] = {}
    for i in rows:
        bal = round(i.amount - i.paid_amount, 2)
        if bal <= _CENTS:
            continue
        d = by_day.setdefault(i.due_date, {"installments_due": 0, "expected_amount": 0.0})
        d["installments_due"] += 1
        d["expected_amount"] = round(d["expected_amount"] + bal, 2)

    days = [
        {"date": d, "installments_due": v["installments_due"],
         "expected_amount": v["expected_amount"]}
        for d, v in sorted(by_day.items())
    ]
    return {
        "from_date": from_date, "to_date": to_date, "days": days,
        "total_installments": sum(d["installments_due"] for d in days),
        "total_expected": round(sum(d["expected_amount"] for d in days), 2),
    }


async def _aggregate(session: AsyncSession, *where) -> dict:
    row = (await session.execute(
        select(
            func.coalesce(func.sum(StudentFeeProfile.agreed_fee), 0.0),
            func.coalesce(func.sum(StudentFeeProfile.total_paid), 0.0),
            func.coalesce(func.sum(StudentFeeProfile.total_pending), 0.0),
            func.count(StudentFeeProfile.id),
        ).where(StudentFeeProfile.is_deleted == False, *where)  # noqa: E712
    )).one()
    agreed, collected, pending, count = float(row[0]), float(row[1]), float(row[2]), int(row[3])
    return {
        "total_agreed": round(agreed, 2),
        "total_collected": round(collected, 2),
        "total_pending": round(pending, 2),
        "collection_pct": _pct(collected, agreed),
        "student_count": count,
    }


async def batch_summary(
    session: AsyncSession, branch_id: uuid.UUID, batch_id: uuid.UUID,
) -> dict:
    """Agreed / collected / pending / collection % for one batch (spec §5 report 3)."""
    out = await _aggregate(
        session,
        StudentFeeProfile.branch_id == branch_id,
        StudentFeeProfile.batch_id == batch_id,
    )
    out["batch_id"] = batch_id
    return out


async def overall_summary(session: AsyncSession, branch_id: uuid.UUID) -> dict:
    """Branch-wide collection summary card (spec §5 report 4)."""
    return await _aggregate(session, StudentFeeProfile.branch_id == branch_id)


async def staff_performance(
    session: AsyncSession, branch_id: uuid.UUID, day: date,
) -> dict:
    """Per-staff calls made and collection achieved on ``day`` (spec §8 feature 4)."""
    calls = dict((await session.execute(
        select(FeeRemark.created_by, func.count(FeeRemark.id)).where(
            FeeRemark.branch_id == branch_id,
            FeeRemark.is_deleted == False,  # noqa: E712
            FeeRemark.call_date == day,
            FeeRemark.created_by.isnot(None),
        ).group_by(FeeRemark.created_by)
    )).all())
    collected = dict((await session.execute(
        select(PaymentRecord.created_by, func.coalesce(func.sum(PaymentRecord.amount_paid), 0.0))
        .where(
            PaymentRecord.branch_id == branch_id,
            PaymentRecord.is_deleted == False,  # noqa: E712
            PaymentRecord.payment_date == day,
            PaymentRecord.created_by.isnot(None),
        ).group_by(PaymentRecord.created_by)
    )).all())

    staff_ids = set(calls) | set(collected)
    names: dict = {}
    if staff_ids:
        for uid, first, last in (await session.execute(
            select(User.id, User.first_name, User.last_name).where(User.id.in_(staff_ids))
        )).all():
            names[uid] = f"{first} {last}".strip()

    rows = [
        {
            "staff_id": uid,
            "staff_name": names.get(uid, "Unknown"),
            "calls_made": int(calls.get(uid, 0)),
            "collection": round(float(collected.get(uid, 0.0)), 2),
        }
        for uid in staff_ids
    ]
    rows.sort(key=lambda r: r["collection"], reverse=True)
    return {"day": day, "staff": rows}
