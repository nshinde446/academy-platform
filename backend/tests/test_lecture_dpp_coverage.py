"""DPP-coverage aggregate: completed lectures vs. those with a DPP.

A DPP is a Test(paper_type="DPP") whose source_lecture_id points back at the
lecture (set by the lectures "Generate DPP" → composer flow). Coverage counts
only *completed* lectures, and only DPP papers (not CPP/TEST).
"""

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.lectures.models.lecture_models import Lecture
from app.modules.lectures.repositories import lecture_repository
from app.modules.tests.models.test_models import Test

BRANCH_A_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
ACADEMIC_YEAR_ID = uuid.UUID("00000000-0000-0000-0000-000000000030")
SUBJECT_ID = uuid.UUID("00000000-0000-0000-0000-000000000050")
TEACHER_ID = uuid.UUID("00000000-0000-0000-0000-000000000060")
BATCH_A_ID = uuid.UUID("00000000-0000-0000-0000-000000000070")


def _lecture(status: str) -> Lecture:
    return Lecture(
        teacher_id=TEACHER_ID,
        batch_id=BATCH_A_ID,
        subject_id=SUBJECT_ID,
        scheduled_start=datetime(2026, 1, 1, 9, tzinfo=timezone.utc),
        scheduled_end=datetime(2026, 1, 1, 10, tzinfo=timezone.utc),
        lecture_status=status,
        delivery_mode="offline",
        branch_id=BRANCH_A_ID,
        academic_year_id=ACADEMIC_YEAR_ID,
        status="active",
        is_deleted=False,
    )


def _paper(paper_type: str, source_lecture_id: uuid.UUID | None) -> Test:
    return Test(
        name=f"{paper_type} paper",
        paper_type=paper_type,
        batch_id=BATCH_A_ID,
        subject_id=SUBJECT_ID,
        branch_id=BRANCH_A_ID,
        academic_year_id=ACADEMIC_YEAR_ID,
        test_status="DRAFT",
        source_lecture_id=source_lecture_id,
        status="active",
        is_deleted=False,
    )


@pytest.mark.asyncio
async def test_dpp_coverage_counts_only_completed_with_dpp(
    db_session: AsyncSession, seed_data
):
    done_a = _lecture("completed")
    done_b = _lecture("completed")
    scheduled = _lecture("scheduled")  # not completed → excluded from both counts
    db_session.add_all([done_a, done_b, scheduled])
    await db_session.flush()

    db_session.add_all(
        [
            _paper("DPP", done_a.id),  # counts
            _paper("TEST", done_b.id),  # wrong paper_type → does NOT count
            _paper("DPP", scheduled.id),  # DPP on a non-completed lecture → excluded
            _paper("DPP", None),  # not lecture-anchored → ignored
        ]
    )
    await db_session.flush()

    cov = await lecture_repository.dpp_coverage(db_session, BRANCH_A_ID)
    assert cov == {"completed": 2, "with_dpp": 1}


@pytest.mark.asyncio
async def test_dpp_coverage_dedupes_multiple_dpps_per_lecture(
    db_session: AsyncSession, seed_data
):
    """Two DPPs off the same lecture still count that lecture once."""
    done = _lecture("completed")
    db_session.add(done)
    await db_session.flush()
    db_session.add_all([_paper("DPP", done.id), _paper("DPP", done.id)])
    await db_session.flush()

    cov = await lecture_repository.dpp_coverage(db_session, BRANCH_A_ID)
    assert cov == {"completed": 1, "with_dpp": 1}


@pytest.mark.asyncio
async def test_dpp_coverage_empty(db_session: AsyncSession, seed_data):
    cov = await lecture_repository.dpp_coverage(db_session, BRANCH_A_ID)
    assert cov == {"completed": 0, "with_dpp": 0}
