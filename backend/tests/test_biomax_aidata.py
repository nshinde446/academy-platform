"""BioMax AIData (R6) push: JSON punch parsing, IST→UTC, dev_id gating,
enrollment-sync ignore, and the end-to-end ingest landing a DailyAttendance row.
"""

import json
import uuid
from datetime import date, datetime, timezone

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from starlette.requests import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.attendance.integrations.biomax import aidata
from app.modules.attendance.integrations.biomax.service import ingest_punches
from app.modules.attendance.models.attendance_models import DailyAttendance
from app.modules.attendance.models.provisioning_models import (
    CMD_SET_USER_INFO,
    STATUS_CONFIRMED,
    STATUS_FAILED,
    STATUS_PENDING,
    STATUS_SENT,
)
from app.modules.attendance.repositories import device_command_repo
from app.modules.attendance.services import daily_service
from app.modules.student.models.student_models import Student

DEV = "AMDB26013800122"


async def _student(db_session: AsyncSession, seed_data, rfid: str) -> Student:
    s = Student(
        id=uuid.uuid4(),
        branch_id=seed_data["branch_a"].id,
        academic_year_id=seed_data["academic_year"].id,
        first_name="Ai", last_name=f"User-{rfid}",
        enrollment_number=f"AID-{rfid}", rfid_number=rfid,
        status="active", is_deleted=False,
    )
    db_session.add(s)
    await db_session.commit()
    return s


# ── pure parsing ─────────────────────────────────────────────────────────────


def test_parse_punch_ist_to_utc():
    body = {"userId": "3001", "name": "RAM SIR", "time": "20260528095500",
            "inOut": "IN", "verifyMode": "Face"}
    events = aidata.parse_aidata_record(body, "Asia/Kolkata")
    assert len(events) == 1
    assert events[0].vendor_user_id == "3001"
    assert events[0].direction == "IN"
    # 09:55 IST == 04:25 UTC
    assert events[0].punch_timestamp == datetime(2026, 5, 28, 4, 25, tzinfo=timezone.utc)
    assert events[0].device_id == "biomax-aidata"


def test_parse_out_direction():
    body = {"userId": "3001", "time": "20260528151000", "inOut": "OUT"}
    events = aidata.parse_aidata_record(body, "Asia/Kolkata")
    assert events[0].direction == "OUT"


def test_enrollment_sync_yields_no_punch():
    # Face-template mirror: no userId/time -> ignored (acked), not ingested.
    body = {"name": "RAM SIR", "face": "AAQD....", "fps": 3, "photo": "/9j/...."}
    assert aidata.parse_aidata_record(body, "Asia/Kolkata") == []


def test_empty_userid_yields_no_punch():
    # Real trap seen on-wire: a face enrolled without a numeric User ID.
    body = {"userId": "", "name": "RAM SIR", "time": "20260617132228", "inOut": "IN"}
    assert aidata.parse_aidata_record(body, "Asia/Kolkata") == []


def test_bad_time_yields_no_punch():
    body = {"userId": "3001", "time": "not-a-time", "inOut": "IN"}
    assert aidata.parse_aidata_record(body, "Asia/Kolkata") == []


def test_direction_mapping():
    assert aidata._direction("IN") == "IN"
    assert aidata._direction("out") == "OUT"
    assert aidata._direction("0") == "IN"
    assert aidata._direction("1") == "OUT"
    assert aidata._direction(None) is None
    assert aidata._direction("weird") is None


# ── enrollment-mirror parsing (identity only, never biometrics) ──────────────


def test_parse_enroll_extracts_identity():
    body = {
        "userId": "3001", "name": "RAM SIR", "privilege": 0,
        "vaildStart": "20200101", "vaildEnd": "20401231",
        "face": "AAQD....", "photo": "/9j/....",
    }
    fields = aidata.parse_enroll_record(body)
    assert fields["vendor_user_id"] == "3001"
    assert fields["name"] == "RAM SIR"
    assert fields["privilege"] == 0
    assert fields["valid_start"] == "20200101"
    assert fields["valid_end"] == "20401231"
    # A template was present -> flag only.
    assert fields["has_face"] is True
    # The blob itself is never carried out of the record.
    assert not any(
        k in fields for k in ("face", "photo", "logPhoto", "fps", "template", "image")
    )


def test_parse_enroll_has_face_false_without_template():
    fields = aidata.parse_enroll_record({"userId": "3001", "name": "NO FACE"})
    assert fields["has_face"] is False
    assert fields["valid_start"] is None and fields["valid_end"] is None


def test_parse_enroll_none_without_userid():
    # Heartbeat / unusable sync -> nothing to mirror.
    assert aidata.parse_enroll_record({"name": "RAM SIR", "face": "AAQD"}) is None
    assert aidata.parse_enroll_record({"userId": "  "}) is None


def test_parse_enroll_truncates_name_and_coerces_privilege():
    fields = aidata.parse_enroll_record(
        {"userId": "3001", "name": "X" * 200, "privilege": "not-int"}
    )
    assert len(fields["name"]) == aidata.MIRROR_NAME_MAX
    assert fields["privilege"] == 0


def test_parse_enroll_junk_validity_dropped():
    fields = aidata.parse_enroll_record(
        {"userId": "3001", "vaildStart": "", "vaildEnd": "N/A"}
    )
    assert fields["valid_start"] is None
    assert fields["valid_end"] is None


# ── mirror persistence (device_users) ────────────────────────────────────────


@pytest.mark.usefixtures("seed_data")
async def test_mirror_enroll_record_lands_device_user(db_session, seed_data):
    branch_id = seed_data["branch_a"].id
    ok = await aidata._mirror_enroll_record(
        db_session, branch_id, DEV,
        {"userId": "3001", "name": "RAM SIR", "vaildStart": "20200101",
         "vaildEnd": "20401231", "face": "AAQD...."},
    )
    assert ok is True
    await db_session.commit()

    users = await device_command_repo.list_device_users(db_session, branch_id, DEV)
    assert len(users) == 1
    assert users[0].vendor_user_id == "3001"
    assert users[0].name == "RAM SIR"
    assert users[0].has_face is True
    assert users[0].valid_start == "20200101"


@pytest.mark.usefixtures("seed_data")
async def test_mirror_enroll_record_upserts_on_resync(db_session, seed_data):
    branch_id = seed_data["branch_a"].id
    await aidata._mirror_enroll_record(
        db_session, branch_id, DEV, {"userId": "3001", "name": "OLD NAME"}
    )
    await db_session.commit()
    await aidata._mirror_enroll_record(
        db_session, branch_id, DEV,
        {"userId": "3001", "name": "NEW NAME", "face": "AAQD"},
    )
    await db_session.commit()

    users = await device_command_repo.list_device_users(db_session, branch_id, DEV)
    assert len(users) == 1  # upsert, not a second row
    assert users[0].name == "NEW NAME"
    assert users[0].has_face is True


@pytest.mark.usefixtures("seed_data")
async def test_mirror_enroll_record_noop_without_userid(db_session, seed_data):
    branch_id = seed_data["branch_a"].id
    ok = await aidata._mirror_enroll_record(
        db_session, branch_id, DEV, {"name": "RAM SIR", "face": "AAQD"}
    )
    assert ok is False
    users = await device_command_repo.list_device_users(db_session, branch_id, DEV)
    assert users == []


# ── dev_id allowlist gating (reused from iclock) ─────────────────────────────


def test_require_known_device_rejects_unknown(monkeypatch):
    import app.modules.attendance.integrations.biomax.iclock as iclock
    monkeypatch.setattr(
        iclock, "get_settings",
        lambda: type("S", (), {"BIOMAX_DEVICE_SERIALS": "AMDB26013800122"})(),
    )
    assert aidata._require_known_device("AMDB26013800122") == "AMDB26013800122"
    with pytest.raises(HTTPException) as exc:
        aidata._require_known_device("NOPE")
    assert exc.value.status_code == 401
    with pytest.raises(HTTPException):
        aidata._require_known_device(None)


def test_literal_devid_header_is_read(monkeypatch):
    """Device sends a literal ``dev_id`` header (underscore). FastAPI would
    convert underscores→hyphens by default and never match — guard the
    convert_underscores=False fix so the endpoint keeps reading it."""
    import app.modules.attendance.integrations.biomax.iclock as iclock
    monkeypatch.setattr(
        iclock, "get_settings",
        lambda: type("S", (), {"BIOMAX_DEVICE_SERIALS": "AMDB26013800122"})(),
    )
    test_app = FastAPI()
    test_app.include_router(aidata.router)
    client = TestClient(test_app)
    ok = client.get("/AIData.aspx", headers={"dev_id": "AMDB26013800122"})
    assert ok.status_code == 200
    bad = client.get("/AIData.aspx", headers={"dev_id": "NOPE"})
    assert bad.status_code == 401


# ── the ack contract (headers, not body) ─────────────────────────────────────


def test_ack_is_carried_in_response_headers_not_body():
    """The R6 reads the ack from HEADERS and ignores the body. Returning "OK"
    as the body (our original bug) leaves the device re-uploading forever."""
    resp = aidata._ack()
    assert resp.headers["response_code"] == "OK"
    assert resp.body == b""


def test_ack_leaves_cmd_code_and_trans_id_empty():
    """A non-empty cmd_code/trans_id means "server has a command for you" — the
    device then re-syncs its whole DB instead of clearing its log. Echoing back
    the request's trans_id is what pinned a real device in an endless loop."""
    resp = aidata._ack()
    assert resp.headers["cmd_code"] == ""
    assert resp.headers["trans_id"] == ""


def test_ingest_failure_is_not_acked(monkeypatch):
    """Never ack a punch we failed to store: the device deletes its only copy
    on ack, so acking through an outage (e.g. mid-deploy) loses it for good.
    On failure we 500 and the device retries."""
    import app.modules.attendance.integrations.biomax.iclock as iclock
    from app.core.database.session import get_db

    monkeypatch.setattr(
        iclock, "get_settings",
        lambda: type("S", (), {"BIOMAX_DEVICE_SERIALS": "AMDB26013800122"})(),
    )
    monkeypatch.setattr(aidata, "_resolve_branch", lambda: uuid.uuid4())

    async def _tz(*a, **k):
        return "Asia/Kolkata"

    async def _boom(*a, **k):
        raise RuntimeError("database is down")

    monkeypatch.setattr(daily_service, "branch_timezone", _tz)
    monkeypatch.setattr(aidata, "ingest_punches", _boom)

    test_app = FastAPI()
    test_app.include_router(aidata.router)

    async def _fake_db():
        yield None

    test_app.dependency_overrides[get_db] = _fake_db
    resp = TestClient(test_app).post(
        "/AIData.aspx",
        headers={"dev_id": "AMDB26013800122", "request_code": "realtime_glog"},
        json={"userId": "3001", "time": "20260528095500", "inOut": "IN"},
    )
    assert resp.status_code == 500
    assert "response_code" not in resp.headers


# ── enrollment mirror is gated by BIOMAX_PROVISIONING_ENABLED ────────────────
#
# These invoke ``aidata_push`` DIRECTLY (awaited on the test's own event loop)
# rather than through Starlette's sync TestClient. TestClient runs the async
# handler on its own thread/loop, so handing it the pytest-asyncio ``db_session``
# would use one asyncpg connection across two loops and DEADLOCK on Postgres
# (it merely works on SQLite). Awaiting the coroutine keeps the DB on one loop.


async def _invoke_aidata_push(
    monkeypatch, session, branch_id, *, enabled: bool, body: dict,
    request_code: str = None,
):
    """Call the real ``aidata_push`` with a fabricated Request, the device
    allowlisted, and the provisioning flag set — all on the current loop."""
    import json as _json

    import app.modules.attendance.integrations.biomax.iclock as iclock
    from starlette.requests import Request

    if request_code is None:
        request_code = aidata.ENROLL_REQUEST_CODE

    monkeypatch.setattr(
        iclock, "get_settings",
        lambda: type("S", (), {"BIOMAX_DEVICE_SERIALS": DEV})(),
    )
    monkeypatch.setattr(
        aidata, "get_settings",
        lambda: type("S", (), {"BIOMAX_PROVISIONING_ENABLED": enabled})(),
    )
    monkeypatch.setattr(aidata, "_resolve_branch", lambda: branch_id)

    async def _tz(*a, **k):
        return "Asia/Kolkata"

    monkeypatch.setattr(daily_service, "branch_timezone", _tz)

    payload = _json.dumps(body).encode()

    async def _receive():
        return {"type": "http.request", "body": payload, "more_body": False}

    request = Request(
        {"type": "http", "method": "POST", "path": "/AIData.aspx",
         "headers": [(b"request_code", request_code.encode()), (b"dev_id", DEV.encode())]},
        _receive,
    )
    return await aidata.aidata_push(
        request,
        dev_id=DEV,
        request_code=request_code,
        session=session,
    )


@pytest.mark.usefixtures("seed_data")
async def test_enroll_push_mirrors_when_enabled(monkeypatch, db_session, seed_data):
    branch_id = seed_data["branch_a"].id
    resp = await _invoke_aidata_push(
        monkeypatch, db_session, branch_id, enabled=True,
        body={"userId": "3001", "name": "RAM SIR", "face": "AAQD...."},
    )
    assert resp.status_code == 200
    assert resp.headers["response_code"] == "OK"  # still acked
    users = await device_command_repo.list_device_users(db_session, branch_id, DEV)
    assert [u.vendor_user_id for u in users] == ["3001"]


@pytest.mark.usefixtures("seed_data")
async def test_enroll_push_ack_and_drops_when_disabled(monkeypatch, db_session, seed_data):
    branch_id = seed_data["branch_a"].id
    resp = await _invoke_aidata_push(
        monkeypatch, db_session, branch_id, enabled=False,
        body={"userId": "3001", "name": "RAM SIR", "face": "AAQD...."},
    )
    assert resp.status_code == 200
    assert resp.headers["response_code"] == "OK"
    users = await device_command_repo.list_device_users(db_session, branch_id, DEV)
    assert users == []  # flag off -> byte-identical ack-and-drop, nothing mirrored


# ── real-time biometric backup (encrypted) from realtime_enroll_data ─────────


@pytest.mark.usefixtures("seed_data")
async def test_enroll_push_backs_up_biometrics_when_key_set(monkeypatch, db_session, seed_data):
    """With a key set, an enrolment push stores the templates ENCRYPTED (decryptable
    back to the exact device strings), maps to the student, and the identity mirror
    still updates. Templates are never stored in cleartext."""
    from cryptography.fernet import Fernet
    import app.modules.attendance.integrations.biomax.biometrics as bio
    from app.modules.attendance.models.provisioning_models import DeviceUserBiometric

    key = Fernet.generate_key().decode()
    monkeypatch.setattr(bio, "get_settings", lambda: type("S", (), {"BIOMAX_BIOMETRIC_KEY": key})())

    branch_id = seed_data["branch_a"].id
    await _student(db_session, seed_data, "3050")  # so student_id resolves

    resp = await _invoke_aidata_push(
        monkeypatch, db_session, branch_id, enabled=True,
        body={"userId": "3050", "name": "RAM SIR", "face": "RkFDRV9URU1QTEFURQ==", "photo": "UEhPVE8="},
    )
    assert resp.status_code == 200
    assert resp.headers["response_code"] == "OK"

    row = (await db_session.execute(
        select(DeviceUserBiometric).where(DeviceUserBiometric.vendor_user_id == "3050")
    )).scalar_one()
    assert row.face_enc is not None and row.photo_enc is not None
    assert row.student_id is not None
    # encrypted at rest — cleartext template is NOT the stored bytes
    assert b"RkFDRV9URU1QTEFURQ==" not in bytes(row.face_enc)
    # ...but decrypts back to the exact device string (round-trip fidelity)
    assert bio.decrypt_template(row.face_enc) == "RkFDRV9URU1QTEFURQ=="
    assert bio.decrypt_template(row.photo_enc) == "UEhPVE8="

    users = await device_command_repo.list_device_users(db_session, branch_id, DEV)
    assert any(u.vendor_user_id == "3050" for u in users)  # mirror still updated


@pytest.mark.usefixtures("seed_data")
async def test_enroll_push_no_biometric_backup_without_key(monkeypatch, db_session, seed_data):
    """No key => blobs are dropped exactly as before; only the identity mirror is kept."""
    import app.modules.attendance.integrations.biomax.biometrics as bio
    from app.modules.attendance.models.provisioning_models import DeviceUserBiometric

    monkeypatch.setattr(bio, "get_settings", lambda: type("S", (), {"BIOMAX_BIOMETRIC_KEY": ""})())
    branch_id = seed_data["branch_a"].id

    await _invoke_aidata_push(
        monkeypatch, db_session, branch_id, enabled=True,
        body={"userId": "3051", "name": "X", "face": "RkFDRQ=="},
    )
    rows = (await db_session.execute(select(DeviceUserBiometric))).scalars().all()
    assert rows == []
    users = await device_command_repo.list_device_users(db_session, branch_id, DEV)
    assert any(u.vendor_user_id == "3051" for u in users)  # mirror still updated


# ── cloud-async GET_USER_INFO result folds into the mirror ───────────────────


@pytest.mark.usefixtures("seed_data")
async def test_send_cmd_result_get_user_info_updates_mirror(monkeypatch, db_session, seed_data):
    """A GET_USER_INFO result (device's user table page) is folded into the mirror
    — identity + has_face only; the face/photo blobs in the body are dropped."""
    from app.modules.attendance.services import provisioning_service

    branch_id = seed_data["branch_a"].id
    row = provisioning_service.build_user_info_command_row(branch_id, DEV, ["6400"])
    (cmd,) = await device_command_repo.enqueue(db_session, [row])
    await device_command_repo.mark_sent(db_session, cmd, "555")
    await db_session.commit()

    resp = await _invoke_aidata_push(
        monkeypatch, db_session, branch_id, enabled=True,
        request_code=aidata.SEND_CMD_RESULT_REQUEST_CODE,
        body={
            "trans_id": "555", "cmd_return_code": "OK", "packageId": 0, "usersCount": 1,
            "users": [{
                "userId": "6400", "name": "Aarav", "privilege": 0,
                "face": "BIG_FACE_BLOB", "photo": "BIG_PHOTO_BLOB",
                "vaildStart": "20200101", "vaildEnd": "20401231",
            }],
        },
    )
    assert resp.status_code == 200
    assert resp.headers["response_code"] == "OK"

    users = await device_command_repo.list_device_users(db_session, branch_id, DEV)
    mirror = next(u for u in users if u.vendor_user_id == "6400")
    assert mirror.has_face is True
    assert mirror.name == "Aarav"
    # No blob field exists on the mirror — the model can't hold the template — but
    # assert the values never leaked in as the name/etc. either.
    assert "BLOB" not in (mirror.name or "")

    confirmed = await device_command_repo.get_command(db_session, cmd.id, branch_id)
    assert confirmed.command_status == "confirmed"


@pytest.mark.usefixtures("seed_data")
async def test_send_cmd_result_get_user_info_no_face_flag_false(monkeypatch, db_session, seed_data):
    """A user the device holds WITHOUT a template → mirror has_face False (still
    'awaiting face' in reconcile)."""
    from app.modules.attendance.services import provisioning_service

    branch_id = seed_data["branch_a"].id
    row = provisioning_service.build_user_info_command_row(branch_id, DEV, ["6401"])
    (cmd,) = await device_command_repo.enqueue(db_session, [row])
    await device_command_repo.mark_sent(db_session, cmd, "556")
    await db_session.commit()

    await _invoke_aidata_push(
        monkeypatch, db_session, branch_id, enabled=True,
        request_code=aidata.SEND_CMD_RESULT_REQUEST_CODE,
        body={"trans_id": "556", "cmd_return_code": "OK", "packageId": 0, "usersCount": 1,
              "users": [{"userId": "6401", "name": "Isha", "privilege": 0}]},
    )
    users = await device_command_repo.list_device_users(db_session, branch_id, DEV)
    mirror = next(u for u in users if u.vendor_user_id == "6401")
    assert mirror.has_face is False


# ── end-to-end ingest ───────────────────────────────────────────────────────


@pytest.mark.usefixtures("seed_data")
async def test_aidata_ingest_lands_daily_attendance(db_session, seed_data):
    await _student(db_session, seed_data, "3001")
    tz_name = await daily_service.branch_timezone(db_session, seed_data["branch_a"].id)
    events = []
    for rec in (
        {"userId": "3001", "time": "20260528095500", "inOut": "IN"},
        {"userId": "3001", "time": "20260528151000", "inOut": "OUT"},
    ):
        events += aidata.parse_aidata_record(rec, tz_name)
    result = await ingest_punches(db_session, events, seed_data["branch_a"].id)
    await daily_service.rebuild_after_ingest(
        db_session, branch_id=seed_data["branch_a"].id,
        affected=[(a.student_id, a.punch_timestamp) for a in result.affected],
        tz_name=tz_name,
    )
    await db_session.commit()

    assert result.inserted == 2
    day = (await db_session.execute(
        select(DailyAttendance).where(
            DailyAttendance.attendance_date == date(2026, 5, 28)
        )
    )).scalar_one()
    assert day.day_status == "PRESENT"
    assert day.signoff == "COMPLETE"


# ── Increment 4: server→device command channel (receive_cmd / send_cmd_result) ─


async def _enqueue_cmd(db_session, branch_id, *, user_id="3001", name="Ravi Kumar"):
    payload = {"users": [{
        "userId": user_id, "name": name, "privilege": 0, "card": "", "pwd": "",
        "vaildStart": "20200101", "vaildEnd": "20401231",
    }]}
    (cmd,) = await device_command_repo.enqueue(db_session, [{
        "branch_id": branch_id, "dev_id": DEV, "command": CMD_SET_USER_INFO,
        "vendor_user_id": user_id, "payload": payload, "student_id": None,
        "command_status": STATUS_PENDING,
        "idempotency_key": f"{DEV}:{CMD_SET_USER_INFO}:{user_id}",
    }])
    await db_session.commit()
    return cmd


def _req(request_code, extra_headers=None):
    """A minimal Starlette Request carrying device headers (for handler-direct
    calls that read request.headers)."""
    headers = [(b"request_code", request_code.encode()), (b"dev_id", DEV.encode())]
    for k, v in (extra_headers or {}).items():
        headers.append((k.encode(), v.encode()))
    return Request({"type": "http", "method": "POST", "path": "/AIData.aspx",
                    "headers": headers})


@pytest.mark.usefixtures("seed_data")
async def test_receive_cmd_empty_queue_returns_error_no_cmd(db_session, seed_data):
    # Must match SmartOffice EXACTLY: response_code ERROR_NO_CMD, empty
    # cmd_code/trans_id, empty body — the device keeps polling only on this.
    resp = await aidata._emit_next_command(db_session, DEV)
    assert resp.headers["response_code"] == "ERROR_NO_CMD"
    assert resp.headers["cmd_code"] == ""
    assert resp.headers["trans_id"] == ""
    assert resp.body == b""


@pytest.mark.usefixtures("seed_data")
async def test_receive_cmd_emits_command_and_marks_sent(db_session, seed_data):
    branch_id = seed_data["branch_a"].id
    cmd = await _enqueue_cmd(db_session, branch_id, user_id="3001", name="Ravi Kumar")

    resp = await aidata._emit_next_command(db_session, DEV)
    assert resp.headers["response_code"] == "OK"
    assert resp.headers["cmd_code"] == "SET_USER_INFO"
    # Numeric trans_id, matching SmartOffice (echo-safe).
    expected_trans = aidata._numeric_trans_id(cmd)
    assert resp.headers["trans_id"] == expected_trans
    assert resp.headers["trans_id"].isdigit()
    body = json.loads(resp.body)
    assert body["users"][0]["userId"] == "3001"
    assert body["users"][0]["name"] == "Ravi Kumar"
    # No biometric keys ever leave in a command body.
    assert not any(k in body["users"][0] for k in ("face", "photo", "fps", "template"))

    await db_session.refresh(cmd)
    assert cmd.command_status == STATUS_SENT
    assert cmd.trans_id == expected_trans
    assert cmd.attempts == 1


@pytest.mark.usefixtures("seed_data")
async def test_receive_cmd_serves_one_at_a_time_fifo(db_session, seed_data):
    branch_id = seed_data["branch_a"].id
    first = await _enqueue_cmd(db_session, branch_id, user_id="1001", name="A")
    await _enqueue_cmd(db_session, branch_id, user_id="1002", name="B")

    r1 = await aidata._emit_next_command(db_session, DEV)
    await db_session.commit()
    # Oldest first; the second fetch gets the other one, not the same.
    assert json.loads(r1.body)["users"][0]["userId"] == "1001"
    r2 = await aidata._emit_next_command(db_session, DEV)
    assert json.loads(r2.body)["users"][0]["userId"] == "1002"
    assert r1.headers["trans_id"] == aidata._numeric_trans_id(first)


@pytest.mark.usefixtures("seed_data")
async def test_send_cmd_result_success_confirms(db_session, seed_data):
    branch_id = seed_data["branch_a"].id
    cmd = await _enqueue_cmd(db_session, branch_id)
    await aidata._emit_next_command(db_session, DEV)  # marks sent, sets trans_id
    await db_session.commit()

    await aidata._handle_cmd_result(
        db_session, DEV,
        _req("send_cmd_result",
             {"trans_id": aidata._numeric_trans_id(cmd), "cmd_return_code": "Success"}),
        {},
    )
    await db_session.refresh(cmd)
    assert cmd.command_status == STATUS_CONFIRMED


@pytest.mark.usefixtures("seed_data")
async def test_send_cmd_result_empty_ack_confirms(db_session, seed_data):
    # This R6 acks a SUCCESSFUL command with an empty result: it echoes the
    # trans_id but sends no cmd_return_code. Absence of an explicit failure = OK.
    # (Observed live 2026-07-30: users registered on the device with ret=''.)
    branch_id = seed_data["branch_a"].id
    cmd = await _enqueue_cmd(db_session, branch_id)
    await aidata._emit_next_command(db_session, DEV)
    await db_session.commit()

    await aidata._handle_cmd_result(
        db_session, DEV,
        _req("send_cmd_result", {"trans_id": aidata._numeric_trans_id(cmd)}),
        {},
    )
    await db_session.refresh(cmd)
    assert cmd.command_status == STATUS_CONFIRMED


@pytest.mark.usefixtures("seed_data")
async def test_send_cmd_result_failure_marks_failed(db_session, seed_data):
    branch_id = seed_data["branch_a"].id
    cmd = await _enqueue_cmd(db_session, branch_id)
    await aidata._emit_next_command(db_session, DEV)
    await db_session.commit()

    await aidata._handle_cmd_result(
        db_session, DEV,
        _req("send_cmd_result",
             {"trans_id": aidata._numeric_trans_id(cmd), "cmd_return_code": "Failure"}),
        {},
    )
    await db_session.refresh(cmd)
    assert cmd.command_status == STATUS_FAILED
    assert cmd.last_error


@pytest.mark.usefixtures("seed_data")
async def test_send_cmd_result_unknown_trans_id_is_ignored(db_session, seed_data):
    # A stray result for a trans_id we never issued must not blow up.
    await aidata._handle_cmd_result(
        db_session, DEV,
        _req("send_cmd_result", {"trans_id": "deadbeef", "cmd_return_code": "Success"}),
        {},
    )  # no exception = pass


@pytest.mark.usefixtures("seed_data")
async def test_receive_cmd_via_push_emits_when_enabled(monkeypatch, db_session, seed_data):
    branch_id = seed_data["branch_a"].id
    await _enqueue_cmd(db_session, branch_id, user_id="3001")
    resp = await _invoke_aidata_push(
        monkeypatch, db_session, branch_id, enabled=True,
        body={}, request_code=aidata.RECEIVE_CMD_REQUEST_CODE,
    )
    assert resp.headers["cmd_code"] == "SET_USER_INFO"


@pytest.mark.usefixtures("seed_data")
async def test_receive_cmd_via_push_inert_when_disabled(monkeypatch, db_session, seed_data):
    branch_id = seed_data["branch_a"].id
    await _enqueue_cmd(db_session, branch_id, user_id="3001")
    resp = await _invoke_aidata_push(
        monkeypatch, db_session, branch_id, enabled=False,
        body={}, request_code=aidata.RECEIVE_CMD_REQUEST_CODE,
    )
    # Flag off -> receive_cmd is NOT handled specially; falls through to the
    # empty ack (cmd_code ""), never emitting the queued command.
    assert resp.headers["cmd_code"] == ""
    cmd = (await device_command_repo.list_commands(db_session, branch_id, DEV))[0]
    assert cmd.command_status == STATUS_PENDING  # still queued, not sent


@pytest.mark.usefixtures("seed_data")
async def test_receive_cmd_captures_device_status(monkeypatch, db_session, seed_data):
    # The status block a device carries on every receive_cmd poll (userCount /
    # faceCount / …) is stored so the UI can show a live count + heartbeat. It
    # must not interfere with the command channel — a queued command still emits.
    branch_id = seed_data["branch_a"].id
    await _enqueue_cmd(db_session, branch_id, user_id="3001")
    status = {
        "userCount": 1103, "faceCount": 554, "fpCount": 0, "cardCount": 0,
        "userMaxCount": 3000, "faceMaxCount": 1500, "firmwareVersion": "R6-1.2.3",
    }
    resp = await _invoke_aidata_push(
        monkeypatch, db_session, branch_id, enabled=True,
        body=status, request_code=aidata.RECEIVE_CMD_REQUEST_CODE,
    )
    # Command still served despite the status payload.
    assert resp.headers["cmd_code"] == "SET_USER_INFO"

    stored = await device_command_repo.get_device_status(db_session, DEV)
    assert stored is not None
    assert stored.branch_id == branch_id
    assert stored.snapshot["userCount"] == 1103
    assert stored.snapshot["faceCount"] == 554
    assert stored.last_seen_at is not None


@pytest.mark.usefixtures("seed_data")
async def test_receive_cmd_without_status_block_stores_nothing(
    monkeypatch, db_session, seed_data
):
    # A bare receive_cmd (no userCount) must not create a status row.
    branch_id = seed_data["branch_a"].id
    await _invoke_aidata_push(
        monkeypatch, db_session, branch_id, enabled=True,
        body={}, request_code=aidata.RECEIVE_CMD_REQUEST_CODE,
    )
    assert await device_command_repo.get_device_status(db_session, DEV) is None


@pytest.mark.usefixtures("seed_data")
async def test_device_heartbeat_gated_by_flag(monkeypatch):
    import app.modules.attendance.integrations.biomax.iclock as iclock
    monkeypatch.setattr(
        iclock, "get_settings",
        lambda: type("S", (), {"BIOMAX_DEVICE_SERIALS": DEV})(),
    )
    # OFF -> 404 (byte-identical to "no such route" before this increment)
    monkeypatch.setattr(
        aidata, "get_settings",
        lambda: type("S", (), {"BIOMAX_PROVISIONING_ENABLED": False})(),
    )
    off = await aidata.device_heartbeat(dev_id=DEV)
    assert off.status_code == 404
    # ON -> keep-connected ack
    monkeypatch.setattr(
        aidata, "get_settings",
        lambda: type("S", (), {"BIOMAX_PROVISIONING_ENABLED": True})(),
    )
    on = await aidata.device_heartbeat(dev_id=DEV)
    assert on.status_code == 200
    assert on.headers["response_code"] == "OK"
