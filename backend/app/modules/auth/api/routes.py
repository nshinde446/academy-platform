import uuid
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config.settings import get_settings
from app.core.database.session import get_db
from app.modules.auth.permissions.rbac import get_current_user, require_roles
from app.modules.auth.schemas.auth_schemas import (
    AdminUserResponse,
    ChangePasswordRequest,
    LoginRequest,
    PasswordResetRequest,
    RoleOption,
    UserCreateRequest,
    UserMeResponse,
    UserUpdateRequest,
)
from app.modules.auth.services import auth_service, user_admin_service

settings = get_settings()
router = APIRouter(prefix="/auth", tags=["auth"])

# Who may manage staff accounts.
_USER_ADMIN_ROLES = ["super_admin", "branch_admin"]


def _actor_branch_id(current_user: dict) -> uuid.UUID | None:
    """The acting admin's branch from the token (stored as a string)."""
    raw = current_user.get("branch_id")
    return uuid.UUID(raw) if raw else None


def _set_auth_cookies(response: Response, access_token: str, refresh_token: str):
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        # path="/" (was /api/v1/auth/refresh) so the page middleware can
        # see a live session and avoid bouncing to /login when only the
        # short-lived access token has expired. Still httpOnly + only used
        # by the /refresh endpoint server-side.
        path="/",
    )


def _clear_auth_cookies(response: Response):
    response.delete_cookie(key="access_token", path="/")
    response.delete_cookie(key="refresh_token", path="/")
    # Also clear the legacy narrowly-scoped cookie from before the path
    # was widened, so logout fully signs out older sessions.
    response.delete_cookie(key="refresh_token", path="/api/v1/auth/refresh")


@router.post("/login")
async def login(
    body: LoginRequest,
    response: Response,
    session: AsyncSession = Depends(get_db),
):
    access_token, refresh_token, _jti = await auth_service.login(
        session, body.email, body.password
    )
    _set_auth_cookies(response, access_token, refresh_token)
    return {"message": "Login successful"}


@router.post("/logout")
async def logout(
    response: Response,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    refresh_token: Annotated[str | None, Cookie()] = None,
):
    if refresh_token:
        from jose import JWTError

        from app.modules.auth.services.token_service import verify_refresh_token

        try:
            payload = verify_refresh_token(refresh_token)
            jti = payload.get("jti")
            if jti:
                await auth_service.logout(session, jti)
        except JWTError:
            pass

    _clear_auth_cookies(response)
    return {"message": "Logged out successfully"}


@router.post("/refresh")
async def refresh(
    response: Response,
    session: AsyncSession = Depends(get_db),
    refresh_token: Annotated[str | None, Cookie()] = None,
):
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No refresh token",
        )

    new_access, new_refresh, _jti = await auth_service.refresh(session, refresh_token)
    _set_auth_cookies(response, new_access, new_refresh)
    return {"message": "Token refreshed"}


@router.get("/me", response_model=UserMeResponse)
async def get_me(
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    return await auth_service.get_me(session, current_user["user_id"])


@router.post("/change-password")
async def change_password(
    body: ChangePasswordRequest,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Signed-in user changes their own password (e.g. off a temp password)."""
    await user_admin_service.change_own_password(
        session,
        user_id=current_user["user_id"],
        current_password=body.current_password,
        new_password=body.new_password,
    )
    return {"message": "Password changed"}


# ── admin user management (no public signup) ─────────────────────────────────


@router.get("/roles", response_model=list[RoleOption])
async def list_roles(
    current_user: dict = Depends(require_roles(_USER_ADMIN_ROLES)),
    session: AsyncSession = Depends(get_db),
):
    """Assignable roles for the user-admin picker."""
    return await user_admin_service.list_roles(session)


@router.get("/users", response_model=list[AdminUserResponse])
async def list_users(
    current_user: dict = Depends(require_roles(_USER_ADMIN_ROLES)),
    session: AsyncSession = Depends(get_db),
):
    return await user_admin_service.list_users(session)


@router.post("/users", response_model=AdminUserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: UserCreateRequest,
    current_user: dict = Depends(require_roles(_USER_ADMIN_ROLES)),
    session: AsyncSession = Depends(get_db),
):
    return await user_admin_service.create_user(
        session,
        body=body,
        actor_id=current_user["user_id"],
        actor_roles=current_user.get("roles", []),
        branch_id=_actor_branch_id(current_user),
    )


@router.patch("/users/{user_id}", response_model=AdminUserResponse)
async def update_user(
    user_id: uuid.UUID,
    body: UserUpdateRequest,
    current_user: dict = Depends(require_roles(_USER_ADMIN_ROLES)),
    session: AsyncSession = Depends(get_db),
):
    return await user_admin_service.update_user(
        session,
        user_id=user_id,
        body=body,
        actor_id=current_user["user_id"],
        actor_roles=current_user.get("roles", []),
        branch_id=_actor_branch_id(current_user),
    )


@router.post("/users/{user_id}/reset-password")
async def reset_user_password(
    user_id: uuid.UUID,
    body: PasswordResetRequest,
    current_user: dict = Depends(require_roles(_USER_ADMIN_ROLES)),
    session: AsyncSession = Depends(get_db),
):
    await user_admin_service.reset_password(
        session, user_id=user_id, new_password=body.password
    )
    return {"message": "Password reset"}


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: uuid.UUID,
    current_user: dict = Depends(require_roles(_USER_ADMIN_ROLES)),
    session: AsyncSession = Depends(get_db),
):
    await user_admin_service.delete_user(
        session, user_id=user_id, actor_id=current_user["user_id"]
    )
    return {"message": "User deleted"}


@router.get("/branch-test/{branch_id}")
async def branch_test(
    branch_id: str,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    import uuid

    from app.modules.auth.repositories import user_repository

    branch_uuid = uuid.UUID(branch_id)
    user_roles = current_user.get("roles", [])

    if "super_admin" not in user_roles:
        has_access = await user_repository.has_branch_access(
            session, current_user["user_id"], branch_uuid
        )
        if not has_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No access to this branch",
            )

    return {"message": "Branch access granted", "branch_id": branch_id}
