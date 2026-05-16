import uuid
from datetime import datetime, timezone

from sqlalchemy import select
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
