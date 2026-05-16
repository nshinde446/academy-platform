import uuid
from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.modules.auth.repositories import user_repository
from app.modules.auth.services.token_service import verify_access_token


async def get_current_user(
    access_token: Annotated[str | None, Cookie()] = None,
    session: AsyncSession = Depends(get_db),
) -> dict:
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    from jose import JWTError

    try:
        payload = verify_access_token(access_token)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    user_id = uuid.UUID(payload["sub"])
    user = await user_repository.get_by_id(session, user_id)
    if not user or user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    return {
        "user_id": user.id,
        "roles": payload.get("roles", []),
        "branch_id": payload.get("branch_id"),
    }


def require_roles(allowed_roles: list[str]):
    async def dependency(current_user: dict = Depends(get_current_user)) -> dict:
        user_roles = current_user.get("roles", [])
        if "super_admin" in user_roles:
            return current_user
        if not any(role in allowed_roles for role in user_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient role",
            )
        return current_user

    return dependency


def require_permissions(required_permissions: list[str]):
    async def dependency(
        current_user: dict = Depends(get_current_user),
        session: AsyncSession = Depends(get_db),
    ) -> dict:
        user_roles = current_user.get("roles", [])
        if "super_admin" in user_roles:
            return current_user

        user_permissions = await user_repository.get_user_permissions(
            session, current_user["user_id"]
        )
        if not all(p in user_permissions for p in required_permissions):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current_user

    return dependency


def require_branch_access(branch_id_param: str = "branch_id"):
    async def dependency(
        current_user: dict = Depends(get_current_user),
        session: AsyncSession = Depends(get_db),
        **kwargs,
    ) -> dict:
        user_roles = current_user.get("roles", [])
        if "super_admin" in user_roles:
            return current_user

        return current_user

    return dependency
