import uuid

from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    first_name: str
    last_name: str
    status: str


class BranchRoleInfo(BaseModel):
    branch_id: uuid.UUID
    branch_name: str
    branch_code: str
    role_name: str


class UserMeResponse(BaseModel):
    id: uuid.UUID
    email: str
    first_name: str
    last_name: str
    status: str
    roles: list[str]
    permissions: list[str]
    branch_roles: list[BranchRoleInfo]
