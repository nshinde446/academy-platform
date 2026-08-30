import uuid

from fastapi import HTTPException, status
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.repositories import user_repository
from app.modules.auth.schemas.auth_schemas import BranchRoleInfo, UserMeResponse
from app.modules.auth.services.token_service import (
    create_access_token,
    create_refresh_token,
    get_refresh_expiry,
    verify_refresh_token,
)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


async def login(
    session: AsyncSession, email: str, password: str
) -> tuple[str, str, str]:
    """Returns (access_token, refresh_token, jti)."""
    user = await user_repository.get_by_email(session, email)
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    if user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive",
        )

    roles = await user_repository.get_user_roles(session, user.id)
    access_token = create_access_token(user.id, roles, user.primary_branch_id)
    refresh_token, jti = create_refresh_token(user.id)

    await user_repository.save_refresh_token(
        session, user.id, jti, get_refresh_expiry()
    )

    return access_token, refresh_token, jti


async def logout(session: AsyncSession, jti: str) -> None:
    await user_repository.revoke_refresh_token(session, jti)


async def refresh(
    session: AsyncSession, refresh_token_raw: str
) -> tuple[str, str, str]:
    """Returns (new_access_token, new_refresh_token, new_jti)."""
    from jose import JWTError

    try:
        payload = verify_refresh_token(refresh_token_raw)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    old_jti = payload.get("jti")
    user_id = uuid.UUID(payload["sub"])

    valid = await user_repository.is_refresh_token_valid(session, old_jti)
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token revoked or expired",
        )

    await user_repository.revoke_refresh_token(session, old_jti)

    user = await user_repository.get_by_id(session, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
        )

    roles = await user_repository.get_user_roles(session, user.id)
    new_access = create_access_token(user.id, roles, user.primary_branch_id)
    new_refresh, new_jti = create_refresh_token(user.id)

    await user_repository.save_refresh_token(
        session, user.id, new_jti, get_refresh_expiry()
    )

    return new_access, new_refresh, new_jti


async def get_me(session: AsyncSession, user_id: uuid.UUID) -> UserMeResponse:
    user = await user_repository.get_by_id(session, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    roles = await user_repository.get_user_roles(session, user.id)
    permissions = await user_repository.get_user_permissions(session, user.id)
    branch_roles_raw = await user_repository.get_user_branch_roles(session, user.id)

    branch_roles = [
        BranchRoleInfo(
            branch_id=br["branch_id"],
            branch_name=br["branch_name"],
            branch_code=br["branch_code"],
            role_name=br["role_name"],
        )
        for br in branch_roles_raw
    ]

    from app.core.config.settings import get_settings

    dev_emails = {
        e.strip().lower()
        for e in get_settings().DEVELOPER_EMAILS.split(",")
        if e.strip()
    }

    return UserMeResponse(
        id=user.id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        status=user.status,
        roles=roles,
        permissions=permissions,
        branch_roles=branch_roles,
        is_developer=(user.email or "").lower() in dev_emails,
    )
