"""Accounts / Fees — Daily Follow-Up dashboard (spec §3) + auto-overdue (spec §8).

The three lists are computed from installment ``due_date`` + unpaid balance (not
from the stored OVERDUE flag), so they are correct even before the daily job runs.
``mark_overdue`` just flips the status field for reporting/profile views.
"""

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.fees.models.fee_models import (
    OVERDUE,
    PAID,
    PARTIAL,
    PENDING,
    FeeRemark,
    Installment,
    StudentFeeProfile,
)
from app.modules.student.models.student_models import Student

_CENTS = 0.01
_UNPAID = (PENDING, PARTIAL, OVERDUE)


def _balance(inst: Installment) -> float:
    return round(inst.amount - inst.paid_amount, 2)


async def mark_overdue(session: AsyncSession, branch_id: uuid.UUID, as_of: date) -> int:
    """Flip PENDING installments whose due date has passed to OVERDUE (spec §8 /
    note #7). PARTIAL rows keep their status — their unpaid balance still surfaces
    in the date-driven Overdue list. Returns the number flipped."""
    rows = (await session.execute(
        select(Installment).where(
            Installment.branch_id == branch_id,
            Installment.is_deleted == False,  # noqa: E712
            Installment.installment_status == PENDING,
            Installment.due_date < as_of,
        )
    )).scalars().all()
    for i in rows:
        i.installment_status = OVERDUE
    await session.flush()
    return len(rows)


async def _student_map(session: AsyncSession, student_ids: set) -> dict:
    """student_id -> {name, prn, phone}. Phone is the parent's number (fee calls
    go to the parent), falling back to the student's own."""
    out: dict = {}
    if not student_ids:
        return out
    for sid, first, last, enr, phone, parent in (await session.execute(
        select(Student.id, Student.first_name, Student.last_name,
               Student.enrollment_number, Student.phone, Student.parent_mobile)
        .where(Student.id.in_(student_ids))
    )).all():
        out[sid] = {
            "name": f"{first} {last}".strip(),
            "prn": enr,
            "phone": parent or phone,
        }
    return out


async def _batch_name_map(session: AsyncSession, batch_ids: set) -> dict:
    from app.modules.batch.models.batch_models import Batch

    if not batch_ids:
        return {}
    return {
        bid: name for bid, name in (await session.execute(
            select(Batch.id, Batch.name).where(Batch.id.in_(batch_ids))
        )).all()
    }


async def _latest_remark_map(session: AsyncSession, student_ids: set) -> dict:
    """student_id -> the most recent FeeRemark (by call_date, then created_at)."""
    out: dict = {}
    if not student_ids:
        return out
    rows = (await session.execute(
        select(FeeRemark).where(
            FeeRemark.student_id.in_(student_ids),
            FeeRemark.is_deleted == False,  # noqa: E712
        ).order_by(FeeRemark.call_date, FeeRemark.created_at)
    )).scalars().all()
    for r in rows:  # ascending → last write per student wins = latest
        out[r.student_id] = r
    return out


async def follow_up_dashboard(
    session: AsyncSession, branch_id: uuid.UUID, day: date,
) -> dict:
    """The Daily Follow-Up dashboard for ``day`` (spec §3): Today's Dues,
    Today's Commitments, and Overdue — each with the per-row amount, phone and
    last remark. Consolidates spec endpoints /followup/today and /overdue."""
    installments = (await session.execute(
        select(Installment).where(
            Installment.branch_id == branch_id,
            Installment.is_deleted == False,  # noqa: E712
            Installment.installment_status.in_(_UNPAID),
        )
    )).scalars().all()
    live = [i for i in installments if _balance(i) > _CENTS]

    profiles = {
        p.id: p for p in (await session.execute(
            select(StudentFeeProfile).where(
                StudentFeeProfile.id.in_({i.profile_id for i in live}),
            )
        )).scalars().all()
    } if live else {}

    # Commitments come from the latest remark per student (next_followup == day).
    student_ids = {i.student_id for i in live}
    remarks = await _latest_remark_map(session, student_ids)
    students = await _student_map(session, student_ids)
    batches = await _batch_name_map(
        session, {p.batch_id for p in profiles.values()}
    )

    def _row(inst: Installment) -> dict:
        s = students.get(inst.student_id, {})
        prof = profiles.get(inst.profile_id)
        rem = remarks.get(inst.student_id)
        return {
            "student_id": inst.student_id,
            "profile_id": inst.profile_id,
            "name": s.get("name", ""),
            "prn": s.get("prn"),
            "phone": s.get("phone"),
            "batch": batches.get(prof.batch_id) if prof else None,
            "installment_id": inst.id,
            "installment_number": inst.installment_number,
            "due_date": inst.due_date,
            "amount_due": _balance(inst),
            "days_overdue": max((day - inst.due_date).days, 0),
            "last_remark": rem.remark_text if rem else None,
            "last_remark_date": rem.call_date if rem else None,
        }

    dues = [_row(i) for i in live if i.due_date == day]
    due_today_students = {i.student_id for i in live if i.due_date == day}
    overdue = sorted(
        (_row(i) for i in live if i.due_date < day),
        key=lambda r: r["due_date"],
    )

    # Commitments: students whose latest remark promised today, shown against their
    # earliest still-unpaid installment. Excludes anyone already in Today's Dues.
    earliest_unpaid: dict = {}
    for i in sorted(live, key=lambda x: x.installment_number):
        earliest_unpaid.setdefault(i.student_id, i)
    commitments = []
    for sid, rem in remarks.items():
        if rem.next_followup_date == day and sid not in due_today_students:
            inst = earliest_unpaid.get(sid)
            if inst is not None:
                commitments.append(_row(inst))
    commitments.sort(key=lambda r: r["name"])

    def _total(rows):
        return round(sum(r["amount_due"] for r in rows), 2)

    return {
        "day": day,
        "dues": dues,
        "commitments": commitments,
        "overdue": overdue,
        "dues_total": _total(dues),
        "commitments_total": _total(commitments),
        "overdue_total": _total(overdue),
    }
