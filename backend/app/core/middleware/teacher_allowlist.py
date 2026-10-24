"""Default-deny allowlist for teacher-only accounts.

A token whose only privileged role is ``teacher`` may reach ONLY the auth and
teacher-portal routes (``/api/v1/auth/*`` and ``/api/v1/me/*``); every other API
route returns 403. This is the spec's most important control: a new endpoint is
blocked for teachers by default, not by remembering to lock it.

Accounts that also hold an elevated role (a teacher who is also an admin) are
unaffected — the restriction applies only when ``teacher`` is the account's sole
privileged role.
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.config.settings import get_settings
from app.modules.auth.services.token_service import verify_access_token

# Roles that grant access beyond the teacher portal. A token carrying any of
# these is never treated as teacher-restricted.
ELEVATED_ROLES = frozenset({
    "super_admin", "branch_admin", "academic_head", "accounts",
    "device_operator", "floor_coordinator", "manager",
})


def _is_teacher_only(roles: list[str]) -> bool:
    rset = set(roles or [])
    return "teacher" in rset and not (rset & ELEVATED_ROLES)


class TeacherAllowlistMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        prefix = get_settings().API_V1_PREFIX.rstrip("/")
        self._prefix = prefix
        self._allowed = (f"{prefix}/auth/", f"{prefix}/me/")

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        # Only versioned API routes are gated; device/docs/health are untouched.
        if not path.startswith(f"{self._prefix}/"):
            return await call_next(request)

        token = request.cookies.get("access_token")
        if token:
            try:
                payload = verify_access_token(token)
            except Exception:  # noqa: BLE001 — invalid token: let auth deps 401
                payload = None
            if payload is not None and _is_teacher_only(payload.get("roles", [])):
                if not any(path.startswith(a) for a in self._allowed):
                    return JSONResponse(
                        status_code=403,
                        content={"error": {
                            "code": "TEACHER_FORBIDDEN",
                            "message": "Teachers can access only the teacher portal.",
                        }},
                    )
        return await call_next(request)
