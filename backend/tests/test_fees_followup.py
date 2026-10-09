"""Accounts / Fees — slice 3: Daily Follow-Up dashboard + auto-overdue sweep."""

import uuid
from datetime import date, datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.fees.jobs import tasks as fee_tasks
from app.modules.fees.models.fee_models import Installment
from app.modules.fees.services import fee_service, followup_service
from app.modules.student.models.student_models import Student, StudentBatchMapping

DAY = date(2026, 11, 1)


async def _student(db_session, seed_data, enr) -> uuid.UUID:
    s = Student(
        id=uuid.uuid4(), branch_id=seed_data["branch_a"].id,
        academic_year_id=seed_data["academic_year"].id,
        first_name=enr, last_name="S", enrollment_number=enr,
        parent_mobile="98" + enr[-6:].rjust(6, "0"),
        status="active", is_deleted=False,
    )
    db_session.add(s)
    db_session.add(StudentBatchMapping(
        student_id=s.id, batch_id=seed_data["batch"].id, branch_id=seed_data["branch_a"].id,
        status="active", is_deleted=False,
    ))
    await db_session.flush()
    return s.id


async def _profile(db_session, seed_data, student_id, plan, agreed):
    return await fee_service.create_fee_profile(
        db_session,
        {
            "student_id": student_id, "batch_id": seed_data["batch"].id,
            "actual_fee": agreed + 10000, "agreed_fee": agreed,
            "payment_mode": "INSTALLMENT", "admission_date": date(2026, 9, 1),
            "installments": plan,
        },
        branch_id=seed_data["branch_a"].id, user_id=seed_data["admin_user"].id,
    )


@pytest.mark.usefixtures("seed_data")
async def test_dashboard_three_lists(db_session: AsyncSession, seed_data):
    b = seed_data["branch_a"].id
    uid = seed_data["admin_user"].id
    s1 = await _student(db_session, seed_data, "FEE001")
    s2 = await _student(db_session, seed_data, "FEE002")
    # s1: one due today, one overdue (1 Oct), one future.
    await _profile(db_session, seed_data, s1, [
        {"number": 1, "due_date": date(2026, 10, 1), "amount": 30000},
        {"number": 2, "due_date": DAY, "amount": 30000},
        {"number": 3, "due_date": date(2026, 12, 1), "amount": 30000},
    ], 90000)
    # s2: one overdue (15 Oct) + a remark promising to pay DAY -> commitment.
    p2 = await _profile(db_session, seed_data, s2, [
        {"number": 1, "due_date": date(2026, 10, 15), "amount": 30000},
        {"number": 2, "due_date": date(2026, 12, 15), "amount": 30000},
    ], 60000)
    await fee_service.add_remark(db_session, {
        "student_id": s2, "profile_id": p2.id,
        "remark_text": "Will pay on 1 Nov", "call_date": date(2026, 10, 28),
        "next_followup_date": DAY,
    }, b, uid)

    dash = await followup_service.follow_up_dashboard(db_session, b, DAY)

    # Dues: s1's installment due today.
    assert [r["student_id"] for r in dash["dues"]] == [s1]
    assert dash["dues_total"] == 30000
    assert dash["dues"][0]["phone"]  # parent mobile surfaced

    # Overdue: s1 (1 Oct) + s2 (15 Oct), oldest first, with days overdue.
    assert [r["due_date"].isoformat() for r in dash["overdue"]] == ["2026-10-01", "2026-10-15"]
    assert dash["overdue"][0]["days_overdue"] == 31
    assert dash["overdue_total"] == 60000

    # Commitments: s2 (promised today), shown against its earliest unpaid.
    assert [r["student_id"] for r in dash["commitments"]] == [s2]
    assert dash["commitments"][0]["last_remark"] == "Will pay on 1 Nov"


@pytest.mark.usefixtures("seed_data")
async def test_paid_installments_excluded(db_session: AsyncSession, seed_data):
    b = seed_data["branch_a"].id
    s1 = await _student(db_session, seed_data, "FEE010")
    await _profile(db_session, seed_data, s1, [
        {"number": 1, "due_date": DAY, "amount": 30000},
    ], 30000)
    inst = (await db_session.execute(
        Installment.__table__.select().where(Installment.student_id == s1)
    )).first()
    await fee_service.record_payment(
        db_session, inst.id, b, amount_paid=30000, payment_date=DAY,
        payment_mode="UPI", notes=None, user_id=seed_data["admin_user"].id,
    )
    dash = await followup_service.follow_up_dashboard(db_session, b, DAY)
    assert dash["dues"] == [] and dash["overdue"] == []


@pytest.mark.usefixtures("seed_data")
async def test_mark_overdue_flips_pending(db_session: AsyncSession, seed_data):
    b = seed_data["branch_a"].id
    s1 = await _student(db_session, seed_data, "FEE020")
    await _profile(db_session, seed_data, s1, [
        {"number": 1, "due_date": date(2026, 10, 1), "amount": 30000},  # past
        {"number": 2, "due_date": DAY, "amount": 30000},                # today
    ], 60000)
    n = await followup_service.mark_overdue(db_session, b, DAY)
    assert n == 1  # only the past-due one flips
    rows = (await db_session.execute(
        Installment.__table__.select().where(Installment.student_id == s1)
        .order_by(Installment.installment_number)
    )).all()
    assert rows[0].installment_status == "OVERDUE"
    assert rows[1].installment_status == "PENDING"  # due today, not past


@pytest.mark.usefixtures("seed_data")
async def test_sweep_only_in_local_sweep_hour(db_session: AsyncSession, seed_data):
    # The sweep runs a branch only when its local time is the sweep hour.
    s1 = await _student(db_session, seed_data, "FEE030")
    await _profile(db_session, seed_data, s1, [
        {"number": 1, "due_date": date(2026, 10, 1), "amount": 30000},
    ], 30000)
    # 18:30 UTC = 00:00 IST (not 06:00) -> no branch swept.
    off_hour = datetime(2026, 11, 1, 18, 30, tzinfo=timezone.utc)
    swept = await fee_tasks.sweep_overdue(db_session, off_hour)
    assert swept == []
    # 00:30 UTC = 06:00 IST -> branch swept.
    on_hour = datetime(2026, 11, 1, 0, 30, tzinfo=timezone.utc)
    swept = await fee_tasks.sweep_overdue(db_session, on_hour)
    assert any(n >= 1 for _b, _d, n in swept)
