import json
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.repositories import audit_repository


async def log_action(
    session: AsyncSession,
    *,
    user_id: uuid.UUID | None,
    action: str,
    table_name: str,
    record_id: uuid.UUID,
    old_values: dict | None = None,
    new_values: dict | None = None,
    ip_address: str | None = None,
    branch_id: uuid.UUID | None = None,
) -> None:
    await audit_repository.create_log(
        session,
        user_id=user_id,
        action=action,
        table_name=table_name,
        record_id=record_id,
        old_values=json.dumps(old_values, default=str) if old_values else None,
        new_values=json.dumps(new_values, default=str) if new_values else None,
        ip_address=ip_address,
        branch_id=branch_id,
    )
