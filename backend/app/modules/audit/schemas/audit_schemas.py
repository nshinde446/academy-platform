import uuid
from datetime import datetime

from pydantic import BaseModel


class AuditLogResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID | None
    action: str
    table_name: str
    record_id: uuid.UUID
    old_values: dict | None = None
    new_values: dict | None = None
    timestamp: datetime
    ip_address: str | None = None
    branch_id: uuid.UUID | None = None

    model_config = {"from_attributes": True}


class AuditLogListResponse(BaseModel):
    items: list[AuditLogResponse]
    total: int
