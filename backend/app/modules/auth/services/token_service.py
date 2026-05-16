import uuid
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

from app.core.config.settings import get_settings

settings = get_settings()


def create_access_token(
    user_id: uuid.UUID,
    roles: list[str],
    branch_id: uuid.UUID | None = None,
) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "roles": roles,
        "branch_id": str(branch_id) if branch_id else None,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(user_id: uuid.UUID) -> tuple[str, str]:
    """Returns (encoded_token, jti)."""
    jti = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "jti": jti,
        "iat": now,
        "exp": now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return token, jti


def verify_access_token(token: str) -> dict:
    """Returns decoded payload or raises JWTError."""
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    if payload.get("type") != "access":
        raise JWTError("Invalid token type")
    return payload


def verify_refresh_token(token: str) -> dict:
    """Returns decoded payload or raises JWTError."""
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    if payload.get("type") != "refresh":
        raise JWTError("Invalid token type")
    return payload


def get_refresh_expiry() -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
