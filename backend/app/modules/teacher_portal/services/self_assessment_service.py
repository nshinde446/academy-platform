"""Teacher Star-System daily self-assessment (Weekend & Star-System SRD §5.2).

The teacher opens the form for a date, picks a dropdown value for each item (the
only free-text field is Miscellaneous), gives a 1–5 star rating to each of the
four main categories, and Saves Draft or Submits. The Final Total Star is the
sum of the four category stars (max 20), recomputed server-side (SA-05).

One assessment per teacher per date (SA-06). Submitted forms are read-only until
the approver rejects them (5.2.2 edit-lock). All access is own-only (BR-05);
approver decisions run through the shared approvals engine (Slice 3).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.teacher_portal.models.workflow_models import (
    AssessmentCategory,
    AssessmentItemMaster,
    SelfAssessment,
    SelfAssessmentItem,
    SelfAssessmentStar,
)
from app.modules.teacher_portal.schemas.portal_schemas import SelfAssessmentWrite
from app.modules.teacher_portal.services import assessment_catalog, workflow_common as wf

_EDITABLE = ("DRAFT", "REJECTED")


async def _catalog(
    session: AsyncSession, branch_id: uuid.UUID
) -> tuple[list[AssessmentCategory], dict[uuid.UUID, list[AssessmentItemMaster]]]:
    """Active categories (sorted) + their active items, seeding defaults first."""
    await assessment_catalog.ensure_seeded(session, branch_id=branch_id)
    cats = list((await session.execute(
        select(AssessmentCategory).where(
            AssessmentCategory.branch_id == branch_id,
            AssessmentCategory.active == True,  # noqa: E712
            AssessmentCategory.is_deleted == False,  # noqa: E712
        ).order_by(AssessmentCategory.sort_order.asc())
    )).scalars().all())
    items = list((await session.execute(
        select(AssessmentItemMaster).where(
            AssessmentItemMaster.branch_id == branch_id,
            AssessmentItemMaster.active == True,  # noqa: E712
            AssessmentItemMaster.is_deleted == False,  # noqa: E712
        ).order_by(AssessmentItemMaster.sort_order.asc())
    )).scalars().all())
    by_cat: dict[uuid.UUID, list[AssessmentItemMaster]] = {}
    for it in items:
        by_cat.setdefault(it.category_id, []).append(it)
    return cats, by_cat


async def form_definition(session: AsyncSession, *, staff_id: uuid.UUID) -> dict:
    """The form structure the teacher fills (SA-01/SA-03): categories, their
    items with dropdown options, and which categories are star-rated."""
    branch_id = await wf.resolve_branch_id(session, staff_id)
    cats, by_cat = await _catalog(session, branch_id)
    return {
        "categories": [
            {
                "id": c.id,
                "name": c.name,
                "is_deduction": c.is_deduction,
                "rated": not c.is_deduction,
                "items": [
                    {
                        "id": it.id,
                        "name": it.item_name,
                        "input_type": it.input_type,
                        "options": it.options,
                    }
                    for it in by_cat.get(c.id, [])
                ],
            }
            for c in cats
        ],
        "max_total_star": assessment_catalog.MAX_FINAL_STAR,
    }


async def _serialize(session: AsyncSession, a: SelfAssessment, *, with_history=True) -> dict:
    items = list((await session.execute(
        select(SelfAssessmentItem).where(
            SelfAssessmentItem.self_assessment_id == a.id,
            SelfAssessmentItem.is_deleted == False,  # noqa: E712
        )
    )).scalars().all())
    stars = list((await session.execute(
        select(SelfAssessmentStar).where(
            SelfAssessmentStar.self_assessment_id == a.id,
            SelfAssessmentStar.is_deleted == False,  # noqa: E712
        )
    )).scalars().all())
    out = {
        "id": a.id,
        "assess_date": a.assess_date,
        "status": a.status_code,
        "final_total_star": float(a.final_total_star),
        "max_total_star": assessment_catalog.MAX_FINAL_STAR,
        "miscellaneous_text": a.miscellaneous_text,
        "approver_id": a.approver_id,
        "submitted_at": a.submitted_at,
        "latest_approver_comment": a.latest_approver_comment,
        "can_edit": a.status_code in _EDITABLE,
        "items": {str(i.item_master_id): i.selected_value for i in items},
        "stars": {str(s.category_id): s.stars for s in stars},
    }
    if with_history:
        out["history"] = await wf.history_for(
            session, record_type=wf.RECORD_SELF_ASSESSMENT, record_id=a.id)
    return out


def _validate_and_total(
    *,
    cats: list[AssessmentCategory],
    by_cat: dict[uuid.UUID, list[AssessmentItemMaster]],
    data: SelfAssessmentWrite,
    submit: bool,
) -> float:
    """Validate item values + stars against the catalog and return the final total.

    Item values must be one of the item's options. Stars (1–5) are required for
    every rated category when submitting (SA-04); drafts may be partial."""
    valid_items = {it.id: it for items in by_cat.values() for it in items}
    for row in data.items:
        it = valid_items.get(row.item_master_id)
        if it is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown assessment item {row.item_master_id}.")
        if row.selected_value not in (it.options or []):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"'{row.selected_value}' is not a valid option for {it.item_name}.")

    rated_ids = {c.id for c in cats if not c.is_deduction}
    star_map: dict[uuid.UUID, int] = {}
    for sr in data.stars:
        if sr.category_id not in rated_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Stars can only be given to the four main categories.")
        if not (1 <= sr.stars <= 5):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Each star rating must be between 1 and 5.")
        star_map[sr.category_id] = sr.stars

    if submit and set(star_map) != rated_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Rate all four main categories before submitting.")
    return float(sum(star_map.values()))


async def save(
    session: AsyncSession,
    *,
    staff_id: uuid.UUID,
    user_id: uuid.UUID,
    data: SelfAssessmentWrite,
    submit: bool,
) -> dict:
    """Create or update the assessment for a date (upsert by date). Blocks when a
    submitted/decided form already exists for the date (SA-06 + edit-lock)."""
    branch_id = await wf.resolve_branch_id(session, staff_id)
    cats, by_cat = await _catalog(session, branch_id)
    total = _validate_and_total(cats=cats, by_cat=by_cat, data=data, submit=submit)

    existing = (await session.execute(
        select(SelfAssessment).where(
            SelfAssessment.branch_id == branch_id,
            SelfAssessment.staff_id == staff_id,
            SelfAssessment.assess_date == data.assess_date,
            SelfAssessment.is_deleted == False,  # noqa: E712
        )
    )).scalar_one_or_none()

    if existing is not None and existing.status_code not in _EDITABLE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"An assessment for {data.assess_date} is already "
                   f"{existing.status_code} and can't be changed.")

    a = existing or SelfAssessment(
        branch_id=branch_id, staff_id=staff_id, assess_date=data.assess_date,
        status_code="DRAFT", created_by=user_id)
    a.miscellaneous_text = (data.miscellaneous_text or None)
    a.final_total_star = total
    a.updated_by = user_id
    if existing is None:
        session.add(a)
    await session.flush()

    await _replace_rows(session, a=a, branch_id=branch_id, data=data, user_id=user_id)

    if submit:
        await _do_submit(session, a=a, branch_id=branch_id,
                         chosen_approver_id=data.approver_id, user_id=user_id)
    await session.flush()
    return await _serialize(session, a)


async def _replace_rows(
    session: AsyncSession,
    *,
    a: SelfAssessment,
    branch_id: uuid.UUID,
    data: SelfAssessmentWrite,
    user_id: uuid.UUID,
) -> None:
    for tbl in (SelfAssessmentItem, SelfAssessmentStar):
        for row in (await session.execute(
            select(tbl).where(
                tbl.self_assessment_id == a.id,
                tbl.is_deleted == False,  # noqa: E712
            )
        )).scalars().all():
            row.is_deleted = True
            row.updated_by = user_id
    for row in data.items:
        session.add(SelfAssessmentItem(
            branch_id=branch_id, self_assessment_id=a.id,
            item_master_id=row.item_master_id, selected_value=row.selected_value,
            created_by=user_id))
    for sr in data.stars:
        session.add(SelfAssessmentStar(
            branch_id=branch_id, self_assessment_id=a.id,
            category_id=sr.category_id, stars=sr.stars, created_by=user_id))
    await session.flush()


async def _do_submit(
    session: AsyncSession, *, a: SelfAssessment, branch_id: uuid.UUID,
    chosen_approver_id: uuid.UUID | None, user_id: uuid.UUID,
) -> None:
    resubmit = a.status_code == "REJECTED"
    approver_id = await wf.resolve_approver(
        session, staff_id=a.staff_id, branch_id=branch_id,
        chosen_approver_id=chosen_approver_id)
    a.approver_id = approver_id
    a.status_code = "PENDING"
    a.submitted_at = datetime.now(timezone.utc)
    a.updated_by = user_id
    await session.flush()
    await wf.log_action(
        session, branch_id=branch_id, record_type=wf.RECORD_SELF_ASSESSMENT,
        record_id=a.id, actor_user_id=user_id,
        action="RESUBMIT" if resubmit else "SUBMIT")
    await wf.notify(
        session, branch_id=branch_id, user_id=approver_id,
        record_type=wf.RECORD_SELF_ASSESSMENT, record_id=a.id,
        message=f"Self-assessment for {a.assess_date} submitted for your approval.",
        actor_user_id=user_id)


async def _get_own(session, *, staff_id, assessment_id) -> SelfAssessment:
    a = (await session.execute(
        select(SelfAssessment).where(
            SelfAssessment.id == assessment_id,
            SelfAssessment.staff_id == staff_id,
            SelfAssessment.is_deleted == False,  # noqa: E712
        )
    )).scalar_one_or_none()
    if a is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assessment not found.")
    return a


async def submit_existing(
    session: AsyncSession, *, staff_id: uuid.UUID, assessment_id: uuid.UUID,
    user_id: uuid.UUID, approver_id: uuid.UUID | None = None,
) -> dict:
    a = await _get_own(session, staff_id=staff_id, assessment_id=assessment_id)
    if a.status_code not in _EDITABLE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"A {a.status_code} assessment can't be submitted.")
    branch_id = a.branch_id
    cats, _ = await _catalog(session, branch_id)
    rated_ids = {c.id for c in cats if not c.is_deduction}
    have = {
        s.category_id
        for s in (await session.execute(
            select(SelfAssessmentStar).where(
                SelfAssessmentStar.self_assessment_id == a.id,
                SelfAssessmentStar.is_deleted == False,  # noqa: E712
            )
        )).scalars().all()
    }
    if rated_ids - have:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Rate all four main categories before submitting.")
    await _do_submit(session, a=a, branch_id=branch_id,
                     chosen_approver_id=approver_id, user_id=user_id)
    return await _serialize(session, a)


async def withdraw(
    session: AsyncSession, *, staff_id: uuid.UUID, assessment_id: uuid.UUID, user_id: uuid.UUID,
) -> dict:
    a = await _get_own(session, staff_id=staff_id, assessment_id=assessment_id)
    if a.status_code != "PENDING":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only a pending assessment can be withdrawn.")
    prev = a.approver_id
    a.status_code = "DRAFT"
    a.submitted_at = None
    a.approver_id = None
    a.updated_by = user_id
    await session.flush()
    await wf.log_action(
        session, branch_id=a.branch_id, record_type=wf.RECORD_SELF_ASSESSMENT,
        record_id=a.id, actor_user_id=user_id, action="WITHDRAW")
    await wf.notify(
        session, branch_id=a.branch_id, user_id=prev,
        record_type=wf.RECORD_SELF_ASSESSMENT, record_id=a.id,
        message=f"Self-assessment for {a.assess_date} was withdrawn.", actor_user_id=user_id)
    return await _serialize(session, a)


async def get_for_date(
    session: AsyncSession, *, staff_id: uuid.UUID, on: date,
) -> dict | None:
    branch_id = await wf.resolve_branch_id(session, staff_id)
    a = (await session.execute(
        select(SelfAssessment).where(
            SelfAssessment.branch_id == branch_id,
            SelfAssessment.staff_id == staff_id,
            SelfAssessment.assess_date == on,
            SelfAssessment.is_deleted == False,  # noqa: E712
        )
    )).scalar_one_or_none()
    return await _serialize(session, a) if a else None


async def list_assessments(
    session: AsyncSession, *, staff_id: uuid.UUID, start: date, end: date,
) -> list[dict]:
    rows = list((await session.execute(
        select(SelfAssessment).where(
            SelfAssessment.staff_id == staff_id,
            SelfAssessment.assess_date >= start,
            SelfAssessment.assess_date <= end,
            SelfAssessment.is_deleted == False,  # noqa: E712
        ).order_by(SelfAssessment.assess_date.desc())
    )).scalars().all())
    return [await _serialize(session, a, with_history=False) for a in rows]
