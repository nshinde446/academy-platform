"""Accounts / Fees module — slice 1: course fee config + create fee profile.

Covers the installment auto-calc (2.5-month rule), ONE_TIME vs INSTALLMENT,
the "installments must sum to the agreed fee" guard, discount, and totals.
"""

from datetime import date

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.fees.services import fee_service

ADMISSION = date(2026, 10, 8)


def _profile_args(seed_data, **overrides):
    base = {
        "student_id": seed_data["student"].id,
        "batch_id": seed_data["batch"].id,
        "actual_fee": 160000.0,
        "agreed_fee": 150000.0,
        "payment_mode": "INSTALLMENT",
        "admission_date": ADMISSION,
        "installments": None,
        "first_installment": 50000.0,
        "remaining_installments": 4,
        "interval_months": 2.5,
    }
    base.update(overrides)
    return base


async def _create(db_session, seed_data, **overrides):
    return await fee_service.create_fee_profile(
        db_session, _profile_args(seed_data, **overrides),
        branch_id=seed_data["branch_a"].id, user_id=seed_data["admin_user"].id,
    )


@pytest.mark.usefixtures("seed_data")
async def test_upsert_course_fee_creates_then_updates(db_session: AsyncSession, seed_data):
    b = seed_data["branch_a"].id
    uid = seed_data["admin_user"].id
    row = await fee_service.upsert_course_fee(
        db_session, branch_id=b, course_name="CET", standard_fee=160000, user_id=uid,
    )
    assert row.standard_fee == 160000
    # Same branch+course upserts (no duplicate row).
    again = await fee_service.upsert_course_fee(
        db_session, branch_id=b, course_name="CET", standard_fee=165000, user_id=uid,
    )
    assert again.id == row.id and again.standard_fee == 165000
    fees = await fee_service.list_course_fees(db_session, b)
    assert len(fees) == 1


@pytest.mark.usefixtures("seed_data")
async def test_installment_profile_auto_schedule(db_session: AsyncSession, seed_data):
    profile = await _create(db_session, seed_data)  # 50k + 4×25k = 150k
    assert profile.discount_amount == 10000
    assert profile.total_paid == 0 and profile.total_pending == 150000
    inst = profile.installments
    assert [i.installment_number for i in inst] == [1, 2, 3, 4, 5]
    # 2.5-month schedule from 8 Oct (spec §2.3).
    assert [i.due_date.isoformat() for i in inst] == [
        "2026-10-08", "2026-12-23", "2027-03-08", "2027-05-23", "2027-08-08",
    ]
    assert [i.amount for i in inst] == [50000, 25000, 25000, 25000, 25000]
    assert all(i.installment_status == "PENDING" for i in inst)


@pytest.mark.usefixtures("seed_data")
async def test_one_time_profile_single_paid_installment(db_session: AsyncSession, seed_data):
    profile = await _create(
        db_session, seed_data, payment_mode="ONE_TIME",
        first_installment=None, remaining_installments=None, installments=None,
    )
    assert profile.total_paid == 150000 and profile.total_pending == 0
    assert len(profile.installments) == 1
    only = profile.installments[0]
    assert only.installment_status == "PAID"
    assert only.amount == 150000 and only.paid_amount == 150000
    assert only.due_date == ADMISSION and only.paid_date == ADMISSION


@pytest.mark.usefixtures("seed_data")
async def test_explicit_installments_used_as_given(db_session: AsyncSession, seed_data):
    plan = [
        {"number": 1, "due_date": date(2026, 10, 8), "amount": 60000},
        {"number": 2, "due_date": date(2026, 11, 8), "amount": 45000},
        {"number": 3, "due_date": date(2026, 12, 8), "amount": 45000},
    ]
    profile = await _create(
        db_session, seed_data, installments=plan,
        first_installment=None, remaining_installments=None,
    )
    assert [i.amount for i in profile.installments] == [60000, 45000, 45000]
    assert [i.due_date.isoformat() for i in profile.installments] == [
        "2026-10-08", "2026-11-08", "2026-12-08",
    ]


@pytest.mark.usefixtures("seed_data")
async def test_installments_must_sum_to_agreed_fee(db_session: AsyncSession, seed_data):
    bad = [
        {"number": 1, "due_date": date(2026, 10, 8), "amount": 50000},
        {"number": 2, "due_date": date(2026, 12, 23), "amount": 50000},
    ]  # sums to 100000, not 150000
    with pytest.raises(HTTPException) as ei:
        await _create(db_session, seed_data, installments=bad,
                      first_installment=None, remaining_installments=None)
    assert ei.value.status_code == 422
    assert "equal the agreed fee" in ei.value.detail


@pytest.mark.usefixtures("seed_data")
async def test_agreed_above_actual_rejected(db_session: AsyncSession, seed_data):
    with pytest.raises(HTTPException) as ei:
        await _create(db_session, seed_data, actual_fee=150000, agreed_fee=160000)
    assert ei.value.status_code == 422


@pytest.mark.usefixtures("seed_data")
async def test_duplicate_profile_rejected(db_session: AsyncSession, seed_data):
    await _create(db_session, seed_data)
    with pytest.raises(HTTPException) as ei:
        await _create(db_session, seed_data)
    assert ei.value.status_code == 409


@pytest.mark.usefixtures("seed_data")
async def test_get_fee_profile_returns_installments(db_session: AsyncSession, seed_data):
    await _create(db_session, seed_data)
    got = await fee_service.get_fee_profile(
        db_session, seed_data["student"].id, seed_data["branch_a"].id,
    )
    assert got.agreed_fee == 150000
    assert len(got.installments) == 5


@pytest.mark.usefixtures("seed_data")
async def test_void_profile_allows_recreate(db_session: AsyncSession, seed_data):
    sid = seed_data["student"].id
    b = seed_data["branch_a"].id
    await _create(db_session, seed_data)
    await fee_service.void_fee_profile(db_session, sid, b, seed_data["admin_user"].id)
    # Gone: read now 404s.
    with pytest.raises(HTTPException) as ei:
        await fee_service.get_fee_profile(db_session, sid, b)
    assert ei.value.status_code == 404
    # The "one profile per student" guard no longer blocks a fresh profile.
    again = await _create(db_session, seed_data, agreed_fee=120000)
    assert again.agreed_fee == 120000
    # Voiding when there is no live profile → 404.
    await fee_service.void_fee_profile(db_session, sid, b, seed_data["admin_user"].id)
    with pytest.raises(HTTPException) as ei2:
        await fee_service.void_fee_profile(db_session, sid, b, seed_data["admin_user"].id)
    assert ei2.value.status_code == 404
