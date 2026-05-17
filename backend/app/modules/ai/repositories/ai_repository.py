import uuid

from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ai.models.ai_models import AIRequest, AIServiceConfig


async def create_request(session: AsyncSession, **kwargs) -> AIRequest:
    req = AIRequest(**kwargs)
    session.add(req)
    await session.flush()
    await session.refresh(req)
    return req


async def get_request(session: AsyncSession, request_id: uuid.UUID) -> AIRequest | None:
    result = await session.execute(
        select(AIRequest).where(
            AIRequest.id == request_id, AIRequest.is_deleted == False
        )
    )
    return result.scalar_one_or_none()


async def update_request(session: AsyncSession, req: AIRequest, **kwargs) -> AIRequest:
    for k, v in kwargs.items():
        setattr(req, k, v)
    await session.flush()
    await session.refresh(req)
    return req


async def list_requests(
    session: AsyncSession,
    request_type: str | None = None,
    request_status: str | None = None,
    branch_id: uuid.UUID | None = None,
    requested_by: uuid.UUID | None = None,
    offset: int = 0,
    limit: int = 50,
) -> list[AIRequest]:
    query = select(AIRequest).where(AIRequest.is_deleted == False)
    if request_type:
        query = query.where(AIRequest.request_type == request_type)
    if request_status:
        query = query.where(AIRequest.request_status == request_status)
    if branch_id:
        query = query.where(AIRequest.branch_id == branch_id)
    if requested_by:
        query = query.where(AIRequest.requested_by == requested_by)
    query = query.order_by(AIRequest.created_at.desc()).offset(offset).limit(limit)
    result = await session.execute(query)
    return list(result.scalars().all())


async def get_config(
    session: AsyncSession,
    service_name: str,
    key: str,
    branch_id: uuid.UUID | None = None,
) -> AIServiceConfig | None:
    query = select(AIServiceConfig).where(
        AIServiceConfig.service_name == service_name,
        AIServiceConfig.config_key == key,
        AIServiceConfig.is_deleted == False,
    )
    if branch_id:
        query = query.where(
            or_(AIServiceConfig.branch_id == branch_id, AIServiceConfig.branch_id == None)
        )
    else:
        query = query.where(AIServiceConfig.branch_id == None)
    query = query.order_by(AIServiceConfig.branch_id.desc().nulls_last()).limit(1)
    result = await session.execute(query)
    return result.scalar_one_or_none()


async def set_config(
    session: AsyncSession,
    service_name: str,
    key: str,
    value: str,
    is_secret: bool = False,
    branch_id: uuid.UUID | None = None,
) -> AIServiceConfig:
    existing = await get_config(session, service_name, key, branch_id)
    if existing and existing.branch_id == branch_id:
        existing.config_value = value
        existing.is_secret = is_secret
        await session.flush()
        await session.refresh(existing)
        return existing
    config = AIServiceConfig(
        service_name=service_name,
        config_key=key,
        config_value=value,
        is_secret=is_secret,
        branch_id=branch_id,
    )
    session.add(config)
    await session.flush()
    await session.refresh(config)
    return config
