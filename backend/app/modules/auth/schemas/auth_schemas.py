import uuid

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


# ── admin user management ────────────────────────────────────────────────────

# Password floor shared by admin-set temp passwords and self-service changes.
_PASSWORD = Field(min_length=8, max_length=128)


class RoleOption(BaseModel):
    """An assignable role for the admin picker (from the roles table)."""

    name: str
    display_name: str


class UserCreateRequest(BaseModel):
    email: EmailStr
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    phone: str | None = Field(default=None, max_length=20)
    role: str  # role name; validated against the roles table
    password: str = _PASSWORD  # temp password the admin communicates to the user


class UserUpdateRequest(BaseModel):
    """Partial edit of a user's profile / role / active state."""

    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    phone: str | None = Field(default=None, max_length=20)
    role: str | None = None
    status: str | None = None  # "active" | "inactive"


class PasswordResetRequest(BaseModel):
    """Admin resets another user's password to a new temp value."""

    password: str = _PASSWORD


class ChangePasswordRequest(BaseModel):
    """A signed-in user changes their own password."""

    current_password: str
    new_password: str = _PASSWORD


class AdminUserResponse(BaseModel):
    id: uuid.UUID
    email: str
    first_name: str
    last_name: str
    phone: str | None
    status: str
    roles: list[str]


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
    # True only for emails in settings.DEVELOPER_EMAILS — gates the /dev
    # monitoring dashboard (by email, independent of role).
    is_developer: bool = False
