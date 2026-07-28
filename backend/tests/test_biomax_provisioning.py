"""BioMax device provisioning (Increment 1 — backend plumbing, emission-free).

Covers the captured SET_USER_INFO payload contract, the enqueue queue (idempotent,
branch-isolated, no-PII), the dry-run/reconcile diffs, and the fail-safe flag gate.
The actual server→device emission is a separate capture-gated increment and is not
exercised here.
"""

import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.modules.attendance.integrations.biomax import provisioning_routes
from app.modules.attendance.models.provisioning_models import (
    CMD_SET_USER_INFO,
    STATUS_PENDING,
    DeviceCommand,
)
from app.modules.attendance.repositories import device_command_repo
from app.modules.attendance.services import provisioning_service
from app.modules.attendance.services.provisioning_service import (
    PayloadError,
    build_user_payload,
)
from app.modules.student.models.student_models import Student

DEV = "AMDB26013800122"


async def _student(db_session, seed_data, *, rfid, branch=None, first="Ravi", last="Kumar"):
    s = Student(
        id=uuid.uuid4(),
        branch_id=(branch or seed_data["branch_a"]).id,
        academic_year_id=seed_data["academic_year"].id,
        first_name=first,
        last_name=last,
        enrollment_number=f"EN-{rfid or uuid.uuid4().hex[:6]}",
        rfid_number=rfid,
        status="active",
        is_deleted=False,
    )
    db_session.add(s)
    await db_session.commit()
    return s


# ── payload contract (§0.6) ───────────────────────────────────────────────────


def test_build_payload_numeric_ok():
    payload = build_user_payload("1000120001", "Ravi Kumar")
    assert list(payload.keys()) == ["users"]
    user = payload["users"][0]
    assert user["userId"] == "1000120001"
    assert user["name"] == "Ravi Kumar"
    assert user["privilege"] == 0
    # Face/thumb only — no RFID card, no PIN.
    assert user["card"] == ""
    assert user["pwd"] == ""
    # Vendor's typo'd validity keys, wide window.
    assert user["vaildStart"] == "20200101"
    assert user["vaildEnd"] == "20401231"


def test_build_payload_rejects_missing_rfid():
    for bad in (None, "", "   "):
        with pytest.raises(PayloadError):
            build_user_payload(bad, "Ravi")


def test_build_payload_rejects_non_numeric():
    # An alphanumeric userId was observed NOT to sync to the device (§0.6).
    with pytest.raises(PayloadError):
        build_user_payload("2026CET001", "Ravi")


def test_build_payload_truncates_long_name():
    long_name = "A" * 80
    user = build_user_payload("42", long_name)["users"][0]
    assert len(user["name"]) <= 50


def test_build_payload_carries_no_biometric_keys():
    user = build_user_payload("42", "Ravi")["users"][0]
    for key in ("face", "photo", "logPhoto", "fps", "template", "image"):
        assert key not in user
        assert key.lower() not in {k.lower() for k in user}


# ── enqueue ───────────────────────────────────────────────────────────────────


@pytest.mark.usefixtures("seed_data")
async def test_enqueue_creates_pending_commands(db_session, seed_data):
    s = await _student(db_session, seed_data, rfid="5001")
    result = await provisioning_service.enqueue_students(
        db_session, seed_data["branch_a"].id, DEV, [s.id]
    )
    await db_session.commit()

    assert result.enqueued == 1
    assert result.skipped == 0
    rows = (await db_session.execute(select(DeviceCommand))).scalars().all()
    assert len(rows) == 1
    cmd = rows[0]
    assert cmd.command == CMD_SET_USER_INFO
    assert cmd.command_status == STATUS_PENDING
    assert cmd.vendor_user_id == "5001"
    assert cmd.student_id == s.id
    assert cmd.branch_id == seed_data["branch_a"].id
    assert cmd.payload["users"][0]["userId"] == "5001"


@pytest.mark.usefixtures("seed_data")
async def test_enqueue_skips_missing_and_non_numeric_rfid(db_session, seed_data):
    good = await _student(db_session, seed_data, rfid="5002")
    no_rfid = await _student(db_session, seed_data, rfid=None)
    alpha = await _student(db_session, seed_data, rfid="ABC123")

    result = await provisioning_service.enqueue_students(
        db_session, seed_data["branch_a"].id, DEV, [good.id, no_rfid.id, alpha.id]
    )
    await db_session.commit()

    assert result.enqueued == 1
    assert result.skipped == 2
    rows = (await db_session.execute(select(DeviceCommand))).scalars().all()
    assert {r.vendor_user_id for r in rows} == {"5002"}


@pytest.mark.usefixtures("seed_data")
async def test_enqueue_is_idempotent(db_session, seed_data):
    s = await _student(db_session, seed_data, rfid="5003")
    first = await provisioning_service.enqueue_students(
        db_session, seed_data["branch_a"].id, DEV, [s.id]
    )
    await db_session.commit()
    second = await provisioning_service.enqueue_students(
        db_session, seed_data["branch_a"].id, DEV, [s.id]
    )
    await db_session.commit()

    assert first.enqueued == 1
    assert second.enqueued == 0
    assert second.skipped == 1
    rows = (await db_session.execute(select(DeviceCommand))).scalars().all()
    assert len(rows) == 1  # not double-enqueued


@pytest.mark.usefixtures("seed_data")
async def test_enqueue_is_branch_isolated(db_session, seed_data):
    in_a = await _student(db_session, seed_data, rfid="5004")
    in_b = await _student(db_session, seed_data, rfid="5005", branch=seed_data["branch_b"])

    result = await provisioning_service.enqueue_students(
        db_session, seed_data["branch_a"].id, DEV, [in_a.id, in_b.id]
    )
    await db_session.commit()

    # Branch B's student is invisible to a branch-A push.
    assert result.enqueued == 1
    rows = (await db_session.execute(select(DeviceCommand))).scalars().all()
    assert {r.vendor_user_id for r in rows} == {"5004"}
    assert all(r.branch_id == seed_data["branch_a"].id for r in rows)


# ── dry-run ───────────────────────────────────────────────────────────────────


@pytest.mark.usefixtures("seed_data")
async def test_dry_run_has_no_side_effects(db_session, seed_data):
    s = await _student(db_session, seed_data, rfid="5006")
    plan = await provisioning_service.render_dry_run(
        db_session, seed_data["branch_a"].id, DEV, [s.id]
    )
    assert plan.to_create == 1
    assert plan.commands[0].action == "create"
    # Nothing enqueued.
    rows = (await db_session.execute(select(DeviceCommand))).scalars().all()
    assert rows == []


# ── reconcile ─────────────────────────────────────────────────────────────────


@pytest.mark.usefixtures("seed_data")
async def test_reconcile_platform_only_when_mirror_empty(db_session, seed_data):
    await _student(db_session, seed_data, rfid="6001")
    rec = await provisioning_service.reconcile(db_session, seed_data["branch_a"].id, DEV)
    assert [r.vendor_user_id for r in rec.on_platform_not_on_device] == ["6001"]
    assert rec.on_device_not_on_platform == []
    assert rec.drift == []


@pytest.mark.usefixtures("seed_data")
async def test_reconcile_matches_and_detects_drift(db_session, seed_data):
    s = await _student(db_session, seed_data, rfid="6002", first="Ravi", last="Kumar")
    # Mirror says the device has this user with the SAME name -> matched (no diff).
    await device_command_repo.upsert_device_user(
        db_session,
        branch_id=seed_data["branch_a"].id,
        dev_id=DEV,
        vendor_user_id="6002",
        name="Ravi Kumar",
    )
    await db_session.commit()
    rec = await provisioning_service.reconcile(db_session, seed_data["branch_a"].id, DEV)
    assert rec.on_platform_not_on_device == []
    assert rec.drift == []

    # Rename on the device mirror -> drift.
    await device_command_repo.upsert_device_user(
        db_session,
        branch_id=seed_data["branch_a"].id,
        dev_id=DEV,
        vendor_user_id="6002",
        name="Wrong Name",
    )
    await db_session.commit()
    rec2 = await provisioning_service.reconcile(db_session, seed_data["branch_a"].id, DEV)
    assert [r.vendor_user_id for r in rec2.drift] == ["6002"]


@pytest.mark.usefixtures("seed_data")
async def test_reconcile_reports_device_only(db_session, seed_data):
    # A user on the device with no matching platform student.
    await device_command_repo.upsert_device_user(
        db_session,
        branch_id=seed_data["branch_a"].id,
        dev_id=DEV,
        vendor_user_id="9999",
        name="Ghost",
    )
    await db_session.commit()
    rec = await provisioning_service.reconcile(db_session, seed_data["branch_a"].id, DEV)
    assert [r.vendor_user_id for r in rec.on_device_not_on_platform] == ["9999"]


# ── repo: cancel + list ───────────────────────────────────────────────────────


@pytest.mark.usefixtures("seed_data")
async def test_cancel_pending_and_list(db_session, seed_data):
    s = await _student(db_session, seed_data, rfid="7001")
    await provisioning_service.enqueue_students(
        db_session, seed_data["branch_a"].id, DEV, [s.id]
    )
    await db_session.commit()

    listed = await device_command_repo.list_commands(
        db_session, seed_data["branch_a"].id, DEV, STATUS_PENDING
    )
    assert len(listed) == 1
    cancelled = await device_command_repo.cancel_pending(db_session, listed[0])
    await db_session.commit()
    assert cancelled.command_status == "cancelled"

    # A re-push after cancel is allowed again (idempotency only blocks in-flight).
    again = await provisioning_service.enqueue_students(
        db_session, seed_data["branch_a"].id, DEV, [s.id]
    )
    await db_session.commit()
    assert again.enqueued == 1


# ── fail-safe flag gate ───────────────────────────────────────────────────────


def test_require_enabled_blocks_when_off(monkeypatch):
    monkeypatch.setattr(
        provisioning_routes, "get_settings",
        lambda: type("S", (), {"BIOMAX_PROVISIONING_ENABLED": False})(),
    )
    with pytest.raises(HTTPException) as exc:
        provisioning_routes._require_enabled()
    assert exc.value.status_code == 503


def test_require_enabled_passes_when_on(monkeypatch):
    monkeypatch.setattr(
        provisioning_routes, "get_settings",
        lambda: type("S", (), {"BIOMAX_PROVISIONING_ENABLED": True})(),
    )
    assert provisioning_routes._require_enabled() is None


@pytest.mark.usefixtures("seed_data")
async def test_provisioning_api_disabled_by_default_returns_503(client):
    # Default settings have the feature off -> the route is dormant (503),
    # before any auth or device check. Proves shipping the plumbing is inert.
    resp = await client.get(f"/api/v1/attendance/provisioning/reconcile?dev_id={DEV}")
    assert resp.status_code == 503
