import uuid

from pydantic import BaseModel


class TeacherCreate(BaseModel):
    branch_id: uuid.UUID
    first_name: str
    last_name: str
    email: str | None = None
    phone: str | None = None
    qualification: str | None = None
    user_id: uuid.UUID | None = None


class TeacherUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    phone: str | None = None
    qualification: str | None = None


class TeacherResponse(BaseModel):
    id: uuid.UUID
    branch_id: uuid.UUID
    user_id: uuid.UUID | None = None
    first_name: str
    last_name: str
    email: str | None = None
    phone: str | None = None
    qualification: str | None = None
    status: str
    model_config = {"from_attributes": True}
