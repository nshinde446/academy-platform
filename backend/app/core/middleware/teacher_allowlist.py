"""Default-deny allowlist for teacher-portal accounts.

A token whose only role is ``teacher_portal`` (the dedicated read-only login the
admin issues to teaching staff) may reach ONLY the auth and teacher-portal routes
(``/api/v1/auth/*`` and ``/api/v1/me/*``); every other API route returns 403.
This is the spec's most important control: a new endpoint is blocked for portal
accounts by default, not by remembering to lock it.

Deliberately keyed on ``teacher_portal``, NOT the existing ``teacher`` role —
the latter is a broadly-permissioned academic role (DPPs, reports, marks) that
must keep its access. A portal account holds only ``teacher_portal``; any account
that also holds the ``teacher`` role or an elevated role is never restricted.
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.config.settings import get_settings
from app.modules.auth.services.token_service import verify_access_token

# The dedicated read-only portal role (distinct from the academic "teacher").
PORTAL_ROLE = "teacher_portal"

# Any of these grants access beyond the portal; a token carrying one is never
# treated as portal-restricted (includes the academic "teacher" role).
FULL_ACCESS_ROLES = frozenset({
    "super_admin", "branch_admin", "academic_head", "accounts",
    "device_operator", "floor_coordinator", "manager", "teacher",
})


def _is_portal_only(roles: list[str]) -> bool:
    rset = set(roles or [])
    return PORTAL_ROLE in rset and not (rset & FULL_ACCESS_ROLES)


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
            if payload is not None and _is_portal_only(payload.get("roles", [])):
                if not any(path.startswith(a) for a in self._allowed):
                    return JSONResponse(
                        status_code=403,
                        content={"error": {
                            "code": "TEACHER_FORBIDDEN",
                            "message": "This account can access only the teacher portal.",
                        }},
                    )
        return await call_next(request)
