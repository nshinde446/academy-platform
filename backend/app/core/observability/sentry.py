"""Sentry error reporting for the backend.

Disabled unless ``SENTRY_DSN`` is set, so local development and the test suite
never emit anything and the code can ship before the secret exists.

**This platform handles student personal data.** Names, phone numbers, email
addresses, parent contact details and dates of birth flow through most
endpoints. Sentry is an external processor, so nothing of the sort may reach
it: ``send_default_pii`` is off and ``_scrub`` redacts known-sensitive keys
from every event before send. When adding a field that carries personal data,
add its key to ``SENSITIVE_KEYS``.
"""

from __future__ import annotations

import logging
from typing import Any

from app.core.config.settings import get_settings
from app.core.middleware.request_id import request_id_ctx

logger = logging.getLogger(__name__)

#: Substrings matched case-insensitively against dict keys. A key containing
#: any of these has its value replaced with ``REDACTED``. Deliberately broad —
#: over-redacting costs debuggability, under-redacting leaks a student's phone
#: number to a third party.
SENSITIVE_KEYS: tuple[str, ...] = (
    "password",
    "token",
    "secret",
    "authorization",
    "cookie",
    "api_key",
    "apikey",
    "dsn",
    # Personal data
    "email",
    "phone",
    "mobile",
    "contact",
    "address",
    "dob",
    "date_of_birth",
    "guardian",
    "parent",
    "first_name",
    "last_name",
    "full_name",
    "student_name",
    "teacher_name",
    "aadhaar",
    "roll_no",
)

REDACTED = "[redacted]"

#: Depth cap so a pathological payload can't spin the scrubber.
_MAX_DEPTH = 12


def _is_sensitive(key: str) -> bool:
    lowered = key.lower()
    return any(marker in lowered for marker in SENSITIVE_KEYS)


def _scrub(value: Any, depth: int = 0) -> Any:
    """Recursively redact sensitive values in dicts/lists.

    Returns a new structure; the caller's object is not mutated.
    """
    if depth > _MAX_DEPTH:
        return REDACTED
    if isinstance(value, dict):
        return {
            k: (REDACTED if _is_sensitive(str(k)) else _scrub(v, depth + 1))
            for k, v in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_scrub(v, depth + 1) for v in value]
    return value


def _before_send(event: dict[str, Any], hint: dict[str, Any]) -> dict[str, Any] | None:
    """Scrub an event, and tag it with the request id.

    The request id is the join key between a backend event and the frontend
    report for the same failure (both carry it), which is what makes a
    user-quoted reference resolve to the whole story rather than half of it.
    """
    try:
        for section in ("request", "extra", "contexts", "user"):
            if section in event:
                event[section] = _scrub(event[section])

        # Headers and cookies never carry anything we need and always carry
        # session material — drop them wholesale rather than key-matching.
        request = event.get("request")
        if isinstance(request, dict):
            request.pop("cookies", None)
            request.pop("headers", None)

        rid = request_id_ctx.get()
        if rid and rid != "-":
            event.setdefault("tags", {})["request_id"] = rid
    except Exception:  # pragma: no cover - reporting must never break the app
        logger.exception("sentry before_send failed; dropping event")
        return None
    return event


def init_sentry() -> bool:
    """Initialise Sentry. Returns True if enabled.

    Safe to call when the SDK isn't installed or no DSN is configured — both
    are ordinary states (local dev, CI), not errors.
    """
    settings = get_settings()
    dsn = getattr(settings, "SENTRY_DSN", "") or ""
    if not dsn:
        logger.info("SENTRY_DSN not set — error reporting disabled")
        return False

    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration
    except ImportError:
        logger.warning("sentry-sdk not installed — error reporting disabled")
        return False

    sentry_sdk.init(
        dsn=dsn,
        environment=settings.ENVIRONMENT,
        release=getattr(settings, "SENTRY_RELEASE", None) or None,
        # Never let the SDK attach request bodies, headers or user identifiers
        # on its own; _before_send is the only path that adds context.
        send_default_pii=False,
        traces_sample_rate=getattr(settings, "SENTRY_TRACES_SAMPLE_RATE", 0.0),
        before_send=_before_send,
        integrations=[
            StarletteIntegration(transaction_style="endpoint"),
            FastApiIntegration(transaction_style="endpoint"),
        ],
    )
    logger.info("Sentry initialised (environment=%s)", settings.ENVIRONMENT)
    return True
