"""BioMax / ZKTeco "iclock" (ADMS push) protocol endpoint.

BioMax devices are ZKTeco-based and speak the standard ADMS "push" protocol.
Point the device's *server/cloud* setting at this host and it will, on its own:

1.  Handshake:  GET  /iclock/cdata?SN=<serial>&options=all&...   → config text
2.  Upload:     POST /iclock/cdata?SN=<serial>&table=ATTLOG&...   → "OK: <n>"
                body = tab-separated punch rows, one per line
3.  Poll cmds:  GET  /iclock/getrequest?SN=<serial>              → "OK" (none)

This is plain text/HTTP, not JSON — so it can't reuse the JSON webhook. It
*does* reuse everything downstream: each ATTLOG row becomes a vendor-agnostic
``PunchEvent`` and flows through ``ingest_punches`` + ``rebuild_after_ingest``
exactly like the cloud feeders.

Trust model: the protocol carries no auth header, so we allowlist device
serials (``BIOMAX_DEVICE_SERIALS``) and attribute punches to
``BIOMAX_BRANCH_ID``. An unknown serial is rejected. ATTLOG times are the
device's local wall-clock (branch tz); we store tz-aware UTC.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config.settings import get_settings
from app.core.database.session import get_db
from app.modules.attendance.integrations.biomax.schemas import PunchEvent
from app.modules.attendance.integrations.biomax.service import ingest_punches
from app.modules.attendance.services import daily_service
from app.modules.attendance.time_utils import get_tz

# Mounted with NO /api/v1 prefix — device firmware posts to a fixed /iclock/*.
router = APIRouter(prefix="/iclock", tags=["attendance"])

ATTLOG_TIME_FMT = "%Y-%m-%d %H:%M:%S"


def _allowed_serials() -> set[str]:
    raw = get_settings().BIOMAX_DEVICE_SERIALS or ""
    return {s.strip() for s in raw.split(",") if s.strip()}


def _require_known_device(sn: str | None) -> str:
    """Validate the device serial against the allowlist (fail-safe: empty
    allowlist rejects everything)."""
    if not sn or sn not in _allowed_serials():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unknown or unconfigured device serial.",
        )
    return sn


def _resolve_branch() -> uuid.UUID:
    configured = get_settings().BIOMAX_BRANCH_ID
    if not configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="BIOMAX_BRANCH_ID is not configured.",
        )
    try:
        return uuid.UUID(configured)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="BIOMAX_BRANCH_ID is not a valid UUID.",
        ) from exc


def _attlog_direction(status_code: str) -> str | None:
    """ZK punch-state → IN/OUT. 0/4 = in, 1/5 = out; anything else unknown.

    Note: classification (first_in/last_out) uses punch *ordering*, not this —
    direction is stored for reference only, so an all-zero device is still fine.
    """
    s = status_code.strip()
    if s in {"0", "4"}:
        return "IN"
    if s in {"1", "5"}:
        return "OUT"
    return None


def parse_attlog(body: str, tz_name: str | None) -> list[PunchEvent]:
    """Parse an ATTLOG upload body into PunchEvents.

    Each line is tab-separated: ``PIN  YYYY-MM-DD HH:MM:SS  status  verify ...``.
    PIN matches ``Student.rfid_number``. Malformed lines are skipped so one bad
    row never drops a whole batch."""
    events: list[PunchEvent] = []
    for line in body.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        pin = parts[0].strip()
        ts_raw = parts[1].strip()
        if not pin or not ts_raw:
            continue
        try:
            naive = datetime.strptime(ts_raw, ATTLOG_TIME_FMT)
        except ValueError:
            continue
        ts_utc = naive.replace(tzinfo=get_tz(tz_name)).astimezone(timezone.utc)
        status_code = parts[2].strip() if len(parts) > 2 else ""
        events.append(PunchEvent(
            vendor_user_id=pin,
            punch_timestamp=ts_utc,
            direction=_attlog_direction(status_code),
            device_id="biomax-iclock",
        ))
    return events


def _handshake_response(sn: str) -> str:
    """Config block the device expects on first contact. Realtime=1 makes it
    push punches as they happen rather than only on a schedule."""
    return (
        f"GET OPTION FROM: {sn}\n"
        "Stamp=9999\n"
        "OpStamp=9999\n"
        "ErrorDelay=30\n"
        "Delay=10\n"
        "TransTimes=00:00;14:00\n"
        "TransInterval=1\n"
        "TransFlag=1111000000\n"
        "Realtime=1\n"
        "Encrypt=0\n"
    )


@router.get("/cdata", response_class=PlainTextResponse)
async def iclock_handshake(sn: str | None = Query(None, alias="SN")):
    """Device boot handshake — returns the push config block."""
    sn = _require_known_device(sn)
    return PlainTextResponse(_handshake_response(sn))


@router.post("/cdata", response_class=PlainTextResponse)
async def iclock_upload(
    request: Request,
    sn: str | None = Query(None, alias="SN"),
    table: str = Query("ATTLOG"),
    session: AsyncSession = Depends(get_db),
):
    """Receive a data upload. Only ATTLOG (punches) is ingested; OPERLOG and
    other tables are acknowledged and ignored. Reply is ``OK: <accepted>``."""
    _require_known_device(sn)
    raw = await request.body()
    body = raw.decode("utf-8", errors="replace")

    if table.upper() != "ATTLOG":
        # OPERLOG (user edits), templates, etc. — ack so the device clears them.
        return PlainTextResponse("OK")

    branch_id = _resolve_branch()
    tz_name = await daily_service.branch_timezone(session, branch_id)
    events = parse_attlog(body, tz_name)

    result = await ingest_punches(session, events, branch_id)
    await daily_service.rebuild_after_ingest(
        session,
        branch_id=branch_id,
        affected=[(a.student_id, a.punch_timestamp) for a in result.affected],
        tz_name=tz_name,
    )
    # ZK firmware treats "OK: N" as success and advances its cursor.
    return PlainTextResponse(f"OK: {result.inserted}")


@router.get("/getrequest", response_class=PlainTextResponse)
async def iclock_getrequest(sn: str | None = Query(None, alias="SN")):
    """Command poll. We push no remote commands, so always ``OK``."""
    _require_known_device(sn)
    return PlainTextResponse("OK")
