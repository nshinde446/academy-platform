import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models.audit_models import AuditLog


async def create_log(
    session: AsyncSession,
    *,
    user_id: uuid.UUID | None,
    action: str,
    table_name: str,
    record_id: uuid.UUID,
    old_values: str | None = None,
    new_values: str | None = None,
    ip_address: str | None = None,
    branch_id: uuid.UUID | None = None,
) -> AuditLog:
    log = AuditLog(
        user_id=user_id,
        action=action,
        table_name=table_name,
        record_id=record_id,
        old_values=old_values,
        new_values=new_values,
        ip_address=ip_address,
        branch_id=branch_id,
    )
    session.add(log)
    await session.flush()
    return log


async def get_logs(
    session: AsyncSession,
    *,
    table_name: str | None = None,
    record_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    action: str | None = None,
    branch_id: uuid.UUID | None = None,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[AuditLog], int]:
    query = select(AuditLog)
    count_query = select(func.count(AuditLog.id))

    if table_name:
        query = query.where(AuditLog.table_name == table_name)
        count_query = count_query.where(AuditLog.table_name == table_name)
    if record_id:
        query = query.where(AuditLog.record_id == record_id)
        count_query = count_query.where(AuditLog.record_id == record_id)
    if user_id:
        query = query.where(AuditLog.user_id == user_id)
        count_query = count_query.where(AuditLog.user_id == user_id)
    if action:
        query = query.where(AuditLog.action == action)
        count_query = count_query.where(AuditLog.action == action)
    if branch_id:
        query = query.where(AuditLog.branch_id == branch_id)
        count_query = count_query.where(AuditLog.branch_id == branch_id)

    query = query.order_by(AuditLog.timestamp.desc()).offset(offset).limit(limit)

    result = await session.execute(query)
    total_result = await session.execute(count_query)

    return list(result.scalars().all()), total_result.scalar_one()
