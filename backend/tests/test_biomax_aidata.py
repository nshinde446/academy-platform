"""BioMax AIData (R6) push: JSON punch parsing, IST→UTC, dev_id gating,
enrollment-sync ignore, and the end-to-end ingest landing a DailyAttendance row.
"""

import uuid
from datetime import date, datetime, timezone

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.attendance.integrations.biomax import aidata
from app.modules.attendance.integrations.biomax.service import ingest_punches
from app.modules.attendance.models.attendance_models import DailyAttendance
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


def _enroll_client(monkeypatch, db_session, branch_id, *, enabled: bool):
    """A TestClient wired to hit ``aidata_push`` with the real db_session, the
    device allowlisted, and the provisioning flag set to ``enabled``."""
    import app.modules.attendance.integrations.biomax.iclock as iclock
    from app.core.database.session import get_db

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

    test_app = FastAPI()
    test_app.include_router(aidata.router)

    async def _db():
        yield db_session

    test_app.dependency_overrides[get_db] = _db
    return TestClient(test_app)


@pytest.mark.usefixtures("seed_data")
async def test_enroll_push_mirrors_when_enabled(monkeypatch, db_session, seed_data):
    branch_id = seed_data["branch_a"].id
    client = _enroll_client(monkeypatch, db_session, branch_id, enabled=True)
    resp = client.post(
        "/AIData.aspx",
        headers={"dev_id": DEV, "request_code": aidata.ENROLL_REQUEST_CODE},
        json={"userId": "3001", "name": "RAM SIR", "face": "AAQD...."},
    )
    assert resp.status_code == 200
    assert resp.headers["response_code"] == "OK"  # still acked
    users = await device_command_repo.list_device_users(db_session, branch_id, DEV)
    assert [u.vendor_user_id for u in users] == ["3001"]


@pytest.mark.usefixtures("seed_data")
async def test_enroll_push_ack_and_drops_when_disabled(monkeypatch, db_session, seed_data):
    branch_id = seed_data["branch_a"].id
    client = _enroll_client(monkeypatch, db_session, branch_id, enabled=False)
    resp = client.post(
        "/AIData.aspx",
        headers={"dev_id": DEV, "request_code": aidata.ENROLL_REQUEST_CODE},
        json={"userId": "3001", "name": "RAM SIR", "face": "AAQD...."},
    )
    assert resp.status_code == 200
    assert resp.headers["response_code"] == "OK"
    users = await device_command_repo.list_device_users(db_session, branch_id, DEV)
    assert users == []  # flag off -> byte-identical ack-and-drop, nothing mirrored


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
