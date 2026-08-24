"""Request/response schemas for RBAC access-control management (Manager only)."""

import uuid
from datetime import datetime

from pydantic import BaseModel


class BatchRef(BaseModel):
    id: uuid.UUID
    name: str


class CoordinatorBatchesResponse(BaseModel):
    """A Floor Coordinator's current batch assignments."""

    user_id: uuid.UUID
    batches: list[BatchRef]


class SetCoordinatorBatchesRequest(BaseModel):
    """Replace a coordinator's batch list (the whole set the Manager wants)."""

    batch_ids: list[uuid.UUID]


class AccountsGrantCreateRequest(BaseModel):
    user_id: uuid.UUID
    # None = branch-wide; set = a single batch.
    batch_id: uuid.UUID | None = None
    # None = permanent; otherwise the grant auto-expires at this instant.
    expires_at: datetime | None = None


class AccountsGrantResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    branch_id: uuid.UUID
    batch_id: uuid.UUID | None = None
    batch_name: str | None = None
    expires_at: datetime | None = None
    granted_by: uuid.UUID
    created_at: datetime
    model_config = {"from_attributes": True}
