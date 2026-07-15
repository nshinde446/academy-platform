"""BioMax "AIData" push protocol receiver (BioMax R6 / AIFace family).

Unlike ZKTeco *iclock* devices, BioMax R6 face terminals do **not** speak the
ADMS/iclock protocol. They push each event as a JSON ``POST /AIData.aspx`` with
``dev_id`` / ``dev_model`` request headers. (SmartOffice / bmxcloud are the
vendor's own AIData receivers — that's why the client's box was IIS/.aspx.)

This is our receiver. It authenticates the device by ``dev_id`` (same allowlist
as iclock — the Cloud ID is identical), turns *punch* records into
vendor-agnostic ``PunchEvent`` and funnels them through the shared
``ingest_punches`` → ``rebuild_after_ingest`` pipeline, exactly like every other
feeder. ATTLOG/AIData times are the device's local wall-clock (branch tz); we
store tz-aware UTC.

Two message kinds arrive on the same URL:

* **PUNCH** — carries ``userId`` + ``time`` (plus ``inOut``, ``verifyMode``,
  ``logPhoto``). Ingested. ``userId`` matches ``Student.rfid_number``.
* **SYNC**  — face-template / photo enrollment mirror (``face`` / ``fps`` /
  ``photo``). Acknowledged and **ignored** — we never persist biometric
  templates (PII), and there's no student mapping on them.

Observed on-wire punch body (base64 blobs elided)::

    POST /AIData.aspx HTTP/1.0
    dev_id: AMDB26013800122
    dev_model: R6
    Content-Type: application/json

    {"userId":"1001","name":"RAM SIR","time":"20260617132228",
     "inOut":"IN","ioMode":10,"doorMode":"open","verifyMode":"Face",
     "workCode":1,"logPhoto":"<jpeg>"}

Provisioning (server → device: create/delete users so 1000s of students never
enrol by hand) is a future phase that rides on the HTTP *response* to these
POSTs. The response is deliberately isolated in ``_ack`` so those commands can
be added later without touching parsing/ingest.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.modules.attendance.integrations.biomax.iclock import (
    _require_known_device,
    _resolve_branch,
)
from app.modules.attendance.integrations.biomax.schemas import PunchEvent
from app.modules.attendance.integrations.biomax.service import ingest_punches
from app.modules.attendance.services import daily_service
from app.modules.attendance.time_utils import get_tz

logger = logging.getLogger(__name__)

# Mounted with NO /api/v1 prefix — device firmware posts to a fixed
# /AIData.aspx (SmartOffice/bmxcloud compatibility).
router = APIRouter(tags=["attendance"])

# BioMax AIData punch time: local wall-clock "YYYYMMDDHHMMSS" (no separators).
AIDATA_TIME_FMT = "%Y%m%d%H%M%S"


def _direction(raw: object) -> str | None:
    """Map the AIData ``inOut`` value to IN/OUT; None if absent/unknown.

    Classification (first_in/last_out) uses punch *ordering*, not this — the
    field is stored for reference only, so an all-"IN" device is still fine.
    """
    if raw is None:
        return None
    v = str(raw).strip().lower()
    if v in {"in", "i", "0", "checkin", "check-in"}:
        return "IN"
    if v in {"out", "o", "1", "checkout", "check-out"}:
        return "OUT"
    return None


def parse_aidata_record(body: dict, tz_name: str | None) -> list[PunchEvent]:
    """Turn one AIData JSON record into PunchEvents.

    A record is a **punch** iff it has both ``userId`` and ``time``; otherwise
    it's an enrollment/photo sync (or heartbeat) and yields no events, so the
    caller just acks it. ``userId`` matches ``Student.rfid_number``. A bad/
    unparseable ``time`` yields nothing rather than 500-ing the push (the device
    would only retry the same broken record forever)."""
    user_id = str(body.get("userId") or "").strip()
    ts_raw = str(body.get("time") or "").strip()
    if not user_id or not ts_raw:
        return []
    try:
        naive = datetime.strptime(ts_raw, AIDATA_TIME_FMT)
    except ValueError:
        logger.warning("AIData punch for %s has unparseable time %r", user_id, ts_raw)
        return []
    ts_utc = naive.replace(tzinfo=get_tz(tz_name)).astimezone(timezone.utc)
    return [PunchEvent(
        vendor_user_id=user_id,
        punch_timestamp=ts_utc,
        direction=_direction(body.get("inOut")),
        device_id="biomax-aidata",
    )]


def _ack() -> PlainTextResponse:
    """Acknowledgement the device reads as "delivered" so it advances its cursor
    and stops re-sending. Isolated here so the future provisioning phase can
    piggyback create/delete-user commands on this response."""
    return PlainTextResponse("OK")


@router.post("/AIData.aspx", response_class=PlainTextResponse)
async def aidata_push(
    request: Request,
    # The device sends a literal ``dev_id`` header (underscore). FastAPI's
    # Header() converts underscores→hyphens by default (would look for
    # ``dev-id`` and never match), so convert_underscores must be off.
    dev_id: str | None = Header(None, convert_underscores=False),
    session: AsyncSession = Depends(get_db),
):
    """Receive one AIData record. Punches are ingested; enrollment syncs are
    acked and ignored. Reply is always a plain ack (see ``_ack``)."""
    _require_known_device(dev_id)

    raw = await request.body()
    try:
        payload = json.loads(raw.decode("utf-8", errors="replace")) if raw else {}
    except json.JSONDecodeError:
        logger.warning("AIData from %s: body not JSON (%d bytes) — acking", dev_id, len(raw))
        return _ack()
    if not isinstance(payload, dict):
        return _ack()

    # Log the shape (keys only — never the base64 face/photo PII) for triage.
    logger.info(
        "AIData from %s: keys=%s userId=%r time=%r",
        dev_id, sorted(payload.keys()), payload.get("userId"), payload.get("time"),
    )

    branch_id = _resolve_branch()
    tz_name = await daily_service.branch_timezone(session, branch_id)
    events = parse_aidata_record(payload, tz_name)
    if not events:
        return _ack()  # enrollment sync / heartbeat — nothing to ingest

    result = await ingest_punches(session, events, branch_id)
    await daily_service.rebuild_after_ingest(
        session,
        branch_id=branch_id,
        affected=[(a.student_id, a.punch_timestamp) for a in result.affected],
        tz_name=tz_name,
    )
    logger.info(
        "AIData punch %s@%s -> inserted=%d skipped_no_student=%d",
        events[0].vendor_user_id, events[0].punch_timestamp,
        result.inserted, result.skipped_no_student,
    )
    return _ack()


@router.get("/AIData.aspx", response_class=PlainTextResponse)
async def aidata_heartbeat(
    dev_id: str | None = Header(None, convert_underscores=False),
):
    """Some firmwares GET the URL as a connectivity/heartbeat probe. Ack it."""
    _require_known_device(dev_id)
    return _ack()
