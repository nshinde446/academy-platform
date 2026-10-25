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


_INVALID = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
)


async def login(
    session: AsyncSession,
    identifier: str,
    password: str,
    *,
    ip: str | None = None,
    user_agent: str | None = None,
) -> tuple[str, str, str, bool]:
    """Authenticate by employee-code username OR email.

    Returns (access_token, refresh_token, jti, must_change_password). Failures
    return a generic "Invalid credentials" (no account enumeration) and record
    an auth event. Repeated failures lock the account per the teacher-portal
    config (default 5 fails / 15-min lock). Lockout and last-login bookkeeping
    live on the user row (migration 0067)."""
    from datetime import datetime, timezone

    from app.modules.teacher_portal.services import auth_events, config_service

    now = datetime.now(timezone.utc)
    ident = (identifier or "").strip()
    user = (
        await user_repository.get_by_username(session, ident)
        or await user_repository.get_by_email(session, ident)
    )
    cfg = await config_service.get_config(session)
    max_fail = int(cfg.get("lockout_attempts") or 5)
    lock_min = int(cfg.get("lockout_minutes") or 15)

    async def _fail_and_raise(exc: HTTPException) -> None:
        """Record the failure, then COMMIT it before raising — the request's own
        transaction would otherwise roll these security side-effects (the event
        and the failed-attempt / lockout counters) back on the error response."""
        await auth_events.record(
            session, event="login_fail", user_id=user.id if user else None,
            username_attempted=ident[:50], ip=ip, user_agent=user_agent,
        )
        await session.commit()
        raise exc

    # Unknown user: constant-ish path, generic error, still logged.
    if user is None:
        await _fail_and_raise(_INVALID)

    # Locked account: reject (generic) until the lock expires.
    locked_until = user.locked_until
    if locked_until is not None and locked_until.tzinfo is None:
        locked_until = locked_until.replace(tzinfo=timezone.utc)
    if locked_until is not None and locked_until > now:
        await _fail_and_raise(_INVALID)

    if not verify_password(password, user.password_hash):
        user.failed_attempts = (user.failed_attempts or 0) + 1
        if user.failed_attempts >= max_fail:
            from datetime import timedelta
            user.locked_until = now + timedelta(minutes=lock_min)
            user.failed_attempts = 0
            await session.flush()
            await auth_events.record(
                session, event="locked", user_id=user.id,
                username_attempted=ident[:50], ip=ip, user_agent=user_agent,
                detail=f"locked for {lock_min} min after {max_fail} failures",
            )
        await _fail_and_raise(_INVALID)

    if user.status != "active":
        await _fail_and_raise(
            HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is inactive")
        )

    # Success: reset counters, stamp last login, log, issue tokens.
    user.failed_attempts = 0
    user.locked_until = None
    user.last_login_at = now
    await session.flush()
    await auth_events.record(
        session, event="login_success", user_id=user.id,
        username_attempted=ident[:50], ip=ip, user_agent=user_agent,
    )

    roles = await user_repository.get_user_roles(session, user.id)
    access_token = create_access_token(user.id, roles, user.primary_branch_id)
    refresh_token, jti = create_refresh_token(user.id)
    await user_repository.save_refresh_token(session, user.id, jti, get_refresh_expiry())

    return access_token, refresh_token, jti, bool(user.must_change_password)


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
        must_change_password=bool(user.must_change_password),
    )
