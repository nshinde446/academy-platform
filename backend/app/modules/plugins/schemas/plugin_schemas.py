import uuid
from datetime import datetime

from pydantic import BaseModel, field_validator


class PluginCreate(BaseModel):
    name: str
    version: str
    description: str | None = None
    entry_point: str
    branch_id: uuid.UUID | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v or len(v) > 100:
            raise ValueError("name must be 1-100 characters")
        return v

    @field_validator("version")
    @classmethod
    def validate_version(cls, v: str) -> str:
        if not v or len(v) > 20:
            raise ValueError("version must be 1-20 characters")
        return v


class PluginResponse(BaseModel):
    id: uuid.UUID
    name: str
    version: str
    description: str | None
    entry_point: str
    is_enabled: bool
    branch_id: uuid.UUID | None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PluginConfigCreate(BaseModel):
    key: str
    value: str
    is_secret: bool = False

    @field_validator("key")
    @classmethod
    def validate_key(cls, v: str) -> str:
        if not v or len(v) > 100:
            raise ValueError("key must be 1-100 characters")
        return v


class PluginConfigResponse(BaseModel):
    id: uuid.UUID
    plugin_id: uuid.UUID
    key: str
    value: str
    is_secret: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class PluginEventCreate(BaseModel):
    event_type: str
    handler: str

    @field_validator("event_type")
    @classmethod
    def validate_event_type(cls, v: str) -> str:
        if not v or len(v) > 50:
            raise ValueError("event_type must be 1-50 characters")
        return v


class PluginEventResponse(BaseModel):
    id: uuid.UUID
    plugin_id: uuid.UUID
    event_type: str
    handler: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
