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

Observed on-wire punch (base64 blobs elided)::

    POST /AIData.aspx HTTP/1.0
    User-Agent: Mozilla/4.0
    Content-Type: application/json
    request_code: realtime_glog
    trans_id: RTLogSend
    dev_id: AMDB26013800122
    dev_model: R6

    {"userId":"1001","name":"RAM SIR","time":"20260617132228",
     "inOut":"IN","ioMode":10,"doorMode":"open","verifyMode":"Face",
     "workCode":1,"logPhoto":"<jpeg>"}

``request_code`` names the message: ``realtime_glog`` (punch) or
``realtime_enroll_data`` (enrollment mirror).

THE ACK IS IN THE RESPONSE HEADERS, NOT THE BODY — see ``_ack``. This was
reverse-engineered from BioMax's own SmartOffice receiver by replaying captured
records at it and reading what it returned; there is no public spec. Getting it
wrong does not fail loudly: the device simply re-uploads its whole database
every few seconds forever and never reports live scans.

Provisioning (server → device: create/delete users so 1000s of students never
enrol by hand) rides the ``cmd_code`` response header, which is why ``_ack``
owns the whole response.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config.settings import get_settings
from app.core.database.session import get_db
from app.modules.attendance.integrations.biomax.iclock import (
    _require_known_device,
    _resolve_branch,
)
from app.modules.attendance.integrations.biomax.schemas import PunchEvent
from app.modules.attendance.integrations.biomax.service import ingest_punches
from app.modules.attendance.repositories import device_command_repo
from app.modules.attendance.services import daily_service
from app.modules.attendance.time_utils import get_tz

# Use the app's configured "academy" logger (JSON handler, INFO). A bare
# getLogger(__name__) sits outside that tree and would be silent.
logger = logging.getLogger("academy")

# Mounted with NO /api/v1 prefix — device firmware posts to a fixed
# /AIData.aspx (SmartOffice/bmxcloud compatibility).
router = APIRouter(tags=["attendance"])

# BioMax AIData punch time: local wall-clock "YYYYMMDDHHMMSS" (no separators).
AIDATA_TIME_FMT = "%Y%m%d%H%M%S"

# The enrollment-mirror message kind (device pushes its own user table).
ENROLL_REQUEST_CODE = "realtime_enroll_data"

# Device-name field is short (SmartOffice EmployeeName is nvarchar(50)); the
# mirror stores at most this many chars so a diff never trips on truncation.
MIRROR_NAME_MAX = 50

# Keys whose *presence* means the sync carried a biometric template/photo. We
# record only that a template exists (``has_face``) — NEVER the blob itself.
BIOMETRIC_KEYS = ("face", "photo", "logPhoto", "fps", "template", "image")


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


def _clean_validity(raw: object) -> str | None:
    """Normalise a ``vaildStart``/``vaildEnd`` value to a bare digit string.

    The device sends ``YYYYMMDD``; anything blank or non-digit is dropped rather
    than mirrored, so a diff never compares against junk."""
    v = str(raw or "").strip()
    return v if v.isdigit() else None


def parse_enroll_record(body: dict) -> dict | None:
    """Extract the **non-biometric** identity fields from an enrollment sync.

    Returns the kwargs for ``upsert_device_user`` (identity only), or ``None`` if
    the record has no ``userId`` (a heartbeat / unusable sync — nothing to
    mirror). ``has_face`` records only *that* a template was present; the blob is
    never read out of ``body`` here, so it can't be persisted downstream.

    ``userId`` is the device userId (== ``Student.rfid_number``). Vendor typo
    keys ``vaildStart``/``vaildEnd`` are honoured, with the corrected spellings
    accepted as a fallback in case a firmware ever fixes them.
    """
    user_id = str(body.get("userId") or "").strip()
    if not user_id:
        return None
    name = str(body.get("name") or "").strip()[:MIRROR_NAME_MAX] or None
    try:
        privilege = int(body.get("privilege") or 0)
    except (TypeError, ValueError):
        privilege = 0
    has_face = any(str(body.get(k) or "").strip() for k in BIOMETRIC_KEYS)
    return {
        "vendor_user_id": user_id,
        "name": name,
        "privilege": privilege,
        "valid_start": _clean_validity(body.get("vaildStart") or body.get("validStart")),
        "valid_end": _clean_validity(body.get("vaildEnd") or body.get("validEnd")),
        "has_face": has_face,
    }


async def _mirror_enroll_record(
    session: AsyncSession, branch_id, dev_id: str, body: dict
) -> bool:
    """Upsert the device-user mirror row for one enrollment sync (identity only).

    No-op returning ``False`` when the record isn't a mirrorable enrollment.
    Gated by the caller behind ``BIOMAX_PROVISIONING_ENABLED`` so that, with the
    flag off, an enrollment sync is ack-and-dropped exactly as before."""
    fields = parse_enroll_record(body)
    if fields is None:
        return False
    await device_command_repo.upsert_device_user(
        session, branch_id=branch_id, dev_id=dev_id, **fields
    )
    logger.info(
        "AIData enroll mirror %s@%s: name=%r has_face=%s",
        fields["vendor_user_id"], dev_id, fields["name"], fields["has_face"],
    )
    return True


def _ack() -> Response:
    """Acknowledgement that makes the device mark a record delivered, delete it
    and advance. It lives ENTIRELY IN HEADERS — the R6 never reads the body.

    * ``response_code: OK`` — the ack itself.
    * ``cmd_code`` / ``trans_id`` — **must be empty**. A non-empty value means
      "the server has a command for you", so the device re-syncs its whole
      database instead of clearing its log. Echoing the request's ``trans_id``
      back is exactly what pinned a device in an endless re-upload loop.

    Anything else — a different ``response_code``, or a non-2xx — makes the
    device KEEP the record and retry. That is our fail-safe: never ack a punch
    we did not actually store (see ``aidata_push``), or it is lost forever.

    ``cmd_code`` is the future server→device provisioning channel.
    """
    return Response(
        content=b"",
        media_type="application/octet-stream",
        headers={"response_code": "OK", "cmd_code": "", "trans_id": ""},
    )


@router.post("/AIData.aspx")
async def aidata_push(
    request: Request,
    # The device sends literal ``dev_id`` / ``request_code`` headers
    # (underscores). FastAPI's Header() converts underscores→hyphens by default
    # (would look for ``dev-id`` and never match), so convert_underscores is off.
    dev_id: str | None = Header(None, convert_underscores=False),
    request_code: str | None = Header(None, convert_underscores=False),
    session: AsyncSession = Depends(get_db),
):
    """Receive one AIData record. Punches are ingested; enrollment syncs are
    acked and ignored.

    We only ack once the punch is durably stored — if ingest raises we return
    500 so the device RETAINS the record and retries. Acking first would make
    the device delete its only copy (e.g. mid-deploy), losing it for good.
    """
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
        "AIData %s from %s: keys=%s userId=%r time=%r",
        request_code or "?", dev_id, sorted(payload.keys()),
        payload.get("userId"), payload.get("time"),
    )

    branch_id = _resolve_branch()
    tz_name = await daily_service.branch_timezone(session, branch_id)
    events = parse_aidata_record(payload, tz_name)
    if not events:
        # Enrollment sync / heartbeat, or an unusable record (blank userId, bad
        # time). When provisioning is enabled, an enrollment sync updates the
        # device-user mirror (identity only) so reconcile has device-side truth;
        # otherwise we ack-and-drop exactly as before. Ack regardless: there is
        # no punch to store, and refusing would make the device retry the record
        # forever and head-of-line block real punches. A mirror failure must not
        # cost the ack, so it's caught and logged, never raised.
        if get_settings().BIOMAX_PROVISIONING_ENABLED:
            try:
                await _mirror_enroll_record(session, branch_id, dev_id, payload)
            except Exception:
                # Clear the failed transaction so the ack path's auto-commit
                # (get_db) doesn't inherit a poisoned session and 500 the device.
                await session.rollback()
                logger.exception(
                    "AIData enroll mirror failed for %s — acking anyway",
                    payload.get("userId"),
                )
        return _ack()

    try:
        result = await ingest_punches(session, events, branch_id)
        await daily_service.rebuild_after_ingest(
            session,
            branch_id=branch_id,
            affected=[(a.student_id, a.punch_timestamp) for a in result.affected],
            tz_name=tz_name,
        )
    except Exception:
        # Do NOT ack — the device keeps the punch and re-sends it later.
        logger.exception(
            "AIData ingest failed for %s@%s — not acking so the device retries",
            events[0].vendor_user_id, events[0].punch_timestamp,
        )
        return Response(status_code=500)

    logger.info(
        "AIData punch %s@%s -> inserted=%d skipped_no_student=%d",
        events[0].vendor_user_id, events[0].punch_timestamp,
        result.inserted, result.skipped_no_student,
    )
    return _ack()


@router.get("/AIData.aspx")
async def aidata_heartbeat(
    dev_id: str | None = Header(None, convert_underscores=False),
):
    """Some firmwares GET the URL as a connectivity/heartbeat probe. Ack it."""
    _require_known_device(dev_id)
    return _ack()
