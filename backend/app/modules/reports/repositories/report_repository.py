import uuid

from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.reports.models.report_models import ReportJob, ReportTemplate


async def create_template(
    session: AsyncSession, **kwargs
) -> ReportTemplate:
    template = ReportTemplate(**kwargs)
    session.add(template)
    await session.flush()
    return template


async def get_template(
    session: AsyncSession, template_id: uuid.UUID
) -> ReportTemplate | None:
    result = await session.execute(
        select(ReportTemplate).where(
            ReportTemplate.id == template_id,
            ReportTemplate.is_deleted == False,
        )
    )
    return result.scalar_one_or_none()


async def list_templates(
    session: AsyncSession,
    branch_id: uuid.UUID | None = None,
    report_type: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> list[ReportTemplate]:
    stmt = select(ReportTemplate).where(
        ReportTemplate.is_deleted == False,
        ReportTemplate.is_active == True,
    )
    if branch_id is not None:
        stmt = stmt.where(
            or_(
                ReportTemplate.branch_id == branch_id,
                ReportTemplate.branch_id.is_(None),
            )
        )
    if report_type is not None:
        stmt = stmt.where(ReportTemplate.report_type == report_type)
    stmt = stmt.offset(offset).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def update_template(
    session: AsyncSession, template: ReportTemplate, **kwargs
) -> ReportTemplate:
    for key, value in kwargs.items():
        setattr(template, key, value)
    await session.flush()
    await session.refresh(template)
    return template


async def create_job(session: AsyncSession, **kwargs) -> ReportJob:
    job = ReportJob(**kwargs)
    session.add(job)
    await session.flush()
    return job


async def get_job(
    session: AsyncSession, job_id: uuid.UUID
) -> ReportJob | None:
    result = await session.execute(
        select(ReportJob).where(
            ReportJob.id == job_id,
            ReportJob.is_deleted == False,
        )
    )
    return result.scalar_one_or_none()


async def update_job(
    session: AsyncSession, job: ReportJob, **kwargs
) -> ReportJob:
    for key, value in kwargs.items():
        setattr(job, key, value)
    await session.flush()
    await session.refresh(job)
    return job


async def list_jobs(
    session: AsyncSession,
    requested_by: uuid.UUID | None = None,
    branch_id: uuid.UUID | None = None,
    job_status: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> list[ReportJob]:
    stmt = select(ReportJob).where(ReportJob.is_deleted == False)
    if requested_by is not None:
        stmt = stmt.where(ReportJob.requested_by == requested_by)
    if branch_id is not None:
        stmt = stmt.where(ReportJob.branch_id == branch_id)
    if job_status is not None:
        stmt = stmt.where(ReportJob.job_status == job_status)
    stmt = stmt.order_by(ReportJob.created_at.desc()).offset(offset).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())
