"""End-to-end acceptance tests for the Weekend & Star-System workflow (SRD §11).

HTTP-level, through the real /me and /admin/approvals routes with auth cookies,
covering the acceptance criteria — especially AC-08 (a teacher cannot open
another teacher's record by changing the URL) and AC-04/05/06/07."""

import uuid
from datetime import date, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models.auth_models import User
from app.modules.auth.services.auth_service import hash_password
from app.modules.auth.services.token_service import create_access_token
from app.modules.staff.models.staff_models import Department, Staff

BRANCH = uuid.UUID("00000000-0000-0000-0000-000000000001")


def _sunday() -> date:
    d = date(2026, 12, 1)
    while d.weekday() != 6:
        d += timedelta(days=1)
    return d


SUN = _sunday()


async def _teacher(db: AsyncSession, emp: str) -> tuple[Staff, User]:
    dept = (await db.execute(
        select(Department).where(Department.branch_id == BRANCH, Department.name == "ACC-T")
    )).scalar_one_or_none()
    if dept is None:
        dept = Department(branch_id=BRANCH, name="ACC-T", id_range_start=96000, id_range_end=96999)
        db.add(dept)
        await db.commit()
    s = Staff(branch_id=BRANCH, emp_code=emp, first_name="Ava", last_name="S", department_id=dept.id)
    db.add(s)
    await db.commit()
    u = User(email=f"{emp}@teacher.local", password_hash=hash_password("x"),
             first_name="Ava", last_name="S", username=emp, staff_id=s.id, primary_branch_id=BRANCH)
    db.add(u)
    await db.commit()
    return s, u


async def _approver(db: AsyncSession) -> User:
    u = User(email="approver@acc.local", password_hash=hash_password("x"),
             first_name="Head", last_name="Sir", primary_branch_id=BRANCH)
    db.add(u)
    await db.commit()
    return u


def _tcookie(u: User) -> dict:
    return {"access_token": create_access_token(u.id, ["teacher_portal"], BRANCH)}


def _acookie(u: User) -> dict:
    return {"access_token": create_access_token(u.id, ["branch_admin"], BRANCH)}


def _plan_body(items=None):
    return {
        "plan_date": SUN.isoformat(),
        "remarks": None,
        "approver_id": None,
        "items": items or [{
            "work_type": "Lecture", "batch_id": None,
            "task_description": "Sunday revision", "start_time": "09:00", "end_time": "11:00",
        }],
    }


# ── AC-01 + AC-08 ────────────────────────────────────────────────────────────

async def test_ac01_create_submit_pending_and_ac08_idor(db_session, seed_data, client):
    _, teacher = await _teacher(db_session, "96001")
    _, other = await _teacher(db_session, "96002")

    # AC-01: create + submit → Pending.
    r = await client.post("/api/v1/me/weekend-plans", params={"submit": True},
                          json=_plan_body(), cookies=_tcookie(teacher))
    assert r.status_code == 201, r.text
    plan = r.json()
    assert plan["status"] == "PENDING"

    # AC-08: another teacher cannot open it by URL → 404.
    r2 = await client.get(f"/api/v1/me/weekend-plans/{plan['id']}", cookies=_tcookie(other))
    assert r2.status_code == 404
    # The owner can.
    r3 = await client.get(f"/api/v1/me/weekend-plans/{plan['id']}", cookies=_tcookie(teacher))
    assert r3.status_code == 200


# ── AC-04 + AC-05 + notifications ────────────────────────────────────────────

async def test_ac04_comment_required_and_ac05_teacher_sees_comment(db_session, seed_data, client):
    _, teacher = await _teacher(db_session, "96003")
    approver = await _approver(db_session)

    r = await client.post("/api/v1/me/weekend-plans", params={"submit": True},
                          json=_plan_body(), cookies=_tcookie(teacher))
    plan_id = r.json()["id"]
    base = f"/api/v1/admin/approvals/WEEKEND_PLAN/{plan_id}"

    # AC-04: no action without a (>=10 char) comment.
    bad = await client.post(f"{base}/decide", params={"branch_id": str(BRANCH)},
                            json={"action": "APPROVE", "comment": "ok"}, cookies=_acookie(approver))
    assert bad.status_code == 400

    good = await client.post(f"{base}/decide", params={"branch_id": str(BRANCH)},
                             json={"action": "APPROVE", "comment": "Approved for Sunday work."},
                             cookies=_acookie(approver))
    assert good.status_code == 200
    assert good.json()["status"] == "APPROVED"

    # AC-05: the teacher sees the status + the exact comment.
    mine = await client.get(f"/api/v1/me/weekend-plans/{plan_id}", cookies=_tcookie(teacher))
    assert mine.json()["status"] == "APPROVED"
    assert mine.json()["latest_approver_comment"] == "Approved for Sunday work."

    # The teacher got an in-app notification with the comment.
    notes = await client.get("/api/v1/me/notifications", cookies=_tcookie(teacher))
    assert any("Approved for Sunday work." in n["message"] for n in notes.json())
    cnt = await client.get("/api/v1/me/notifications/unread-count", cookies=_tcookie(teacher))
    assert cnt.json()["count"] >= 1


# ── AC-06 ────────────────────────────────────────────────────────────────────

async def test_ac06_reject_edit_resubmit_history(db_session, seed_data, client):
    _, teacher = await _teacher(db_session, "96004")
    approver = await _approver(db_session)

    r = await client.post("/api/v1/me/weekend-plans", params={"submit": True},
                          json=_plan_body(), cookies=_tcookie(teacher))
    plan_id = r.json()["id"]
    await client.post(f"/api/v1/admin/approvals/WEEKEND_PLAN/{plan_id}/decide",
                      params={"branch_id": str(BRANCH)},
                      json={"action": "REJECT", "comment": "Please add a second batch."},
                      cookies=_acookie(approver))

    # Edit (now rejected) and resubmit.
    edit = await client.put(f"/api/v1/me/weekend-plans/{plan_id}", params={"submit": True},
                            json=_plan_body(items=[
                                {"work_type": "Lecture", "batch_id": None, "task_description": "Batch A",
                                 "start_time": "09:00", "end_time": "10:00"},
                                {"work_type": "Doubt Solving", "batch_id": None, "task_description": "Batch B",
                                 "start_time": "10:00", "end_time": "11:00"},
                            ]), cookies=_tcookie(teacher))
    assert edit.status_code == 200
    body = edit.json()
    assert body["status"] == "PENDING"
    actions = [h["action"] for h in body["history"]]
    assert actions == ["SUBMIT", "REJECT", "RESUBMIT"]  # history preserved


# ── AC-07 ────────────────────────────────────────────────────────────────────

async def test_ac07_mark_absent_visible(db_session, seed_data, client):
    _, teacher = await _teacher(db_session, "96005")
    approver = await _approver(db_session)
    r = await client.post("/api/v1/me/weekend-plans", params={"submit": True},
                          json=_plan_body(), cookies=_tcookie(teacher))
    plan_id = r.json()["id"]
    dec = await client.post(f"/api/v1/admin/approvals/WEEKEND_PLAN/{plan_id}/decide",
                            params={"branch_id": str(BRANCH)},
                            json={"action": "MARK_ABSENT", "comment": "No punch recorded on the day."},
                            cookies=_acookie(approver))
    assert dec.json()["status"] == "ABSENT"
    mine = await client.get(f"/api/v1/me/weekend-plans/{plan_id}", cookies=_tcookie(teacher))
    assert mine.json()["status"] == "ABSENT"
    assert "No punch" in mine.json()["latest_approver_comment"]


# ── AC-02 + AC-03 (Star System via HTTP) ─────────────────────────────────────

async def test_ac02_ac03_star_form_and_total(db_session, seed_data, client):
    _, teacher = await _teacher(db_session, "96006")
    form = await client.get("/api/v1/me/self-assessment-form", cookies=_tcookie(teacher))
    cats = form.json()["categories"]
    assert len(cats) == 5  # AC-02: all categories present
    rated = [c for c in cats if c["rated"]]
    assert len(rated) == 4

    stars = [{"category_id": c["id"], "stars": v} for c, v in zip(rated, [4, 3, 4, 5])]
    save = await client.put("/api/v1/me/self-assessments", params={"submit": True},
                            json={"assess_date": "2026-11-16", "approver_id": None,
                                  "miscellaneous_text": None, "items": [], "stars": stars},
                            cookies=_tcookie(teacher))
    assert save.status_code == 200
    assert save.json()["final_total_star"] == 16.0  # AC-03: 4+3+4+5
    assert save.json()["status"] == "PENDING"
