import uuid
from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.modules.auth.repositories import user_repository
from app.modules.auth.services.token_service import verify_access_token

_MANAGER_ROLES = ("super_admin", "branch_admin")


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


def require_manager_or_audit(action: str, module: str):
    """Manager-only gate that AUDITS denied attempts.

    Allows super_admin / branch_admin (Manager) exactly as before — no access
    change. When anyone else attempts the privileged action (e.g. a Floor
    Coordinator hitting Delete or manual-mark) it writes an ``Access Denied``
    audit row before returning 403, so the Manager's audit report shows the
    attempt. Not flag-gated: logging a denial is always safe."""

    async def dependency(
        request: Request,
        current_user: dict = Depends(get_current_user),
        session: AsyncSession = Depends(get_db),
    ) -> dict:
        roles = current_user.get("roles", [])
        if any(r in _MANAGER_ROLES for r in roles):
            return current_user

        from app.modules.audit.services import audit_service

        branch_raw = current_user.get("branch_id")
        await audit_service.log_action(
            session,
            user_id=current_user["user_id"],
            action="Access Denied",
            table_name=module,
            record_id=current_user["user_id"],  # the actor; no target on a denial
            new_values={"attempted": action, "roles": roles},
            ip_address=request.client.host if request.client else None,
            branch_id=uuid.UUID(branch_raw) if branch_raw else None,
        )
        await session.commit()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role"
        )

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
