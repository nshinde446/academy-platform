import uuid

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.analytics.models.analytics_models import (
    AnalyticsBatchSummary,
    AnalyticsStudentSummary,
    AnalyticsTeacherSummary,
)


# ─── Student Summary ──────────────────────────────────────────────────────────

async def get_student_summary(
    session: AsyncSession, student_id: uuid.UUID, branch_id: uuid.UUID
) -> AnalyticsStudentSummary | None:
    result = await session.execute(
        select(AnalyticsStudentSummary).where(
            AnalyticsStudentSummary.student_id == student_id,
            AnalyticsStudentSummary.branch_id == branch_id,
            AnalyticsStudentSummary.is_deleted == False,
        )
    )
    return result.scalar_one_or_none()


async def upsert_student_summary(
    session: AsyncSession, student_id: uuid.UUID, branch_id: uuid.UUID, **kwargs
) -> AnalyticsStudentSummary:
    existing = await get_student_summary(session, student_id, branch_id)
    if existing:
        for key, value in kwargs.items():
            setattr(existing, key, value)
        await session.flush()
        return existing
    summary = AnalyticsStudentSummary(
        student_id=student_id, branch_id=branch_id, **kwargs
    )
    session.add(summary)
    await session.flush()
    return summary


async def get_risk_students(
    session: AsyncSession, branch_id: uuid.UUID, threshold: float
) -> list[AnalyticsStudentSummary]:
    result = await session.execute(
        select(AnalyticsStudentSummary).where(
            AnalyticsStudentSummary.branch_id == branch_id,
            AnalyticsStudentSummary.risk_score >= threshold,
            AnalyticsStudentSummary.is_deleted == False,
        ).order_by(AnalyticsStudentSummary.risk_score.desc())
    )
    return list(result.scalars().all())


async def clear_student_summaries(session: AsyncSession, branch_id: uuid.UUID) -> None:
    await session.execute(
        delete(AnalyticsStudentSummary).where(
            AnalyticsStudentSummary.branch_id == branch_id
        )
    )


# ─── Teacher Summary ──────────────────────────────────────────────────────────

async def get_teacher_summary(
    session: AsyncSession, teacher_id: uuid.UUID, branch_id: uuid.UUID
) -> AnalyticsTeacherSummary | None:
    result = await session.execute(
        select(AnalyticsTeacherSummary).where(
            AnalyticsTeacherSummary.teacher_id == teacher_id,
            AnalyticsTeacherSummary.branch_id == branch_id,
            AnalyticsTeacherSummary.is_deleted == False,
        )
    )
    return result.scalar_one_or_none()


async def upsert_teacher_summary(
    session: AsyncSession, teacher_id: uuid.UUID, branch_id: uuid.UUID, **kwargs
) -> AnalyticsTeacherSummary:
    existing = await get_teacher_summary(session, teacher_id, branch_id)
    if existing:
        for key, value in kwargs.items():
            setattr(existing, key, value)
        await session.flush()
        return existing
    summary = AnalyticsTeacherSummary(
        teacher_id=teacher_id, branch_id=branch_id, **kwargs
    )
    session.add(summary)
    await session.flush()
    return summary


# ─── Batch Summary ─────────────────────────────────────────────────────────────

async def get_batch_summary(
    session: AsyncSession, batch_id: uuid.UUID, branch_id: uuid.UUID
) -> AnalyticsBatchSummary | None:
    result = await session.execute(
        select(AnalyticsBatchSummary).where(
            AnalyticsBatchSummary.batch_id == batch_id,
            AnalyticsBatchSummary.branch_id == branch_id,
            AnalyticsBatchSummary.is_deleted == False,
        )
    )
    return result.scalar_one_or_none()


async def upsert_batch_summary(
    session: AsyncSession, batch_id: uuid.UUID, branch_id: uuid.UUID, **kwargs
) -> AnalyticsBatchSummary:
    existing = await get_batch_summary(session, batch_id, branch_id)
    if existing:
        for key, value in kwargs.items():
            setattr(existing, key, value)
        await session.flush()
        return existing
    summary = AnalyticsBatchSummary(
        batch_id=batch_id, branch_id=branch_id, **kwargs
    )
    session.add(summary)
    await session.flush()
    return summary
