"""Accounts / Fees — slice 4: collection forecast + batch/overall summary + staff perf."""

import uuid
from datetime import date

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.fees.models.fee_models import Installment
from app.modules.fees.services import fee_service, forecast_service
from app.modules.student.models.student_models import Student, StudentBatchMapping


async def _student(db_session, seed_data, enr, batch_id) -> uuid.UUID:
    s = Student(
        id=uuid.uuid4(), branch_id=seed_data["branch_a"].id,
        academic_year_id=seed_data["academic_year"].id,
        first_name=enr, last_name="S", enrollment_number=enr,
        status="active", is_deleted=False,
    )
    db_session.add(s)
    db_session.add(StudentBatchMapping(
        student_id=s.id, batch_id=batch_id, branch_id=seed_data["branch_a"].id,
        status="active", is_deleted=False,
    ))
    await db_session.flush()
    return s.id


async def _profile(db_session, seed_data, student_id, batch_id, plan, agreed):
    return await fee_service.create_fee_profile(
        db_session,
        {
            "student_id": student_id, "batch_id": batch_id,
            "actual_fee": agreed + 10000, "agreed_fee": agreed,
            "payment_mode": "INSTALLMENT", "admission_date": date(2026, 9, 1),
            "installments": plan,
        },
        branch_id=seed_data["branch_a"].id, user_id=seed_data["admin_user"].id,
    )


@pytest.mark.usefixtures("seed_data")
async def test_forecast_range_day_wise_expected(db_session: AsyncSession, seed_data):
    b = seed_data["branch_a"].id
    s1 = await _student(db_session, seed_data, "FC001", seed_data["batch"].id)
    s2 = await _student(db_session, seed_data, "FC002", seed_data["batch"].id)
    await _profile(db_session, seed_data, s1, seed_data["batch"].id, [
        {"number": 1, "due_date": date(2026, 10, 20), "amount": 30000},
        {"number": 2, "due_date": date(2026, 10, 23), "amount": 20000},
    ], 50000)
    await _profile(db_session, seed_data, s2, seed_data["batch"].id, [
        {"number": 1, "due_date": date(2026, 10, 23), "amount": 40000},
    ], 40000)

    fc = await forecast_service.forecast_range(
        db_session, b, date(2026, 10, 20), date(2026, 10, 24),
    )
    by_date = {d["date"].isoformat(): d for d in fc["days"]}
    assert by_date["2026-10-20"]["expected_amount"] == 30000
    assert by_date["2026-10-23"]["installments_due"] == 2
    assert by_date["2026-10-23"]["expected_amount"] == 60000  # 20000 + 40000
    assert fc["total_expected"] == 90000 and fc["total_installments"] == 3


@pytest.mark.usefixtures("seed_data")
async def test_forecast_excludes_paid_balance(db_session: AsyncSession, seed_data):
    b = seed_data["branch_a"].id
    s1 = await _student(db_session, seed_data, "FC010", seed_data["batch"].id)
    await _profile(db_session, seed_data, s1, seed_data["batch"].id, [
        {"number": 1, "due_date": date(2026, 10, 23), "amount": 30000},
    ], 30000)
    inst = (await db_session.execute(
        Installment.__table__.select().where(Installment.student_id == s1)
    )).first()
    # Partially pay 10k → only the 20k balance is "expected".
    await fee_service.record_payment(
        db_session, inst.id, b, amount_paid=10000, payment_date=date(2026, 10, 23),
        payment_mode="UPI", notes=None, user_id=seed_data["admin_user"].id,
    )
    fc = await forecast_service.forecast_range(db_session, b, date(2026, 10, 23), date(2026, 10, 23))
    assert fc["total_expected"] == 20000


@pytest.mark.usefixtures("seed_data")
async def test_batch_and_overall_summary(db_session: AsyncSession, seed_data):
    b = seed_data["branch_a"].id
    a_batch = seed_data["batch"].id
    b_batch = seed_data["batch_b"].id
    s1 = await _student(db_session, seed_data, "FC100", a_batch)
    s2 = await _student(db_session, seed_data, "FC101", b_batch)
    await _profile(db_session, seed_data, s1, a_batch, [
        {"number": 1, "due_date": date(2026, 10, 1), "amount": 100000},
    ], 100000)
    await _profile(db_session, seed_data, s2, b_batch, [
        {"number": 1, "due_date": date(2026, 10, 1), "amount": 50000},
    ], 50000)
    inst1 = (await db_session.execute(
        Installment.__table__.select().where(Installment.student_id == s1)
    )).first()
    await fee_service.record_payment(
        db_session, inst1.id, b, amount_paid=60000, payment_date=date(2026, 10, 1),
        payment_mode="CASH", notes=None, user_id=seed_data["admin_user"].id,
    )

    batch = await forecast_service.batch_summary(db_session, b, a_batch)
    assert batch["total_agreed"] == 100000 and batch["total_collected"] == 60000
    assert batch["total_pending"] == 40000 and batch["collection_pct"] == 60.0
    assert batch["batch_id"] == a_batch

    overall = await forecast_service.overall_summary(db_session, b)
    assert overall["total_agreed"] == 150000  # 100k + 50k
    assert overall["total_collected"] == 60000
    assert overall["collection_pct"] == 40.0  # 60000 / 150000
    assert overall["student_count"] == 2


@pytest.mark.usefixtures("seed_data")
async def test_staff_performance(db_session: AsyncSession, seed_data):
    b = seed_data["branch_a"].id
    uid = seed_data["admin_user"].id
    day = date(2026, 10, 23)
    s1 = await _student(db_session, seed_data, "FC200", seed_data["batch"].id)
    p = await _profile(db_session, seed_data, s1, seed_data["batch"].id, [
        {"number": 1, "due_date": day, "amount": 30000},
    ], 30000)
    inst = (await db_session.execute(
        Installment.__table__.select().where(Installment.student_id == s1)
    )).first()
    await fee_service.record_payment(
        db_session, inst.id, b, amount_paid=30000, payment_date=day,
        payment_mode="UPI", notes=None, user_id=uid,
    )
    await fee_service.add_remark(db_session, {
        "student_id": s1, "profile_id": p.id, "remark_text": "Paid in full",
        "call_date": day, "next_followup_date": None,
    }, b, uid)

    perf = await forecast_service.staff_performance(db_session, b, day)
    me = next(r for r in perf["staff"] if r["staff_id"] == uid)
    assert me["calls_made"] == 1 and me["collection"] == 30000
    # A different day → nothing for this staff.
    empty = await forecast_service.staff_performance(db_session, b, date(2026, 10, 24))
    assert all(r["staff_id"] != uid for r in empty["staff"])
