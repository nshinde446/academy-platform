import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models.auth_models import (
    Branch,
    Permission,
    RefreshToken,
    Role,
    RolePermission,
    User,
    UserBranchRole,
    UserRole,
)


async def get_by_email(session: AsyncSession, email: str) -> User | None:
    result = await session.execute(
        select(User).where(User.email == email, User.is_deleted == False)  # noqa: E712
    )
    return result.scalar_one_or_none()


async def get_by_id(session: AsyncSession, user_id: uuid.UUID) -> User | None:
    result = await session.execute(
        select(User).where(User.id == user_id, User.is_deleted == False)  # noqa: E712
    )
    return result.scalar_one_or_none()


async def get_user_roles(session: AsyncSession, user_id: uuid.UUID) -> list[str]:
    result = await session.execute(
        select(Role.name)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(UserRole.user_id == user_id, UserRole.is_deleted == False)  # noqa: E712
    )
    return list(result.scalars().all())


async def get_user_permissions(session: AsyncSession, user_id: uuid.UUID) -> list[str]:
    result = await session.execute(
        select(Permission.name)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .join(UserRole, UserRole.role_id == RolePermission.role_id)
        .where(UserRole.user_id == user_id, UserRole.is_deleted == False)  # noqa: E712
    )
    return list(result.scalars().all())


async def get_user_branch_roles(
    session: AsyncSession, user_id: uuid.UUID
) -> list[dict]:
    result = await session.execute(
        select(
            UserBranchRole.branch_id,
            Branch.name.label("branch_name"),
            Branch.code.label("branch_code"),
            Role.name.label("role_name"),
        )
        .join(Branch, Branch.id == UserBranchRole.branch_id)
        .join(Role, Role.id == UserBranchRole.role_id)
        .where(
            UserBranchRole.user_id == user_id,
            UserBranchRole.is_deleted == False,  # noqa: E712
        )
    )
    return [
        {
            "branch_id": row.branch_id,
            "branch_name": row.branch_name,
            "branch_code": row.branch_code,
            "role_name": row.role_name,
        }
        for row in result.all()
    ]


async def has_branch_access(
    session: AsyncSession, user_id: uuid.UUID, branch_id: uuid.UUID
) -> bool:
    result = await session.execute(
        select(UserBranchRole.id)
        .where(
            UserBranchRole.user_id == user_id,
            UserBranchRole.branch_id == branch_id,
            UserBranchRole.is_deleted == False,  # noqa: E712
        )
        .limit(1)
    )
    return result.scalar_one_or_none() is not None


async def is_super_admin(session: AsyncSession, user_id: uuid.UUID) -> bool:
    roles = await get_user_roles(session, user_id)
    return "super_admin" in roles


async def has_permission(
    session: AsyncSession, user_id: uuid.UUID, permission_name: str
) -> bool:
    permissions = await get_user_permissions(session, user_id)
    return permission_name in permissions


# ── admin user management ────────────────────────────────────────────────────


async def list_users(session: AsyncSession) -> list[User]:
    """All non-deleted users, newest first (the admin roster)."""
    result = await session.execute(
        select(User)
        .where(User.is_deleted == False)  # noqa: E712
        .order_by(User.created_at.desc())
    )
    return list(result.scalars().all())


async def roles_for_users(
    session: AsyncSession, user_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[str]]:
    """user_id -> [role names], batched for the roster (avoids N+1)."""
    if not user_ids:
        return {}
    result = await session.execute(
        select(UserRole.user_id, Role.name)
        .join(Role, Role.id == UserRole.role_id)
        .where(
            UserRole.user_id.in_(user_ids),
            UserRole.is_deleted == False,  # noqa: E712
        )
    )
    out: dict[uuid.UUID, list[str]] = {}
    for user_id, role_name in result.all():
        out.setdefault(user_id, []).append(role_name)
    return out


async def get_role_by_name(session: AsyncSession, name: str) -> Role | None:
    result = await session.execute(
        select(Role).where(Role.name == name, Role.is_deleted == False)  # noqa: E712
    )
    return result.scalar_one_or_none()


async def list_roles(session: AsyncSession) -> list[Role]:
    result = await session.execute(
        select(Role).where(Role.is_deleted == False).order_by(Role.display_name)  # noqa: E712
    )
    return list(result.scalars().all())


async def count_active_users_with_role(session: AsyncSession, role_name: str) -> int:
    """How many active, non-deleted users currently hold a role — used to guard
    against removing/deactivating the last super_admin (lock-out prevention)."""
    result = await session.execute(
        select(func.count(func.distinct(User.id)))
        .select_from(User)
        .join(UserRole, UserRole.user_id == User.id)
        .join(Role, Role.id == UserRole.role_id)
        .where(
            Role.name == role_name,
            User.status == "active",
            User.is_deleted == False,  # noqa: E712
            UserRole.is_deleted == False,  # noqa: E712
        )
    )
    return int(result.scalar_one())


async def create_user(
    session: AsyncSession,
    *,
    email: str,
    password_hash: str,
    first_name: str,
    last_name: str,
    phone: str | None,
    primary_branch_id: uuid.UUID | None,
    created_by: uuid.UUID | None,
) -> User:
    user = User(
        email=email,
        password_hash=password_hash,
        first_name=first_name,
        last_name=last_name,
        phone=phone,
        primary_branch_id=primary_branch_id,
        status="active",
        is_deleted=False,
        created_by=created_by,
    )
    session.add(user)
    await session.flush()
    return user


async def set_user_role(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    role_id: uuid.UUID,
    branch_id: uuid.UUID | None,
) -> None:
    """Make ``role_id`` the user's sole role. Soft-deletes any existing role
    mappings first so a role change never leaves a stale grant behind."""
    for model in (UserRole, UserBranchRole):
        rows = (await session.execute(
            select(model).where(
                model.user_id == user_id,
                model.is_deleted == False,  # noqa: E712
            )
        )).scalars().all()
        for row in rows:
            row.is_deleted = True
    session.add(UserRole(user_id=user_id, role_id=role_id, status="active", is_deleted=False))
    if branch_id is not None:
        session.add(UserBranchRole(
            user_id=user_id, branch_id=branch_id, role_id=role_id,
            status="active", is_deleted=False,
        ))
    await session.flush()


async def set_password(
    session: AsyncSession, user: User, password_hash: str
) -> None:
    user.password_hash = password_hash
    await session.flush()


async def revoke_all_refresh_tokens(session: AsyncSession, user_id: uuid.UUID) -> None:
    """Revoke every live refresh token for a user — used when deactivating,
    deleting, or resetting a password so existing sessions can't continue."""
    now = datetime.now(timezone.utc)
    tokens = (await session.execute(
        select(RefreshToken).where(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked_at == None,  # noqa: E711
        )
    )).scalars().all()
    for token in tokens:
        token.revoked_at = now
    await session.flush()


async def save_refresh_token(
    session: AsyncSession,
    user_id: uuid.UUID,
    jti: str,
    expires_at: datetime,
) -> None:
    token = RefreshToken(user_id=user_id, jti=jti, expires_at=expires_at)
    session.add(token)
    await session.flush()


async def revoke_refresh_token(session: AsyncSession, jti: str) -> None:
    result = await session.execute(
        select(RefreshToken).where(RefreshToken.jti == jti)
    )
    token = result.scalar_one_or_none()
    if token:
        token.revoked_at = datetime.now(timezone.utc)
        await session.flush()


async def is_refresh_token_valid(session: AsyncSession, jti: str) -> bool:
    result = await session.execute(
        select(RefreshToken).where(
            RefreshToken.jti == jti,
            RefreshToken.revoked_at == None,  # noqa: E711
            RefreshToken.expires_at > datetime.now(timezone.utc),
        )
    )
    return result.scalar_one_or_none() is not None
