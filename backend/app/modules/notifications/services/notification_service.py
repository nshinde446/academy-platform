import json
import logging
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.services import audit_service
from app.modules.notifications.repositories import notification_repository
from app.modules.notifications.schemas.notification_schemas import VALID_CHANNELS, VALID_EVENT_TYPES

logger = logging.getLogger(__name__)

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
    for field in ["name", "event_type", "channel", "subject", "body_template", "is_active"]:
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

    for item in pending:
        success = await send_notification(item)
        if success:
            await notification_repository.mark_sent(session, item)
            sent_count += 1
        else:
            await notification_repository.mark_failed(
                session, item, "Delivery failed (placeholder sender)"
            )
            failed_count += 1

    return {"sent": sent_count, "failed": failed_count, "total": len(pending)}


async def send_notification(queue_item) -> bool:
    payload = None
    if queue_item.payload_json:
        try:
            payload = json.loads(queue_item.payload_json)
        except (json.JSONDecodeError, TypeError):
            payload = queue_item.payload_json

    body = ""
    if payload and isinstance(payload, dict):
        body = json.dumps(payload, default=str)[:200]

    logger.info(
        "NOTIFICATION [%s] to=%s channel=%s payload=%s",
        queue_item.delivery_status,
        queue_item.recipient,
        queue_item.channel,
        body,
    )
    return True


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
