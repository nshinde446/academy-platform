"""Accounts / Fees — business logic (slice 1: course fee config + create profile).

Installment dates follow spec §2.3: installment ``n`` falls on
``admission_date + (n-1) × interval`` where the default interval is 2.5 months —
add the whole months, then +15 days for the half.
"""

import calendar
import uuid
from datetime import date, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.services import audit_service
from app.modules.fees.models.fee_models import (
    INSTALLMENT,
    ONE_TIME,
    PAID,
    PARTIAL,
    PAYMENT_MODES,
    PENDING,
    CourseFeeConfig,
    FeeRemark,
    Installment,
    PaymentRecord,
    StudentFeeProfile,
)
from app.modules.student.models.student_models import Student

_CENTS = 0.01  # float tolerance for the "installments must sum to agreed fee" check


def _add_months(d: date, months: int) -> date:
    """``d`` shifted by whole months, clamping the day to the target month."""
    m = d.month - 1 + months
    year = d.year + m // 12
    month = m % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _installment_due_date(admission: date, n: int, interval_months: float = 2.5) -> date:
    """Due date of installment ``n`` (1-based). Whole months, then +15 days for a
    half-month remainder (spec §2.3)."""
    steps = (n - 1) * interval_months
    whole = int(steps)
    due = _add_months(admission, whole)
    if steps - whole >= 0.5:
        due = due + timedelta(days=15)
    return due


def _even_split(total: float, parts: int) -> list[float]:
    """Split ``total`` into ``parts`` amounts that sum exactly to it — equal
    (rounded to the rupee) with the last absorbing the remainder."""
    base = round(total / parts)
    amounts = [float(base)] * (parts - 1)
    amounts.append(round(total - base * (parts - 1), 2))
    return amounts


# ── Course fee config (spec §1) ──────────────────────────────────────────────

async def list_course_fees(session: AsyncSession, branch_id: uuid.UUID) -> list[CourseFeeConfig]:
    return list((await session.execute(
        select(CourseFeeConfig).where(
            CourseFeeConfig.branch_id == branch_id,
            CourseFeeConfig.is_deleted == False,  # noqa: E712
        ).order_by(CourseFeeConfig.course_name)
    )).scalars().all())


async def upsert_course_fee(
    session: AsyncSession, *, branch_id: uuid.UUID, course_name: str,
    standard_fee: float, user_id: uuid.UUID, ip_address: str | None = None,
) -> CourseFeeConfig:
    """Set/replace the standard fee for a course in a branch (one live row per
    branch+course). Changing it affects only new admissions (spec §1 note)."""
    if standard_fee < 0:
        raise HTTPException(status_code=422, detail="Standard fee cannot be negative")
    name = course_name.strip()
    existing = (await session.execute(
        select(CourseFeeConfig).where(
            CourseFeeConfig.branch_id == branch_id,
            CourseFeeConfig.course_name == name,
            CourseFeeConfig.is_deleted == False,  # noqa: E712
        )
    )).scalar_one_or_none()
    if existing:
        existing.standard_fee = standard_fee
        existing.updated_by = user_id
        row = existing
    else:
        row = CourseFeeConfig(
            branch_id=branch_id, course_name=name, standard_fee=standard_fee,
            created_by=user_id,
        )
        session.add(row)
    await session.flush()
    await audit_service.log_action(
        session, user_id=user_id, action="UPSERT", table_name="course_fee_configs",
        record_id=row.id, new_values={"course_name": name, "standard_fee": standard_fee},
        ip_address=ip_address, branch_id=branch_id,
    )
    return row


# ── Student fee profile (spec §2) ────────────────────────────────────────────

def _build_installments(data: dict, agreed_fee: float) -> list[dict]:
    """Return the installment rows (dicts) for a profile, before persistence.

    ONE_TIME → a single PAID row at admission. INSTALLMENT → the explicit plan if
    given, else an auto-generated 2.5-month schedule from first_installment +
    remaining_installments. Raises 422 unless the amounts sum to the agreed fee."""
    admission = data["admission_date"]
    mode = data["payment_mode"]

    if mode == ONE_TIME:
        return [{
            "installment_number": 1, "due_date": admission, "amount": agreed_fee,
            "installment_status": PAID, "paid_amount": agreed_fee, "paid_date": admission,
        }]

    explicit = data.get("installments")
    if explicit:
        rows = [{
            "installment_number": i.get("number", idx + 1),
            "due_date": i["due_date"], "amount": float(i["amount"]),
            "installment_status": PENDING, "paid_amount": 0.0, "paid_date": None,
        } for idx, i in enumerate(explicit)]
    else:
        first = data.get("first_installment")
        remaining = data.get("remaining_installments")
        if first is None or remaining is None:
            raise HTTPException(
                status_code=422,
                detail="Installment mode needs either `installments` or "
                       "`first_installment` + `remaining_installments`",
            )
        interval = data.get("interval_months") or 2.5
        rows = [{
            "installment_number": 1, "due_date": admission, "amount": float(first),
            "installment_status": PENDING, "paid_amount": 0.0, "paid_date": None,
        }]
        if remaining > 0:
            for n, amt in enumerate(_even_split(agreed_fee - first, remaining), start=2):
                rows.append({
                    "installment_number": n,
                    "due_date": _installment_due_date(admission, n, interval),
                    "amount": amt, "installment_status": PENDING,
                    "paid_amount": 0.0, "paid_date": None,
                })

    total = round(sum(r["amount"] for r in rows), 2)
    if abs(total - agreed_fee) > _CENTS:
        raise HTTPException(
            status_code=422,
            detail=f"Installments total {total} must equal the agreed fee {agreed_fee}",
        )
    return rows


async def create_fee_profile(
    session: AsyncSession, data: dict, branch_id: uuid.UUID,
    user_id: uuid.UUID, ip_address: str | None = None,
) -> StudentFeeProfile:
    """Create a student's fee profile + its installment schedule at admission
    (spec §2). One profile per student. Idempotency is the caller's concern —
    a second create for the same student is rejected."""
    student = (await session.execute(
        select(Student).where(
            Student.id == data["student_id"], Student.is_deleted == False,  # noqa: E712
        )
    )).scalar_one_or_none()
    if student is None or student.branch_id != branch_id:
        raise HTTPException(status_code=404, detail="Student not found in this branch")

    mode = data["payment_mode"]
    if mode not in (ONE_TIME, INSTALLMENT):
        raise HTTPException(status_code=422, detail="payment_mode must be ONE_TIME or INSTALLMENT")

    actual_fee = float(data["actual_fee"])
    agreed_fee = float(data["agreed_fee"])
    if agreed_fee > actual_fee:
        raise HTTPException(status_code=422, detail="Agreed fee cannot exceed the actual fee")
    if agreed_fee <= 0:
        raise HTTPException(status_code=422, detail="Agreed fee must be greater than 0")

    existing = (await session.execute(
        select(StudentFeeProfile).where(
            StudentFeeProfile.student_id == data["student_id"],
            StudentFeeProfile.is_deleted == False,  # noqa: E712
        )
    )).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="This student already has a fee profile")

    installment_rows = _build_installments(data, agreed_fee)
    paid = round(sum(r["paid_amount"] for r in installment_rows), 2)

    profile = StudentFeeProfile(
        student_id=data["student_id"], branch_id=branch_id, batch_id=data["batch_id"],
        actual_fee=actual_fee, agreed_fee=agreed_fee,
        discount_amount=round(actual_fee - agreed_fee, 2), payment_mode=mode,
        total_paid=paid, total_pending=round(agreed_fee - paid, 2),
        admission_date=data["admission_date"], created_by=user_id,
    )
    session.add(profile)
    await session.flush()

    for r in installment_rows:
        session.add(Installment(
            profile_id=profile.id, student_id=data["student_id"], branch_id=branch_id,
            payment_mode=r.get("payment_mode"), created_by=user_id, **{
                k: r[k] for k in (
                    "installment_number", "due_date", "amount",
                    "installment_status", "paid_amount", "paid_date",
                )
            },
        ))
    await session.flush()

    await audit_service.log_action(
        session, user_id=user_id, action="CREATE", table_name="student_fee_profiles",
        record_id=profile.id,
        new_values={"student_id": str(data["student_id"]), "agreed_fee": agreed_fee,
                    "payment_mode": mode, "installments": len(installment_rows)},
        ip_address=ip_address, branch_id=branch_id,
    )
    # Transient attribute for the response model (no ORM relationship needed).
    profile.installments = await _installments_for(session, profile.id)
    return profile


async def _installments_for(session: AsyncSession, profile_id: uuid.UUID) -> list[Installment]:
    return list((await session.execute(
        select(Installment).where(
            Installment.profile_id == profile_id, Installment.is_deleted == False,  # noqa: E712
        ).order_by(Installment.installment_number)
    )).scalars().all())


async def get_fee_profile(
    session: AsyncSession, student_id: uuid.UUID, branch_id: uuid.UUID,
) -> StudentFeeProfile:
    """A student's fee profile + ordered installments (spec §7, slice-1 read)."""
    profile = (await session.execute(
        select(StudentFeeProfile).where(
            StudentFeeProfile.student_id == student_id,
            StudentFeeProfile.is_deleted == False,  # noqa: E712
        )
    )).scalar_one_or_none()
    if profile is None:
        raise HTTPException(status_code=404, detail="No fee profile for this student")
    if profile.branch_id != branch_id:
        raise HTTPException(status_code=403, detail="No access to this branch")
    profile.installments = await _installments_for(session, profile.id)
    # Call log, newest first — powers the profile view's remarks history (spec §7).
    profile.remarks = list((await session.execute(
        select(FeeRemark).where(
            FeeRemark.profile_id == profile.id, FeeRemark.is_deleted == False,  # noqa: E712
        ).order_by(FeeRemark.call_date.desc(), FeeRemark.created_at.desc())
    )).scalars().all())
    return profile


# ── Payments (spec §6) + remarks (spec §4) ───────────────────────────────────

async def record_payment(
    session: AsyncSession, installment_id: uuid.UUID, branch_id: uuid.UUID,
    *, amount_paid: float, payment_date: date, payment_mode: str,
    notes: str | None, user_id: uuid.UUID, ip_address: str | None = None,
) -> dict:
    """Record a payment against an installment (spec §6). Partial payments keep
    the balance on the same installment (status PARTIAL); a full payment marks it
    PAID. The profile's totals are updated. A payment above the installment's
    remaining balance is rejected (developer-note #4, applied per installment)."""
    mode = (payment_mode or "").upper()
    if mode not in PAYMENT_MODES:
        raise HTTPException(status_code=422, detail=f"payment_mode must be one of {sorted(PAYMENT_MODES)}")
    if amount_paid <= 0:
        raise HTTPException(status_code=422, detail="Amount paid must be greater than 0")

    inst = (await session.execute(
        select(Installment).where(
            Installment.id == installment_id, Installment.is_deleted == False,  # noqa: E712
        )
    )).scalar_one_or_none()
    if inst is None or inst.branch_id != branch_id:
        raise HTTPException(status_code=404, detail="Installment not found in this branch")
    if inst.installment_status == PAID:
        raise HTTPException(status_code=409, detail="This installment is already fully paid")

    balance = round(inst.amount - inst.paid_amount, 2)
    if amount_paid - balance > _CENTS:
        raise HTTPException(
            status_code=422,
            detail=f"Payment {amount_paid} exceeds this installment's balance {balance}",
        )

    profile = (await session.execute(
        select(StudentFeeProfile).where(StudentFeeProfile.id == inst.profile_id)
    )).scalar_one()

    session.add(PaymentRecord(
        student_id=inst.student_id, installment_id=inst.id, branch_id=branch_id,
        amount_paid=amount_paid, payment_date=payment_date, payment_mode=mode,
        notes=notes, created_by=user_id,
    ))

    inst.paid_amount = round(inst.paid_amount + amount_paid, 2)
    inst.payment_mode = mode
    inst.paid_date = payment_date
    inst.installment_status = PAID if inst.paid_amount >= inst.amount - _CENTS else PARTIAL

    profile.total_paid = round(profile.total_paid + amount_paid, 2)
    profile.total_pending = round(profile.total_pending - amount_paid, 2)
    profile.updated_by = user_id
    await session.flush()

    await audit_service.log_action(
        session, user_id=user_id, action="PAYMENT", table_name="fee_payment_records",
        record_id=inst.id,
        new_values={"amount_paid": amount_paid, "mode": mode,
                    "installment_status": inst.installment_status},
        ip_address=ip_address, branch_id=branch_id,
    )
    return {
        "installment": inst,
        "total_paid": profile.total_paid,
        "total_pending": profile.total_pending,
    }


async def add_remark(
    session: AsyncSession, data: dict, branch_id: uuid.UUID,
    user_id: uuid.UUID, ip_address: str | None = None,
) -> FeeRemark:
    """Add a call-log remark (spec §4). A next follow-up date is required unless
    the fee is fully paid (developer-note #5); when given, the student shows up in
    that day's Commitments list (built in slice 3)."""
    profile = (await session.execute(
        select(StudentFeeProfile).where(
            StudentFeeProfile.id == data["profile_id"],
            StudentFeeProfile.is_deleted == False,  # noqa: E712
        )
    )).scalar_one_or_none()
    if profile is None or profile.branch_id != branch_id:
        raise HTTPException(status_code=404, detail="Fee profile not found in this branch")
    if profile.student_id != data["student_id"]:
        raise HTTPException(status_code=422, detail="student_id does not match this profile")

    if data.get("next_followup_date") is None and profile.total_pending > _CENTS:
        raise HTTPException(
            status_code=422,
            detail="A next follow-up date is required until the fee is fully paid",
        )

    remark = FeeRemark(
        student_id=data["student_id"], profile_id=data["profile_id"], branch_id=branch_id,
        remark_text=data["remark_text"], call_date=data["call_date"],
        next_followup_date=data.get("next_followup_date"), created_by=user_id,
    )
    session.add(remark)
    await session.flush()

    await audit_service.log_action(
        session, user_id=user_id, action="REMARK", table_name="fee_remarks",
        record_id=remark.id,
        new_values={"next_followup_date": str(data.get("next_followup_date"))},
        ip_address=ip_address, branch_id=branch_id,
    )
    return remark
