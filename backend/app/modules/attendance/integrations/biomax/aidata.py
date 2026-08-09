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

Provisioning (server → device: create/update users so 1000s of students never
enrol by hand) does NOT ride the punch response. The device fetches queued
commands with a dedicated ``request_code: receive_cmd`` and reports each result
with ``send_cmd_result`` (both still on this URL); a separate
``/DeviceHeartbeat.aspx`` keeps it "connected". The command name is the
``cmd_code`` response header, ``trans_id`` correlates the result, and the JSON
payload rides the body. All of it is dormant unless ``BIOMAX_PROVISIONING_ENABLED``.
Protocol recovered from SmartOffice's own handler — see
docs/biomax-provisioning-implementation.md §0.7.
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
from app.modules.attendance.integrations.biomax import biometrics
from app.modules.attendance.models.provisioning_models import CMD_GET_USER_INFO
from app.modules.attendance.repositories import device_command_repo
from app.modules.attendance.services import daily_service, provisioning_service
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

# ── provisioning: the server → device command channel (see docs §0.7) ─────────
# Recovered from SmartOffice's own handler. Commands do NOT ride the punch
# response — the device FETCHES them with a dedicated ``receive_cmd`` request and
# reports each result with ``send_cmd_result``. All still on POST /AIData.aspx,
# switched on the ``request_code`` header.
RECEIVE_CMD_REQUEST_CODE = "receive_cmd"       # device asks for a queued command
SEND_CMD_RESULT_REQUEST_CODE = "send_cmd_result"  # device reports a result
RESULT_SUCCESS = "Success"                      # cmd_return_code on success

# The exact "nothing queued" response SmartOffice returns to a receive_cmd — a
# ``response_code: ERROR_NO_CMD`` (NOT ``OK``) with empty cmd_code/trans_id and
# empty body. Captured from SmartOffice's own log: the device polls happily every
# 20s as long as it gets this; anything else and it gives up the command channel.
RESPONSE_CODE_NO_CMD = "ERROR_NO_CMD"

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


def _numeric_trans_id(command) -> str:
    """A NUMERIC correlation token, matching SmartOffice (which uses the integer
    DeviceCommandId, e.g. ``1008``). The firmware appears to treat ``trans_id`` as
    a number, so a uuid-hex token risks being mangled on echo. Derived from the
    command's uuid (low 31 bits) so it's stable, positive, and echo-safe; we store
    and match on the exact string via ``find_by_trans_id``."""
    return str(command.id.int & 0x7FFFFFFF)


def _command_response(command) -> Response:
    """Serve one queued command to the device on its ``receive_cmd`` fetch.

    Matches SmartOffice's exact wire shape: ``response_code: OK``, the command in
    ``cmd_code``, a numeric ``trans_id`` (echoed back in ``send_cmd_result``), and
    the JSON payload — ``build_user_payload``'s ``{"users":[…]}`` — in the body.
    """
    body = json.dumps(command.payload or {}).encode("utf-8")
    return Response(
        content=body,
        media_type="application/octet-stream",
        headers={
            "response_code": "OK",
            "cmd_code": command.command,
            "trans_id": command.trans_id or "",
        },
    )


def _no_command_response() -> Response:
    """Tell the device the queue is empty — SmartOffice's exact ``ERROR_NO_CMD``
    (empty cmd_code/trans_id, empty body). The device keeps polling on this."""
    return Response(
        content=b"",
        media_type="application/octet-stream",
        headers={"response_code": RESPONSE_CODE_NO_CMD, "cmd_code": "", "trans_id": ""},
    )


async def _emit_next_command(session: AsyncSession, dev_id: str) -> Response:
    """Answer a ``receive_cmd`` fetch: dequeue the oldest pending command, mark it
    ``sent`` with a fresh ``trans_id``, and hand it to the device. One command per
    fetch — the device polls repeatedly, so the queue drains without batching."""
    command = await device_command_repo.next_pending(session, dev_id)
    if command is None:
        return _no_command_response()
    trans_id = _numeric_trans_id(command)
    await device_command_repo.mark_sent(session, command, trans_id)
    logger.info(
        "AIData receive_cmd %s -> emit %s trans_id=%s user=%s",
        dev_id, command.command, trans_id, command.vendor_user_id,
    )
    return _command_response(command)


async def _handle_cmd_result(
    session: AsyncSession, dev_id: str, request: Request, body: dict
) -> None:
    """Process a ``send_cmd_result``: match the echoed ``trans_id`` to the sent
    command and mark it confirmed/failed. Fields may arrive as request headers or
    in the JSON body (exact placement is a build-time detail — read both)."""
    trans_id = (request.headers.get("trans_id") or str(body.get("trans_id") or "")).strip()
    ret = (
        request.headers.get("cmd_return_code")
        or str(body.get("cmd_return_code") or body.get("result") or "")
    ).strip()
    if not trans_id:
        logger.warning("AIData send_cmd_result from %s: no trans_id — ignoring", dev_id)
        return
    command = await device_command_repo.find_by_trans_id(session, dev_id, trans_id)
    if command is None:
        logger.warning("AIData send_cmd_result %s: unknown trans_id=%r", dev_id, trans_id)
        return
    # This R6 acknowledges a SUCCESSFUL command with an EMPTY result (SET_USER_INFO)
    # or an explicit "OK" (GET_USER_INFO). Treat empty / Success / OK / 0 as
    # success; only a different non-empty code is a real device-side failure.
    ret_l = ret.lower()
    failed = ret != "" and ret_l not in (RESULT_SUCCESS.lower(), "ok", "0")
    if failed:
        await device_command_repo.mark_failed(session, command, ret)
        logger.info("AIData cmd FAILED %s trans_id=%s ret=%r", command.command, trans_id, ret)
        return

    # GET_USER_INFO: the result body carries the device's users (with a face flag).
    # Fold them into the mirror — identity + has_face only, blobs dropped.
    if command.command == CMD_GET_USER_INFO:
        users = body.get("users") if isinstance(body, dict) else None
        n = await provisioning_service.apply_user_info_page(
            session, command.branch_id, dev_id, users or []
        )
        # Keep batches small enough to fit one page; if the device still paged,
        # warn (the unfetched users refresh on the next scheduled pull).
        if isinstance(body, dict) and (body.get("packageId") or 0):
            logger.warning(
                "AIData GET_USER_INFO trans_id=%s paged (packageId=%s) — lower the batch size",
                trans_id, body.get("packageId"),
            )
        logger.info("AIData GET_USER_INFO result trans_id=%s -> mirror upserted=%d", trans_id, n)

    await device_command_repo.mark_confirmed(session, command)
    logger.info("AIData cmd CONFIRMED %s trans_id=%s (ret=%r)", command.command, trans_id, ret)


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
        logger.warning("AIData from %s: body not JSON (%d bytes)", dev_id, len(raw))
        payload = {}
    if not isinstance(payload, dict):
        payload = {}

    # Log the shape (keys only — never the base64 face/photo PII) for triage.
    logger.info(
        "AIData %s from %s: keys=%s userId=%r time=%r",
        request_code or "?", dev_id, sorted(payload.keys()),
        payload.get("userId"), payload.get("time"),
    )

    provisioning_on = get_settings().BIOMAX_PROVISIONING_ENABLED

    # Server → device command channel (docs §0.7). Gated by the flag so that,
    # off, these request kinds are never handled specially and the receiver
    # behaves byte-identically to today. Never touches the punch/ingest path.
    if provisioning_on:
        if request_code == RECEIVE_CMD_REQUEST_CODE:
            return await _emit_next_command(session, dev_id)
        if request_code == SEND_CMD_RESULT_REQUEST_CODE:
            try:
                await _handle_cmd_result(session, dev_id, request, payload)
            except Exception:
                # A confirmation hiccup must never NAK the device — clear the
                # failed transaction so the ack path commits cleanly, and ack.
                await session.rollback()
                logger.exception("AIData send_cmd_result handling failed for %s", dev_id)
            return _ack()

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
        if provisioning_on:
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
            # Real-time biometric backup (encrypted) — a distinct, key-gated step.
            # In a SAVEPOINT so a backup hiccup rolls back ONLY itself, never the
            # identity mirror above or the ack. Templates are never logged.
            if biometrics.biometric_backup_enabled():
                try:
                    async with session.begin_nested():
                        stored = await provisioning_service.capture_biometrics(
                            session, branch_id, dev_id, payload
                        )
                    if stored:
                        logger.info(
                            "AIData biometric backup stored for %s", payload.get("userId")
                        )
                except Exception:
                    logger.exception(
                        "AIData biometric backup failed for %s — acking anyway",
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


@router.api_route("/DeviceHeartbeat.aspx", methods=["GET", "POST"])
async def device_heartbeat(
    dev_id: str | None = Header(None, convert_underscores=False),
):
    """The device's keep-connected heartbeat (docs §0.7). Answering it keeps the
    terminal in its 'connected' state so it keeps issuing ``receive_cmd`` — the
    command channel. Gated by the flag: OFF, we 404 exactly as before (no such
    route existed), so the live device's behaviour is unchanged; ON, we ack.

    The exact expected heartbeat response is a build-time detail to confirm in the
    on-device test — a bare ``response_code: OK`` is the minimal keep-alive."""
    _require_known_device(dev_id)
    if not get_settings().BIOMAX_PROVISIONING_ENABLED:
        return Response(status_code=404)
    return _ack()
