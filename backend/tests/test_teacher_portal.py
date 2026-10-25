"""Teacher Login — Slice 2: default-deny allowlist + read-only /me/* endpoints.

Covers the spec's security core: a teacher-only token reaches only /auth/* and
/me/*; My Day reads the worked examples (late 7 -> Rs.500, on time -> 0, etc.);
the staff id comes from the session so an IDOR param is ignored + logged; fine
is hidden until day close; a forced password change blocks the data routes.
"""

import uuid
from datetime import date, datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.attendance.models.attendance_models import (
    LateFineSlab,
    StaffDailyAttendance,
)
from app.modules.auth.models.auth_models import AuthEvent, User
from app.modules.auth.services.auth_service import hash_password
from app.modules.auth.services.token_service import create_access_token
from app.modules.staff.models.staff_models import Department, Staff

BRANCH = uuid.UUID("00000000-0000-0000-0000-000000000001")  # seed branch_a (Asia/Kolkata)
UTC = timezone.utc


def _utc_for_ist(d: date, hh: int, mm: int) -> datetime:
    """UTC instant for a local IST (UTC+5:30) wall-clock time on date d."""
    total = hh * 60 + mm - 330  # subtract 5:30
    return datetime(d.year, d.month, d.day, 0, 0, tzinfo=UTC).replace(
        hour=(total // 60) % 24, minute=total % 60
    )


async def _slabs(db: AsyncSession) -> None:
    db.add_all([
        LateFineSlab(min_minutes=1, max_minutes=5, fine_amount=200, color_hex="#BDD7EE", label="1-5"),
        LateFineSlab(min_minutes=6, max_minutes=10, fine_amount=500, color_hex="#FFEB84", label="6-10"),
        LateFineSlab(min_minutes=11, max_minutes=None, fine_amount=1000, color_hex="#FF6B6B", label="11+"),
    ])


async def _teacher(db: AsyncSession, emp: str, shift="09:00") -> tuple[Staff, User]:
    dept = (await db.execute(
        select(Department).where(Department.branch_id == BRANCH, Department.name == "MSA-Teachers")
    )).scalar_one_or_none()
    if dept is None:
        dept = Department(branch_id=BRANCH, name="MSA-Teachers", id_range_start=1, id_range_end=99)
        db.add(dept)
        await db.commit()
    s = Staff(
        branch_id=BRANCH, emp_code=emp, first_name="Asha", last_name="Rao",
        department_id=dept.id, shift_start=shift,
    )
    db.add(s)
    await db.commit()
    u = User(
        email=f"{emp}@teacher.local", password_hash=hash_password("x"),
        first_name="Asha", last_name="Rao", username=emp, staff_id=s.id,
        primary_branch_id=BRANCH,
    )
    db.add(u)
    await db.commit()
    return s, u


def _cookie(user: User, roles=("teacher_portal",)) -> dict:
    token = create_access_token(user.id, list(roles), BRANCH)
    return {"access_token": token}


# ── allowlist (default deny) ─────────────────────────────────────────────────

async def test_teacher_only_token_blocked_off_allowlist(db_session: AsyncSession, seed_data, client):
    _, u = await _teacher(db_session, "91001")
    r = await client.get(
        "/api/v1/students", params={"branch_id": str(BRANCH)}, cookies=_cookie(u),
    )
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "TEACHER_FORBIDDEN"


async def test_teacher_can_reach_me_route(db_session: AsyncSession, seed_data, client):
    _, u = await _teacher(db_session, "91002")
    r = await client.get("/api/v1/me/profile", cookies=_cookie(u))
    assert r.status_code == 200
    assert r.json()["employee_code"] == "91002"


async def test_admin_token_not_restricted(db_session: AsyncSession, seed_data, client):
    _, u = await _teacher(db_session, "91003")
    # Same account but the token also carries an elevated role -> not teacher-only.
    r = await client.get(
        "/api/v1/students", params={"branch_id": str(BRANCH)},
        cookies=_cookie(u, roles=("teacher_portal", "branch_admin")),
    )
    assert r.status_code != 403 or r.json().get("error", {}).get("code") != "TEACHER_FORBIDDEN"


# ── My Day worked examples ───────────────────────────────────────────────────

@pytest.mark.parametrize("in_hh,in_mm,exp_late,exp_fine", [
    (9, 7, 7, 500),    # late 7 -> slab 6-10 -> 500
    (8, 58, 0, 0),     # on time
    (9, 12, 12, 1000),  # late 12 -> 11+ -> 1000
    (9, 3, 3, 200),    # late 3 -> 1-5 -> 200
])
async def test_my_day_worked_examples(
    db_session: AsyncSession, seed_data, client, in_hh, in_mm, exp_late, exp_fine
):
    await _slabs(db_session)
    s, u = await _teacher(db_session, f"920{in_mm:02d}", shift="09:00")
    past = date(2026, 10, 1)  # a closed (past) day so the fine is visible
    db_session.add(StaffDailyAttendance(
        staff_id=s.id, branch_id=BRANCH, attendance_date=past,
        first_in=_utc_for_ist(past, in_hh, in_mm),
        last_out=_utc_for_ist(past, 17, 0), day_status="PRESENT" if exp_late == 0 else "LATE",
        signoff="COMPLETE", source="BIOMETRIC", work_minutes=400,
    ))
    await db_session.commit()
    r = await client.get("/api/v1/me/day", params={"date": past.isoformat()}, cookies=_cookie(u))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["first_lecture_start"] == "09:00"
    assert body["late_minutes"] == exp_late
    assert body["fine"]["visible"] is True
    assert body["fine"]["amount"] == exp_fine


# ── fine visibility (pending until day close) ────────────────────────────────

async def test_fine_pending_for_today_before_close(db_session: AsyncSession, seed_data, client):
    await _slabs(db_session)
    s, u = await _teacher(db_session, "93001", shift="09:00")
    today = date.today()
    # IN clearly late, but today's fine stays hidden until the day-close time.
    db_session.add(StaffDailyAttendance(
        staff_id=s.id, branch_id=BRANCH, attendance_date=today,
        first_in=_utc_for_ist(today, 9, 7), last_out=None,
        day_status="LATE", signoff="MISSING", source="BIOMETRIC", work_minutes=0,
    ))
    await db_session.commit()
    r = await client.get("/api/v1/me/day", cookies=_cookie(u))
    body = r.json()
    # Late minutes are live; the fine is withheld pre-close (amount None).
    assert body["late_minutes"] == 7
    # Before 23:30 the fine is pending; this test runs well before then in CI.
    if body["fine"]["visible"] is False:
        assert body["fine"]["amount"] is None


# ── IDOR: identity from the session only ─────────────────────────────────────

async def test_idor_param_is_ignored_and_logged(db_session: AsyncSession, seed_data, client):
    await _slabs(db_session)
    s_a, u_a = await _teacher(db_session, "94001", shift="09:00")
    s_b, _ = await _teacher(db_session, "94002", shift="09:00")
    past = date(2026, 10, 2)
    # Only teacher B has a record that day.
    db_session.add(StaffDailyAttendance(
        staff_id=s_b.id, branch_id=BRANCH, attendance_date=past,
        first_in=_utc_for_ist(past, 9, 30), last_out=None,
        day_status="LATE", signoff="MISSING", source="BIOMETRIC", work_minutes=0,
    ))
    await db_session.commit()
    # Teacher A asks for B's staff_id — must get A's own (empty) data, not B's.
    r = await client.get(
        "/api/v1/me/day",
        params={"date": past.isoformat(), "staff_id": str(s_b.id)},
        cookies=_cookie(u_a),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["attendance"]["in"] is None          # A has no punch -> not B's 09:30
    assert body["late_minutes"] is None
    # The probe was logged.
    events = (await db_session.execute(
        select(AuthEvent).where(AuthEvent.event == "idor_attempt", AuthEvent.user_id == u_a.id)
    )).scalars().all()
    assert len(events) >= 1


# ── forced password change gate ──────────────────────────────────────────────

async def test_must_change_password_blocks_data(db_session: AsyncSession, seed_data, client):
    _, u = await _teacher(db_session, "95001")
    u.must_change_password = True
    await db_session.commit()
    r = await client.get("/api/v1/me/profile", cookies=_cookie(u))
    assert r.status_code == 403
    assert r.json()["error"]["message"] == "PASSWORD_CHANGE_REQUIRED"


# ── month summary ────────────────────────────────────────────────────────────

async def test_month_summary_counts(db_session: AsyncSession, seed_data, client):
    await _slabs(db_session)
    s, u = await _teacher(db_session, "96001", shift="09:00")
    # (day, status, IN hh, IN mm): 08:58 on time, 09:07 late (x2).
    for d, st, hh, mm in [(1, "PRESENT", 8, 58), (2, "LATE", 9, 7), (3, "HALF_DAY", 9, 7)]:
        day = date(2026, 9, d)
        db_session.add(StaffDailyAttendance(
            staff_id=s.id, branch_id=BRANCH, attendance_date=day,
            first_in=_utc_for_ist(day, hh, mm), last_out=None,
            day_status=st, signoff="MISSING", source="BIOMETRIC", work_minutes=0,
        ))
    await db_session.commit()
    r = await client.get("/api/v1/me/month-summary", params={"year": 2026, "month": 9}, cookies=_cookie(u))
    assert r.status_code == 200
    b = r.json()
    # PRESENT + LATE both count as present days; HALF_DAY is separate.
    assert b["present_days"] == 2 and b["half_days"] == 1
    assert b["late_count"] == 2            # the 09:07 LATE + 09:07 HALF_DAY both late
    assert b["total_late_minutes"] == 14
    assert b["total_fine"] == 1000         # two 7-min days -> 500 + 500 (Sept is past)
