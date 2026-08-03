"""WhatsApp Cloud API (Meta / Graph API) message client.

We talk to Meta's Cloud API directly — no BSP middleman — to send transactional
"utility" template messages (attendance alerts) to parents. This module is the
thin HTTP layer; deciding *what* to send and mapping a queued notification onto a
template is ``notification_service``'s job.

A business-initiated WhatsApp message MUST use a pre-approved template (Meta
rejects free-form text outside a 24h customer-service window), so the payload is
always ``type: template`` with a template name, language, and ordered body
parameters. See docs/whatsapp-attendance-notifications.md.

Endpoint (per Meta Cloud API "Send Messages"):
    POST https://graph.facebook.com/{version}/{phone_number_id}/messages
    Authorization: Bearer {access_token}
    {
      "messaging_product": "whatsapp",
      "to": "9198XXXXXXXX",
      "type": "template",
      "template": {
        "name": "attendance_absent_alert",
        "language": {"code": "en"},
        "components": [
          {"type": "body", "parameters": [
            {"type": "text", "text": "Rahul"},
            {"type": "text", "text": "03 Aug 2026"}
          ]}
        ]
      }
    }
Success (HTTP 200):
    {"messages": [{"id": "wamid.HBg..."}], ...}
Error (HTTP 4xx/5xx):
    {"error": {"message": "...", "code": 131030, "error_data": {...}}}
"""

from __future__ import annotations

import re

import httpx

GRAPH_BASE = "https://graph.facebook.com"


class WhatsAppError(RuntimeError):
    """Raised when the Cloud API returns an error envelope or a bad HTTP status.

    ``retryable`` is False for permanent failures (bad number, template not
    found, permission) so the queue can fail them fast instead of burning its
    retries; True for transient issues (5xx, rate limit, network)."""

    def __init__(self, message: str, *, retryable: bool = True):
        super().__init__(message)
        self.retryable = retryable


# Meta rejects a "+" and any spacing/dashes — the "to" field wants digits only,
# country code included (e.g. Indian 10-digit -> 91XXXXXXXXXX).
_NON_DIGITS = re.compile(r"\D")


def normalize_recipient(raw: str, default_country_code: str = "91") -> str | None:
    """Digits-only E.164-without-plus number Meta accepts, or None if unusable.

    A bare 10-digit Indian mobile gets the country code prefixed; a number that
    already carries a country code (>=11 digits) is used as-is."""
    if not raw:
        return None
    digits = _NON_DIGITS.sub("", raw)
    if len(digits) == 10:
        digits = default_country_code + digits
    # 11 digits with a leading 0 (0XXXXXXXXXX) -> drop the trunk 0, add cc.
    elif len(digits) == 11 and digits.startswith("0"):
        digits = default_country_code + digits[1:]
    if len(digits) < 11 or len(digits) > 15:
        return None
    return digits


def build_template_payload(
    *,
    to: str,
    template_name: str,
    language: str,
    body_params: list[str],
) -> dict:
    """The JSON body for one template send. ``body_params`` are positional and
    fill the template's {{1}}, {{2}}, … body placeholders in order."""
    components = []
    if body_params:
        components.append({
            "type": "body",
            "parameters": [{"type": "text", "text": str(p)} for p in body_params],
        })
    return {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": language},
            **({"components": components} if components else {}),
        },
    }


async def send_template_message(
    *,
    access_token: str,
    phone_number_id: str,
    api_version: str,
    to: str,
    template_name: str,
    language: str,
    body_params: list[str],
    timeout: float = 30.0,
    client: httpx.AsyncClient | None = None,
) -> str:
    """Send one approved template message. Returns Meta's message id (wamid).

    ``client`` is injectable so tests drive this without a live API. Raises
    ``WhatsAppError`` (with ``retryable``) on any non-2xx or error envelope."""
    url = f"{GRAPH_BASE}/{api_version}/{phone_number_id}/messages"
    payload = build_template_payload(
        to=to, template_name=template_name, language=language, body_params=body_params
    )
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    owns_client = client is None
    client = client or httpx.AsyncClient(timeout=timeout)
    try:
        resp = await client.post(url, json=payload, headers=headers)
    except httpx.HTTPError as exc:  # network/timeout — worth retrying
        raise WhatsAppError(f"WhatsApp request failed: {exc}", retryable=True) from exc
    finally:
        if owns_client:
            await client.aclose()

    if resp.status_code == 200:
        body = resp.json()
        messages = body.get("messages") if isinstance(body, dict) else None
        if messages and isinstance(messages, list):
            return messages[0].get("id", "")
        raise WhatsAppError(f"Unexpected WhatsApp success body: {body}", retryable=False)

    # Error path. 4xx (except 429) are permanent: bad number, unknown template,
    # auth/permission — retrying can't help, so fail fast.
    retryable = resp.status_code >= 500 or resp.status_code == 429
    detail = resp.text[:300]
    try:
        err = resp.json().get("error", {})
        detail = f"code={err.get('code')} {err.get('message')}"
    except (ValueError, AttributeError):
        pass
    raise WhatsAppError(
        f"WhatsApp API HTTP {resp.status_code}: {detail}", retryable=retryable
    )
