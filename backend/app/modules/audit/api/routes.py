import json
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.modules.auth.permissions.rbac import require_roles
from app.modules.audit.repositories import audit_repository
from app.modules.audit.schemas.audit_schemas import (
    AuditLogListResponse,
    AuditLogResponse,
)

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/logs", response_model=AuditLogListResponse)
async def list_audit_logs(
    _current_user: dict = Depends(require_roles(["super_admin"])),
    session: AsyncSession = Depends(get_db),
    table_name: str | None = Query(None),
    record_id: uuid.UUID | None = Query(None),
    user_id: uuid.UUID | None = Query(None),
    action: str | None = Query(None),
    branch_id: uuid.UUID | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    logs, total = await audit_repository.get_logs(
        session,
        table_name=table_name,
        record_id=record_id,
        user_id=user_id,
        action=action,
        branch_id=branch_id,
        offset=offset,
        limit=limit,
    )

    items = []
    for log in logs:
        items.append(
            AuditLogResponse(
                id=log.id,
                user_id=log.user_id,
                action=log.action,
                table_name=log.table_name,
                record_id=log.record_id,
                old_values=json.loads(log.old_values) if log.old_values else None,
                new_values=json.loads(log.new_values) if log.new_values else None,
                timestamp=log.timestamp,
                ip_address=log.ip_address,
                branch_id=log.branch_id,
            )
        )

    return AuditLogListResponse(items=items, total=total)
