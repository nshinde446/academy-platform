import json
import logging
import re
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config.settings import get_settings
from app.modules.audit.services import audit_service
from app.modules.events.repositories import event_repository
from app.modules.events.services import event_service
from app.modules.notifications.integrations.whatsapp import client as whatsapp_client
from app.modules.notifications.repositories import notification_repository
from app.modules.notifications.schemas.notification_schemas import (
    VALID_CHANNELS,
    VALID_DIGEST_SCOPES,
    VALID_EVENT_TYPES,
)

# Defaults returned when a branch has never saved settings (no row yet).
_DEFAULT_DIGEST_ENABLED = False
_DEFAULT_DIGEST_SCOPE = "ABSENT_ONLY"
_DEFAULT_WHATSAPP_ENABLED = False

# This consumer's name in processed_events — its own high-water mark, so it
# never re-enqueues an event another consumer (analytics, …) already handled.
CONSUMER_NAME = "notifications"

logger = logging.getLogger(__name__)

# Placeholder names in a body_template, in the order they appear. This ordering
# is what maps the template's {name} tokens onto a Meta template's positional
# {{1}}, {{2}}, … body parameters, so the admin keeps a single human-readable
# source of truth for both.
_PLACEHOLDER_RE = re.compile(r"\{(\w+)\}")

COMPARISON_OPS = {
    "lt": lambda a, b: a < b,
    "lte": lambda a, b: a <= b,
    "gt": lambda a, b: a > b,
    "gte": lambda a, b: a >= b,
    "eq": lambda a, b: a == b,
    "neq": lambda a, b: a != b,
}


async def create_template(
    session: AsyncSession,
    data: dict,
    current_user_id: uuid.UUID,
    ip_address: str | None = None,
):
    if data.get("channel") not in VALID_CHANNELS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid channel. Must be one of: {', '.join(sorted(VALID_CHANNELS))}",
        )
    if data.get("event_type") not in VALID_EVENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid event_type. Must be one of: {', '.join(sorted(VALID_EVENT_TYPES))}",
        )

    condition_json = None
    if data.get("condition_json"):
        condition_json = json.dumps(data["condition_json"])

    template = await notification_repository.create_template(
        session,
        name=data["name"],
        event_type=data["event_type"],
        channel=data["channel"],
        subject=data.get("subject"),
        body_template=data["body_template"],
        is_active=data.get("is_active", True),
        condition_json=condition_json,
        branch_id=data.get("branch_id"),
        provider_template_name=data.get("provider_template_name"),
        provider_language=data.get("provider_language"),
    )

    await audit_service.log_action(
        session,
        user_id=current_user_id,
        action="CREATE",
        table_name="notification_templates",
        record_id=template.id,
        new_values={"name": data["name"], "event_type": data["event_type"], "channel": data["channel"]},
        ip_address=ip_address,
        branch_id=data.get("branch_id"),
    )

    return _format_template(template)


async def list_templates(
    session: AsyncSession,
    branch_id: uuid.UUID | None = None,
    event_type: str | None = None,
    offset: int = 0,
    limit: int = 50,
):
    templates = await notification_repository.list_templates(
        session, branch_id=branch_id, event_type=event_type, offset=offset, limit=limit,
    )
    return [_format_template(t) for t in templates]


async def update_template(
    session: AsyncSession,
    template_id: uuid.UUID,
    data: dict,
    current_user_id: uuid.UUID,
    ip_address: str | None = None,
):
    template = await notification_repository.get_template(session, template_id)
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")

    old_values = {"name": template.name, "event_type": template.event_type}
    template_branch_id = template.branch_id
    template_record_id = template.id

    updates = {}
    for field in [
        "name", "event_type", "channel", "subject", "body_template", "is_active",
        "provider_template_name", "provider_language",
    ]:
        if data.get(field) is not None:
            updates[field] = data[field]

    if "channel" in updates and updates["channel"] not in VALID_CHANNELS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid channel. Must be one of: {', '.join(sorted(VALID_CHANNELS))}",
        )
    if "event_type" in updates and updates["event_type"] not in VALID_EVENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid event_type. Must be one of: {', '.join(sorted(VALID_EVENT_TYPES))}",
        )

    if data.get("condition_json") is not None:
        updates["condition_json"] = json.dumps(data["condition_json"])

    template = await notification_repository.update_template(session, template, **updates)

    await audit_service.log_action(
        session,
        user_id=current_user_id,
        action="UPDATE",
        table_name="notification_templates",
        record_id=template_record_id,
        old_values=old_values,
        new_values=updates,
        ip_address=ip_address,
        branch_id=template_branch_id,
    )

    return _format_template(template)


async def delete_template(
    session: AsyncSession,
    template_id: uuid.UUID,
    current_user_id: uuid.UUID,
    ip_address: str | None = None,
):
    template = await notification_repository.get_template(session, template_id)
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")

    await notification_repository.update_template(session, template, is_deleted=True)

    await audit_service.log_action(
        session,
        user_id=current_user_id,
        action="DELETE",
        table_name="notification_templates",
        record_id=template.id,
        old_values={"name": template.name},
        ip_address=ip_address,
        branch_id=template.branch_id,
    )


async def consume_events(session: AsyncSession, limit: int = 100) -> dict:
    """Turn emitted ``AcademicEvent`` rows into queued notifications.

    This is the bridge between the event bus and the notification engine: the
    absent sweep (and any other producer) only *emits* events; nothing enqueued
    a message until this consumer read them. Idempotent via ``processed_events``
    keyed on this consumer name, so an event is enqueued at most once even if the
    drain runs repeatedly.

    An event whose type has no active template simply enqueues nothing and is
    still marked processed, so it isn't re-examined forever.
    """
    events = await event_repository.get_unprocessed_events(
        session, CONSUMER_NAME, limit=limit
    )

    consumed = 0
    enqueued = 0
    for event in events:
        metadata = {}
        if event.metadata_json:
            try:
                loaded = json.loads(event.metadata_json)
                metadata = loaded if isinstance(loaded, dict) else {}
            except (json.JSONDecodeError, TypeError):
                metadata = {}

        # metadata carries the human fields (student_name, attendance_date,
        # recipient=parent_mobile); the columns carry the ids. Flatten both so a
        # template body and its condition can reference either.
        event_data = {
            "event_type": event.event_type,
            "event_id": str(event.event_id),
            "branch_id": str(event.branch_id) if event.branch_id else None,
            "student_id": str(event.student_id) if event.student_id else None,
            **metadata,
        }

        try:
            queued = await process_event(session, event_data)
            enqueued += len(queued)
            await event_service.process_event(
                session, event.event_id, CONSUMER_NAME, success=True
            )
        except Exception as exc:  # noqa: BLE001 — record & move on, don't wedge the drain
            logger.exception("Failed to consume event %s", event.event_id)
            await event_service.process_event(
                session, event.event_id, CONSUMER_NAME,
                success=False, error_message=str(exc)[:500],
            )
        consumed += 1

    return {"consumed": consumed, "enqueued": enqueued}


async def process_event(
    session: AsyncSession,
    event_data: dict,
):
    event_type = event_data.get("event_type")
    branch_id = event_data.get("branch_id")
    event_id = event_data.get("event_id")

    if not event_type:
        return []

    if isinstance(branch_id, str):
        branch_id = uuid.UUID(branch_id)
    if isinstance(event_id, str):
        event_id = uuid.UUID(event_id)

    templates = await notification_repository.get_active_templates(
        session, event_type, branch_id
    )

    queued = []
    for template in templates:
        if not evaluate_condition(template.condition_json, event_data):
            continue

        body = render_template(template.body_template, event_data)
        recipient = event_data.get("recipient", "placeholder@example.com")

        queue_item = await notification_repository.enqueue_notification(
            session,
            template_id=template.id,
            recipient=recipient,
            channel=template.channel,
            payload_json=json.dumps(event_data, default=str),
            delivery_status="PENDING",
            branch_id=branch_id,
        )

        now = datetime.now(timezone.utc)
        await notification_repository.create_notification_event(
            session,
            event_id=event_id or uuid.uuid4(),
            template_id=template.id,
            queue_id=queue_item.id,
            triggered_at=now,
        )

        queued.append(queue_item)

    return queued


def evaluate_condition(condition_json: str | None, event_data: dict) -> bool:
    if not condition_json:
        return True

    try:
        condition = json.loads(condition_json)
    except (json.JSONDecodeError, TypeError):
        return True

    if condition.get("type") == "comparison":
        field = condition.get("field")
        operator = condition.get("operator")
        value = condition.get("value")
        actual = event_data.get(field)
        if actual is None or operator not in COMPARISON_OPS:
            return False
        try:
            return COMPARISON_OPS[operator](float(actual), float(value))
        except (ValueError, TypeError):
            return False

    return True


def render_template(body_template: str, data: dict) -> str:
    result = body_template
    for key, value in data.items():
        result = result.replace(f"{{{key}}}", str(value))
    return result


async def process_queue(session: AsyncSession) -> dict:
    pending = await notification_repository.get_pending_notifications(session, limit=100)

    sent_count = 0
    failed_count = 0
    skipped_count = 0

    # Per-branch WhatsApp master toggle, cached so a full queue only hits the
    # settings table once per branch. None branch_id -> treated as off.
    wa_enabled: dict[uuid.UUID, bool] = {}

    for item in pending:
        template = await notification_repository.get_template(session, item.template_id)
        branch_enabled = False
        if item.branch_id is not None:
            if item.branch_id not in wa_enabled:
                s = await notification_repository.get_settings(session, item.branch_id)
                wa_enabled[item.branch_id] = bool(s and s.whatsapp_enabled)
            branch_enabled = wa_enabled[item.branch_id]
        outcome, error, retryable = await send_notification(
            item, template, branch_whatsapp_enabled=branch_enabled
        )
        if outcome == "SENT":
            await notification_repository.mark_sent(session, item)
            sent_count += 1
        elif outcome == "SKIP":
            skipped_count += 1  # left PENDING — e.g. channel disabled
        else:  # FAILED
            await notification_repository.mark_failed(
                session, item, error or "Delivery failed"
            )
            # A permanent failure (bad number, unknown template, auth) can never
            # succeed on retry — exhaust it now rather than burning three drains.
            if not retryable and item.delivery_status != "FAILED":
                item.delivery_status = "FAILED"
                await session.flush()
            failed_count += 1

    return {
        "sent": sent_count,
        "failed": failed_count,
        "skipped": skipped_count,
        "total": len(pending),
    }


def _ordered_body_params(body_template: str, payload: dict) -> list[str]:
    """The payload values for a template's {name} tokens, in appearance order —
    the positional parameters a Meta template's {{1}}, {{2}}, … expect."""
    return [str(payload.get(name, "")) for name in _PLACEHOLDER_RE.findall(body_template)]


async def send_notification(
    queue_item, template=None, *, branch_whatsapp_enabled: bool = False
) -> tuple[str, str | None, bool]:
    """Deliver one queued notification.

    Returns ``(outcome, error_message, retryable)`` where outcome is
    ``"SENT"`` | ``"FAILED"`` | ``"SKIP"``. SKIP leaves the row PENDING (e.g. the
    channel is disabled) so it flushes once enabled, without consuming retries.

    ``branch_whatsapp_enabled`` is the branch's UI master toggle; WhatsApp only
    sends when it AND the infra env flag are on.

    EMAIL/SMS/PUSH remain log-only stubs (real senders can slot in the same way
    WhatsApp does); only WHATSAPP is wired to a live provider.
    """
    payload = {}
    if queue_item.payload_json:
        try:
            loaded = json.loads(queue_item.payload_json)
            payload = loaded if isinstance(loaded, dict) else {}
        except (json.JSONDecodeError, TypeError):
            payload = {}

    if queue_item.channel == "WHATSAPP":
        return await _send_whatsapp(queue_item, template, payload, branch_whatsapp_enabled)

    # EMAIL / SMS / PUSH — not yet wired to a provider; log and treat as sent so
    # the queue drains in dev exactly as before.
    logger.info(
        "NOTIFICATION [%s] to=%s channel=%s payload=%s",
        queue_item.delivery_status,
        queue_item.recipient,
        queue_item.channel,
        json.dumps(payload, default=str)[:200],
    )
    return "SENT", None, False


async def _send_whatsapp(
    queue_item, template, payload: dict, branch_enabled: bool = False
) -> tuple[str, str | None, bool]:
    # Branch UI master toggle off -> skip (leave PENDING), no charge.
    if not branch_enabled:
        return "SKIP", None, False
    settings = get_settings()
    if not settings.WHATSAPP_ENABLED:
        return "SKIP", None, False  # infra flag off — leave PENDING, don't charge
    if not settings.WHATSAPP_ACCESS_TOKEN or not settings.WHATSAPP_PHONE_NUMBER_ID:
        return "FAILED", "WhatsApp enabled but access token / phone number id unset", False
    if template is None:
        return "FAILED", "Template not found for queue item", False
    if not template.provider_template_name or not template.provider_language:
        return (
            "FAILED",
            "WHATSAPP template missing provider_template_name / provider_language",
            False,
        )

    to = whatsapp_client.normalize_recipient(queue_item.recipient or "")
    if not to:
        return "FAILED", f"Unusable recipient number: {queue_item.recipient!r}", False

    body_params = _ordered_body_params(template.body_template, payload)
    try:
        message_id = await whatsapp_client.send_template_message(
            access_token=settings.WHATSAPP_ACCESS_TOKEN,
            phone_number_id=settings.WHATSAPP_PHONE_NUMBER_ID,
            api_version=settings.WHATSAPP_API_VERSION,
            to=to,
            template_name=template.provider_template_name,
            language=template.provider_language,
            body_params=body_params,
        )
    except whatsapp_client.WhatsAppError as exc:
        return "FAILED", str(exc), exc.retryable

    logger.info("WHATSAPP sent to=%s wamid=%s", to, message_id)
    return "SENT", None, False


async def list_queue(
    session: AsyncSession,
    delivery_status: str | None = None,
    branch_id: uuid.UUID | None = None,
    offset: int = 0,
    limit: int = 50,
):
    items = await notification_repository.list_queue(
        session, delivery_status=delivery_status, branch_id=branch_id,
        offset=offset, limit=limit,
    )
    return [_format_queue_item(i) for i in items]


def _delivery_log_row(q) -> dict:
    """Map a queued message to a delivery-log row (§5). Student fields come from
    the queued payload — there's no student FK on the queue."""
    payload = {}
    if q.payload_json:
        try:
            loaded = json.loads(q.payload_json)
            payload = loaded if isinstance(loaded, dict) else {}
        except (json.JSONDecodeError, TypeError):
            payload = {}
    return {
        "id": q.id,
        "student_name": payload.get("student_name"),
        "prn": payload.get("prn") or payload.get("enrollment_number"),
        "parent_contact": q.recipient,
        "date": payload.get("attendance_date") or payload.get("date"),
        "delivery_status": q.delivery_status,
        "sent_by": q.sent_by,
        "sent_at": q.sent_at,
        "error_message": q.error_message,
        "created_at": q.created_at,
    }


async def delivery_log(
    session: AsyncSession,
    *,
    branch_id: uuid.UUID | None = None,
    delivery_status: str | None = None,
    offset: int = 0,
    limit: int = 100,
) -> list[dict]:
    """WhatsApp absence-notification delivery log — who actually received a
    message, so the team can confirm coverage and re-send to anyone missed."""
    items = await notification_repository.list_queue(
        session,
        delivery_status=delivery_status,
        branch_id=branch_id,
        channel="whatsapp",
        offset=offset,
        limit=limit,
    )
    return [_delivery_log_row(i) for i in items]


async def get_notification_settings(
    session: AsyncSession, branch_id: uuid.UUID
) -> dict:
    """The branch's digest settings, or sensible defaults if never saved."""
    settings = await notification_repository.get_settings(session, branch_id)
    if settings is None:
        return {
            "branch_id": branch_id,
            "daily_digest_enabled": _DEFAULT_DIGEST_ENABLED,
            "daily_digest_scope": _DEFAULT_DIGEST_SCOPE,
            "whatsapp_enabled": _DEFAULT_WHATSAPP_ENABLED,
        }
    return {
        "branch_id": settings.branch_id,
        "daily_digest_enabled": settings.daily_digest_enabled,
        "daily_digest_scope": settings.daily_digest_scope,
        "whatsapp_enabled": settings.whatsapp_enabled,
    }


async def update_notification_settings(
    session: AsyncSession,
    branch_id: uuid.UUID,
    data: dict,
    current_user_id: uuid.UUID,
    ip_address: str | None = None,
) -> dict:
    if data.get("daily_digest_scope") is not None and (
        data["daily_digest_scope"] not in VALID_DIGEST_SCOPES
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid scope. Must be one of: {', '.join(sorted(VALID_DIGEST_SCOPES))}",
        )

    fields = {k: v for k, v in data.items() if v is not None}
    settings = await notification_repository.upsert_settings(
        session, branch_id, **fields
    )

    await audit_service.log_action(
        session,
        user_id=current_user_id,
        action="UPDATE",
        table_name="notification_settings",
        record_id=settings.id,
        new_values=fields,
        ip_address=ip_address,
        branch_id=branch_id,
    )

    return {
        "branch_id": settings.branch_id,
        "daily_digest_enabled": settings.daily_digest_enabled,
        "daily_digest_scope": settings.daily_digest_scope,
        "whatsapp_enabled": settings.whatsapp_enabled,
    }


def _format_template(t):
    condition = None
    if t.condition_json:
        try:
            condition = json.loads(t.condition_json)
        except (json.JSONDecodeError, TypeError):
            pass
    return {
        "id": t.id,
        "name": t.name,
        "event_type": t.event_type,
        "channel": t.channel,
        "subject": t.subject,
        "body_template": t.body_template,
        "is_active": t.is_active,
        "condition": condition,
        "branch_id": t.branch_id,
        "provider_template_name": t.provider_template_name,
        "provider_language": t.provider_language,
        "created_at": t.created_at,
        "updated_at": t.updated_at,
    }


def _format_queue_item(q):
    payload = None
    if q.payload_json:
        try:
            payload = json.loads(q.payload_json)
        except (json.JSONDecodeError, TypeError):
            pass
    return {
        "id": q.id,
        "template_id": q.template_id,
        "recipient": q.recipient,
        "channel": q.channel,
        "payload": payload,
        "delivery_status": q.delivery_status,
        "retry_count": q.retry_count,
        "max_retries": q.max_retries,
        "scheduled_at": q.scheduled_at,
        "sent_at": q.sent_at,
        "error_message": q.error_message,
        "branch_id": q.branch_id,
        "created_at": q.created_at,
    }
