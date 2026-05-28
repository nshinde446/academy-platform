from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config.settings import get_settings
from app.core.database.session import get_db
from app.modules.auth.permissions.rbac import get_current_user, require_roles
from app.modules.auth.schemas.auth_schemas import LoginRequest, UserMeResponse
from app.modules.auth.services import auth_service

settings = get_settings()
router = APIRouter(prefix="/auth", tags=["auth"])


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
