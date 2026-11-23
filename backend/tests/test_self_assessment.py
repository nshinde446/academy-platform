"""Teacher Star-System self-assessment — SRD §5.2.

Form definition (seeded catalog), draft/submit, final-total = sum of 4 category
stars (SA-05), one-per-date lock (SA-06), option validation (SA-02), submit needs
all four ratings (SA-04), approver decision round-trip, and admin config."""

import uuid
from datetime import date

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.modules.auth.models.auth_models import User
from app.modules.auth.services.auth_service import hash_password
from app.modules.staff.models.staff_models import Department, Staff
from app.modules.teacher_portal.schemas.portal_schemas import (
    SelfAssessmentItemIn,
    SelfAssessmentStarIn,
    SelfAssessmentWrite,
)
from app.modules.teacher_portal.services import approvals_service as appr
from app.modules.teacher_portal.services import assessment_config_service as cfg
from app.modules.teacher_portal.services import self_assessment_service as sa
from app.modules.teacher_portal.services import workflow_common as wf

BRANCH = uuid.UUID("00000000-0000-0000-0000-000000000001")
APPROVER = uuid.UUID("00000000-0000-0000-0000-000000000100")
DAY = date(2026, 11, 16)


async def _teacher(db, emp_code="95000"):
    dept = Department(branch_id=BRANCH, name=f"SA-{emp_code}",
                      id_range_start=95000, id_range_end=95999)
    db.add(dept)
    await db.flush()
    s = Staff(branch_id=BRANCH, emp_code=emp_code, first_name="Kiran", last_name="P",
              department_id=dept.id)
    db.add(s)
    await db.flush()
    u = User(email=f"{emp_code}@t.com", password_hash=hash_password("x"),
             first_name="Kiran", last_name="P", username=emp_code, staff_id=s.id,
             primary_branch_id=BRANCH)
    db.add(u)
    await db.flush()
    return s, u


async def _rated_cat_ids(db, staff):
    form = await sa.form_definition(db, staff_id=staff.id)
    return [c["id"] for c in form["categories"] if c["rated"]], form


def _full_stars(cat_ids, values=(4, 3, 4, 5)):
    return [SelfAssessmentStarIn(category_id=cid, stars=v) for cid, v in zip(cat_ids, values)]


@pytest.mark.usefixtures("seed_data")
async def test_form_definition_has_five_categories(db_session, seed_data):
    s, _ = await _teacher(db_session)
    form = await sa.form_definition(db_session, staff_id=s.id)
    assert len(form["categories"]) == 5
    assert sum(1 for c in form["categories"] if c["rated"]) == 4
    assert form["max_total_star"] == 20
    # Every non-deduction item has options and no free-text item exists.
    for c in form["categories"]:
        for it in c["items"]:
            assert it["options"]


@pytest.mark.usefixtures("seed_data")
async def test_save_draft_computes_final_total(db_session, seed_data):
    s, _ = await _teacher(db_session, "95001")
    cat_ids, _ = await _rated_cat_ids(db_session, s)
    out = await sa.save(db_session, staff_id=s.id, user_id=APPROVER, submit=False,
                        data=SelfAssessmentWrite(assess_date=DAY, stars=_full_stars(cat_ids)))
    assert out["status"] == "DRAFT"
    assert out["final_total_star"] == 16.0  # 4+3+4+5


@pytest.mark.usefixtures("seed_data")
async def test_invalid_option_rejected(db_session, seed_data):
    s, _ = await _teacher(db_session, "95002")
    form = await sa.form_definition(db_session, staff_id=s.id)
    item = form["categories"][0]["items"][0]
    with pytest.raises(HTTPException) as ei:
        await sa.save(db_session, staff_id=s.id, user_id=APPROVER, submit=False,
                      data=SelfAssessmentWrite(
                          assess_date=DAY,
                          items=[SelfAssessmentItemIn(item_master_id=item["id"],
                                                      selected_value="NONSENSE")]))
    assert ei.value.status_code == 400


@pytest.mark.usefixtures("seed_data")
async def test_submit_requires_all_four_ratings(db_session, seed_data):
    s, _ = await _teacher(db_session, "95003")
    cat_ids, _ = await _rated_cat_ids(db_session, s)
    with pytest.raises(HTTPException) as ei:
        await sa.save(db_session, staff_id=s.id, user_id=APPROVER, submit=True,
                      data=SelfAssessmentWrite(
                          assess_date=DAY, stars=_full_stars(cat_ids[:2], (4, 4))))
    assert ei.value.status_code == 400


@pytest.mark.usefixtures("seed_data")
async def test_one_per_date_and_submit_then_locked(db_session, seed_data):
    s, _ = await _teacher(db_session, "95004")
    cat_ids, _ = await _rated_cat_ids(db_session, s)
    await sa.save(db_session, staff_id=s.id, user_id=APPROVER, submit=True,
                  data=SelfAssessmentWrite(assess_date=DAY, stars=_full_stars(cat_ids)))
    # Second save for the same date, now PENDING → blocked (SA-06 + edit-lock).
    with pytest.raises(HTTPException) as ei:
        await sa.save(db_session, staff_id=s.id, user_id=APPROVER, submit=False,
                      data=SelfAssessmentWrite(assess_date=DAY, stars=_full_stars(cat_ids)))
    assert ei.value.status_code == 409


@pytest.mark.usefixtures("seed_data")
async def test_full_round_trip_with_approver(db_session, seed_data):
    s, u = await _teacher(db_session, "95005")
    cat_ids, form = await _rated_cat_ids(db_session, s)
    item = form["categories"][0]["items"][0]
    out = await sa.save(
        db_session, staff_id=s.id, user_id=APPROVER, submit=True,
        data=SelfAssessmentWrite(
            assess_date=DAY, miscellaneous_text="Busy day",
            items=[SelfAssessmentItemIn(item_master_id=item["id"],
                                        selected_value=item["options"][0])],
            stars=_full_stars(cat_ids)))
    assert out["status"] == "PENDING"

    decided = await appr.decide(
        db_session, branch_id=BRANCH, record_type=wf.RECORD_SELF_ASSESSMENT,
        record_id=out["id"], approver_user_id=APPROVER, action="APPROVE",
        comment="Nice work this week.")
    assert decided["status"] == "APPROVED"
    assert decided["final_total_star"] == 16.0
    # Teacher sees it reflected.
    back = await sa.get_for_date(db_session, staff_id=s.id, on=DAY)
    assert back["status"] == "APPROVED"
    assert back["latest_approver_comment"] == "Nice work this week."


@pytest.mark.usefixtures("seed_data")
async def test_admin_config_add_and_toggle_item(db_session, seed_data):
    s, _ = await _teacher(db_session, "95006")
    cat = (await sa.form_definition(db_session, staff_id=s.id))["categories"][0]
    added = await cfg.add_item(
        db_session, branch_id=BRANCH, user_id=APPROVER, category_id=cat["id"],
        item_name="Extra Duty", input_type="STATUS", options=["Not Done", "Done"])
    cat_now = next(c for c in (await cfg.catalog(db_session, branch_id=BRANCH))["categories"]
                   if c["id"] == cat["id"])
    assert any(it["name"] == "Extra Duty" for it in cat_now["items"])
    await cfg.update_item(db_session, branch_id=BRANCH, user_id=APPROVER,
                          item_id=added["id"], active=False)
    form = await sa.form_definition(db_session, staff_id=s.id)
    cat_form = next(c for c in form["categories"] if c["id"] == cat["id"])
    assert all(it["name"] != "Extra Duty" for it in cat_form["items"])  # inactive hidden
