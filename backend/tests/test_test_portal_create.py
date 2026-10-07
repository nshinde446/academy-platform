"""Test Portal — per-subject manual flow, Section 1 (Schedule a Test).

Covers the create-test extensions that coexist with the ZipGrade/OMR flow:
multi-batch scheduling, per-subject total marks, and the JEE-only Question Type.
"""

import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.modules.academic.models.academic_models import Course
from app.modules.batch.models.batch_models import Batch
from app.modules.tests.models.test_models import TestBatch, TestSubject
from app.modules.tests.services import test_service


async def _create(db_session, seed_data, data):
    data = {"name": "PCM Test — 31 Aug", **data}
    test = await test_service.create_test(
        db_session, data, current_user_id=seed_data["admin_user"].id,
    )
    await db_session.flush()
    return test


async def _cet_batch(db_session, seed_data) -> Batch:
    """A non-JEE (CET) batch: fresh course so JEE detection is false."""
    course = Course(
        id=uuid.uuid4(), branch_id=seed_data["branch_a"].id,
        name="MHT-CET 12th", code="CET-12", duration_years=1, is_deleted=False,
    )
    db_session.add(course)
    await db_session.flush()
    batch = Batch(
        id=uuid.uuid4(), branch_id=seed_data["branch_a"].id,
        start_academic_year_id=seed_data["academic_year"].id,
        end_academic_year_id=seed_data["academic_year"].id,
        course_id=course.id, name="11th CET-1", code="CET-1", capacity=60,
        is_deleted=False,
    )
    db_session.add(batch)
    await db_session.flush()
    return batch


@pytest.mark.usefixtures("seed_data")
async def test_create_multi_batch_and_per_subject_marks(db_session, seed_data):
    test = await _create(db_session, seed_data, {
        "batch_ids": [seed_data["batch"].id, seed_data["batch_b"].id],
        "subjects": [{"subject_id": seed_data["subject"].id, "total_marks": 80.0}],
    })

    # Primary batch is the first; both batches recorded in test_batches.
    assert test.batch_id == seed_data["batch"].id
    batch_rows = (await db_session.execute(
        select(TestBatch).where(TestBatch.test_id == test.id, TestBatch.is_deleted == False)
    )).scalars().all()
    assert {b.batch_id for b in batch_rows} == {seed_data["batch"].id, seed_data["batch_b"].id}
    assert sorted(test.batch_ids) == sorted([seed_data["batch"].id, seed_data["batch_b"].id])

    # Per-subject total marks stored on test_subjects.
    subj = (await db_session.execute(
        select(TestSubject).where(TestSubject.test_id == test.id, TestSubject.is_deleted == False)
    )).scalar_one()
    assert subj.subject_id == seed_data["subject"].id
    assert subj.total_marks == 80.0


@pytest.mark.usefixtures("seed_data")
async def test_question_type_allowed_for_jee_batch(db_session, seed_data):
    # The seed batch's course is "JEE Advanced" (JEE-ADV) -> a JEE batch.
    test = await _create(db_session, seed_data, {
        "batch_ids": [seed_data["batch"].id],
        "subject_ids": [seed_data["subject"].id],
        "question_type": "MCQ_NUMERICAL",
    })
    assert test.question_type == "MCQ_NUMERICAL"


@pytest.mark.usefixtures("seed_data")
async def test_question_type_rejected_for_non_jee_batch(db_session, seed_data):
    cet = await _cet_batch(db_session, seed_data)
    with pytest.raises(HTTPException) as ei:
        await _create(db_session, seed_data, {
            "batch_ids": [cet.id],
            "subject_ids": [seed_data["subject"].id],
            "question_type": "MCQ_ONLY",
        })
    assert ei.value.status_code == 422
    assert "JEE" in ei.value.detail


@pytest.mark.usefixtures("seed_data")
async def test_legacy_single_batch_create_still_works(db_session, seed_data):
    # The OMR / composer shape (single batch_id + subject_id) is unchanged.
    test = await _create(db_session, seed_data, {
        "batch_id": seed_data["batch"].id,
        "subject_id": seed_data["subject"].id,
        "total_marks": 200.0,
    })
    assert test.batch_id == seed_data["batch"].id
    assert test.question_type == "NA"
    batch_rows = (await db_session.execute(
        select(TestBatch).where(TestBatch.test_id == test.id, TestBatch.is_deleted == False)
    )).scalars().all()
    assert len(batch_rows) == 1  # the single batch is still mirrored into test_batches
