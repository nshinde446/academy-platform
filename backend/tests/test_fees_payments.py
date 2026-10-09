"""Accounts / Fees — slice 2: payment recording + remarks/call log."""

from datetime import date

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.fees.services import fee_service

ADMISSION = date(2026, 10, 8)
PAY_DAY = date(2026, 10, 8)


async def _profile(db_session, seed_data):
    return await fee_service.create_fee_profile(
        db_session,
        {
            "student_id": seed_data["student"].id, "batch_id": seed_data["batch"].id,
            "actual_fee": 160000.0, "agreed_fee": 150000.0,
            "payment_mode": "INSTALLMENT", "admission_date": ADMISSION,
            "first_installment": 50000.0, "remaining_installments": 4,
        },
        branch_id=seed_data["branch_a"].id, user_id=seed_data["admin_user"].id,
    )


async def _pay(db_session, seed_data, inst_id, amount, mode="UPI"):
    return await fee_service.record_payment(
        db_session, inst_id, seed_data["branch_a"].id,
        amount_paid=amount, payment_date=PAY_DAY, payment_mode=mode, notes=None,
        user_id=seed_data["admin_user"].id,
    )


@pytest.mark.usefixtures("seed_data")
async def test_full_payment_marks_paid_and_updates_totals(db_session: AsyncSession, seed_data):
    p = await _profile(db_session, seed_data)
    first = p.installments[0]  # 50000
    res = await _pay(db_session, seed_data, first.id, 50000, mode="CASH")
    assert res["installment"].installment_status == "PAID"
    assert res["installment"].paid_amount == 50000
    assert res["installment"].payment_mode == "CASH"
    assert res["total_paid"] == 50000 and res["total_pending"] == 100000


@pytest.mark.usefixtures("seed_data")
async def test_partial_then_full_payment(db_session: AsyncSession, seed_data):
    p = await _profile(db_session, seed_data)
    inst = p.installments[1]  # 25000
    r1 = await _pay(db_session, seed_data, inst.id, 15000)
    assert r1["installment"].installment_status == "PARTIAL"
    assert r1["installment"].paid_amount == 15000
    assert r1["total_pending"] == 135000  # 150000 - 15000
    r2 = await _pay(db_session, seed_data, inst.id, 10000)  # balance
    assert r2["installment"].installment_status == "PAID"
    assert r2["installment"].paid_amount == 25000
    assert r2["total_pending"] == 125000


@pytest.mark.usefixtures("seed_data")
async def test_overpayment_beyond_installment_rejected(db_session: AsyncSession, seed_data):
    p = await _profile(db_session, seed_data)
    inst = p.installments[1]  # 25000
    with pytest.raises(HTTPException) as ei:
        await _pay(db_session, seed_data, inst.id, 30000)
    assert ei.value.status_code == 422
    assert "exceeds" in ei.value.detail


@pytest.mark.usefixtures("seed_data")
async def test_paying_a_paid_installment_rejected(db_session: AsyncSession, seed_data):
    p = await _profile(db_session, seed_data)
    inst = p.installments[0]
    await _pay(db_session, seed_data, inst.id, 50000)
    with pytest.raises(HTTPException) as ei:
        await _pay(db_session, seed_data, inst.id, 1)
    assert ei.value.status_code == 409


@pytest.mark.usefixtures("seed_data")
async def test_invalid_payment_mode_rejected(db_session: AsyncSession, seed_data):
    p = await _profile(db_session, seed_data)
    with pytest.raises(HTTPException) as ei:
        await _pay(db_session, seed_data, p.installments[0].id, 50000, mode="CARD")
    assert ei.value.status_code == 422


@pytest.mark.usefixtures("seed_data")
async def test_remark_requires_followup_until_fully_paid(db_session: AsyncSession, seed_data):
    p = await _profile(db_session, seed_data)
    b = seed_data["branch_a"].id
    uid = seed_data["admin_user"].id
    # No follow-up date while fees are pending → rejected.
    with pytest.raises(HTTPException) as ei:
        await fee_service.add_remark(db_session, {
            "student_id": seed_data["student"].id, "profile_id": p.id,
            "remark_text": "Called, no answer", "call_date": PAY_DAY,
            "next_followup_date": None,
        }, b, uid)
    assert ei.value.status_code == 422

    # With a follow-up date → created.
    r = await fee_service.add_remark(db_session, {
        "student_id": seed_data["student"].id, "profile_id": p.id,
        "remark_text": "Parent will pay on 15 Oct", "call_date": PAY_DAY,
        "next_followup_date": date(2026, 10, 15),
    }, b, uid)
    assert r.next_followup_date == date(2026, 10, 15)
    assert r.created_by == uid


@pytest.mark.usefixtures("seed_data")
async def test_remark_followup_optional_when_fully_paid(db_session: AsyncSession, seed_data):
    # One-time fully-paid profile → a remark may omit the follow-up date.
    p = await fee_service.create_fee_profile(
        db_session, {
            "student_id": seed_data["student"].id, "batch_id": seed_data["batch"].id,
            "actual_fee": 160000.0, "agreed_fee": 150000.0,
            "payment_mode": "ONE_TIME", "admission_date": ADMISSION,
        },
        branch_id=seed_data["branch_a"].id, user_id=seed_data["admin_user"].id,
    )
    r = await fee_service.add_remark(db_session, {
        "student_id": seed_data["student"].id, "profile_id": p.id,
        "remark_text": "Fully paid, courtesy call", "call_date": PAY_DAY,
        "next_followup_date": None,
    }, seed_data["branch_a"].id, seed_data["admin_user"].id)
    assert r.next_followup_date is None
