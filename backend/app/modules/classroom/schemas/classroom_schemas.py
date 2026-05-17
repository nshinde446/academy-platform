import uuid

from pydantic import BaseModel


class ClassroomCreate(BaseModel):
    branch_id: uuid.UUID
    name: str
    code: str
    capacity: int = 30
    floor: str | None = None


class ClassroomUpdate(BaseModel):
    name: str | None = None
    code: str | None = None
    capacity: int | None = None
    floor: str | None = None


class ClassroomResponse(BaseModel):
    id: uuid.UUID
    branch_id: uuid.UUID
    name: str
    code: str
    capacity: int
    floor: str | None = None
    status: str
    model_config = {"from_attributes": True}
