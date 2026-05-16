from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

bearer_scheme = HTTPBearer()


async def require_auth(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> None:
    """Placeholder auth dependency. Stage 2 will implement full JWT validation."""
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token validation not yet implemented",
        headers={"WWW-Authenticate": "Bearer"},
    )
