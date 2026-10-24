import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database.base import Base, BaseModel


class Branch(BaseModel):
    __tablename__ = "branch"

    institute_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("institutes.id"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # IANA timezone for all local-day attendance logic (sign-in/out bucketing,
    # the nightly absent sweep). Per-branch so branches can differ; defaults to
    # Asia/Kolkata. See docs/biometric-attendance-design.md §2.3.
    timezone: Mapped[str] = mapped_column(
        String(64), nullable=False, server_default="Asia/Kolkata", default="Asia/Kolkata"
    )


class User(BaseModel):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    primary_branch_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("branch.id"), nullable=True
    )

    # ── Teacher Login account-lifecycle fields (migration 0067) ─────────────
    # Teacher accounts log in by employee code (username), which links to the
    # staff record the read-only portal serves. Email-login users leave these
    # null. Uniqueness (case-insensitive username, one user per staff) is
    # enforced by partial indexes in the migration. The existing ``status``
    # column (BaseModel) carries active/inactive — no separate is_active.
    username: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # use_alter breaks the users<->staff<->teachers FK cycle for metadata table
    # ordering (staff/teachers already reference users); the migration adds the
    # real FK on Postgres.
    staff_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("staff.id", use_alter=True, name="fk_users_staff_id"),
        nullable=True,
    )
    must_change_password: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false", default=False
    )
    password_changed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    failed_attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0", default=0
    )
    locked_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class Role(BaseModel):
    __tablename__ = "roles"

    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)


class Permission(BaseModel):
    __tablename__ = "permissions"

    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    module: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)


class UserRole(BaseModel):
    __tablename__ = "user_roles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=False
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("roles.id"), nullable=False
    )


class RolePermission(BaseModel):
    __tablename__ = "role_permissions"

    role_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("roles.id"), nullable=False
    )
    permission_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("permissions.id"), nullable=False
    )


class UserBranchRole(BaseModel):
    __tablename__ = "user_branch_roles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=False
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("branch.id"), nullable=False
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("roles.id"), nullable=False
    )


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=False
    )
    jti: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


# Recognised auth_events.event values (append-only login/account activity log).
AUTH_EVENT_TYPES = frozenset({
    "login_success", "login_fail", "locked", "unlocked",
    "password_changed", "password_reset", "account_created",
    "account_disabled", "account_enabled", "idor_attempt",
})


class AuthEvent(Base):
    """Append-only record of login + account-lifecycle activity for the teacher
    login module (migration 0067). Distinct from the business audit log: this is
    the security/login trail (successes, failures, lockouts, IDOR attempts)."""

    __tablename__ = "auth_events"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # Nullable: a failed login for an unknown username has no user_id.
    user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    username_attempted: Mapped[str | None] = mapped_column(String(50), nullable=True)
    event: Mapped[str] = mapped_column(String(40), nullable=False)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(400), nullable=True)
    # The admin who performed an account action (reset/disable/…); null for
    # self-service events like a login.
    actor_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    detail: Mapped[str | None] = mapped_column(String(500), nullable=True)


class TeacherPortalConfig(Base):
    """Key/value settings for the teacher portal, seeded with the spec defaults
    (migration 0067) so they change without a deploy. ``value`` is JSON so each
    key keeps its natural type (string / int / bool)."""

    __tablename__ = "teacher_portal_config"

    key: Mapped[str] = mapped_column(String(50), primary_key=True)
    value: Mapped[object] = mapped_column(JSON, nullable=False)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
