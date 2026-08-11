"""BioMax device provisioning (Increment 1 — backend plumbing, emission-free).

Covers the captured SET_USER_INFO payload contract, the enqueue queue (idempotent,
branch-isolated, no-PII), the dry-run/reconcile diffs, and the fail-safe flag gate.
The actual server→device emission is a separate capture-gated increment and is not
exercised here.
"""

import uuid
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.modules.attendance.integrations.biomax import provisioning_routes
from app.modules.attendance.models.attendance_models import RawPunchLog
from app.modules.attendance.models.provisioning_models import (
    CMD_SET_USER_INFO,
    STATUS_PENDING,
    DeviceCommand,
)
from app.modules.attendance.repositories import device_command_repo
from app.modules.attendance.schemas.provisioning_schemas import DeviceUserSnapshotRow
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
async def test_reconcile_confirmed_push_is_awaiting_face_not_need_push(
    db_session, seed_data
):
    """A confirmed push that the device hasn't mirrored back (no face enrolled)
    is 'awaiting face enrolment', not 'needs pushing' — so the panel stops
    telling staff to re-push identities that are already on the device."""
    s = await _student(db_session, seed_data, rfid="6100")
    await provisioning_service.enqueue_students(
        db_session, seed_data["branch_a"].id, DEV, [s.id]
    )
    cmd = (await db_session.execute(
        select(DeviceCommand).where(DeviceCommand.vendor_user_id == "6100")
    )).scalar_one()
    await device_command_repo.mark_confirmed(db_session, cmd)
    await db_session.commit()

    rec = await provisioning_service.reconcile(db_session, seed_data["branch_a"].id, DEV)
    # Not in the mirror, but confirmed -> awaiting face, not need-push.
    assert [r.vendor_user_id for r in rec.on_platform_not_on_device] == []
    assert [r.vendor_user_id for r in rec.awaiting_face_enrollment] == ["6100"]

    # Once the device mirrors it back (face enrolled), it leaves both buckets.
    await device_command_repo.upsert_device_user(
        db_session, branch_id=seed_data["branch_a"].id, dev_id=DEV,
        vendor_user_id="6100", name="Ravi Kumar", has_face=True,
    )
    await db_session.commit()
    rec2 = await provisioning_service.reconcile(db_session, seed_data["branch_a"].id, DEV)
    assert rec2.on_platform_not_on_device == []
    assert rec2.awaiting_face_enrollment == []


@pytest.mark.usefixtures("seed_data")
async def test_reconcile_punched_student_is_enrolled_not_awaiting(
    db_session, seed_data
):
    """A student who has ever punched is definitively enrolled (a face template
    only exists after enrolment at the terminal). Even with a confirmed push and
    an empty mirror — the exact state that used to read as 'awaiting face' — the
    punch removes them from BOTH buckets, so the panel stops over-counting the
    people who are actively marking attendance."""
    s = await _student(db_session, seed_data, rfid="6200")
    await provisioning_service.enqueue_students(
        db_session, seed_data["branch_a"].id, DEV, [s.id]
    )
    cmd = (await db_session.execute(
        select(DeviceCommand).where(DeviceCommand.vendor_user_id == "6200")
    )).scalar_one()
    await device_command_repo.mark_confirmed(db_session, cmd)
    db_session.add(
        RawPunchLog(
            id=uuid.uuid4(),
            branch_id=seed_data["branch_a"].id,
            student_id=s.id,
            device_id=DEV,
            punch_timestamp=datetime.now(timezone.utc),
            is_deleted=False,
        )
    )
    await db_session.commit()

    rec = await provisioning_service.reconcile(db_session, seed_data["branch_a"].id, DEV)
    assert [r.vendor_user_id for r in rec.awaiting_face_enrollment] == []
    assert [r.vendor_user_id for r in rec.on_platform_not_on_device] == []


@pytest.mark.usefixtures("seed_data")
async def test_reconcile_matches_and_detects_drift(db_session, seed_data):
    s = await _student(db_session, seed_data, rfid="6002", first="Ravi", last="Kumar")
    # Mirror says the device has this user WITH A FACE and the SAME name -> matched.
    # (has_face is what makes them "enrolled" rather than "awaiting face".)
    await device_command_repo.upsert_device_user(
        db_session,
        branch_id=seed_data["branch_a"].id,
        dev_id=DEV,
        vendor_user_id="6002",
        name="Ravi Kumar",
        has_face=True,
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
        has_face=True,
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


# ── device-user snapshot sync (ground truth from the terminal) ────────────────


@pytest.mark.usefixtures("seed_data")
async def test_sync_snapshot_with_face_clears_awaiting_face(db_session, seed_data):
    """A confirmed-but-unmirrored student reads as 'awaiting face'. Once the
    on-site agent's snapshot reports the device holds their FACE, they're enrolled
    — out of awaiting-face entirely. This is the fix for stale 'awaiting face'."""
    s = await _student(db_session, seed_data, rfid="6300", first="Ravi", last="Kumar")
    await provisioning_service.enqueue_students(db_session, seed_data["branch_a"].id, DEV, [s.id])
    cmd = (await db_session.execute(
        select(DeviceCommand).where(DeviceCommand.vendor_user_id == "6300")
    )).scalar_one()
    await device_command_repo.mark_confirmed(db_session, cmd)
    await db_session.commit()

    rec = await provisioning_service.reconcile(db_session, seed_data["branch_a"].id, DEV)
    assert [r.vendor_user_id for r in rec.awaiting_face_enrollment] == ["6300"]

    upserted, removed = await provisioning_service.sync_device_users(
        db_session, seed_data["branch_a"].id, DEV,
        [DeviceUserSnapshotRow(vendor_user_id="6300", name="Ravi Kumar", has_face=True)],
    )
    await db_session.commit()
    assert (upserted, removed) == (1, 0)

    rec2 = await provisioning_service.reconcile(db_session, seed_data["branch_a"].id, DEV)
    assert rec2.awaiting_face_enrollment == []
    assert rec2.drift == []  # name matches
    assert rec2.on_platform_not_on_device == []


@pytest.mark.usefixtures("seed_data")
async def test_sync_snapshot_identity_only_stays_awaiting_face(db_session, seed_data):
    """A snapshot user WITHOUT a face is on the device (identity pushed) but still
    needs a face enrolled — so they stay in 'awaiting face', not matched."""
    s = await _student(db_session, seed_data, rfid="6301", first="Sia", last="Rao")
    await provisioning_service.sync_device_users(
        db_session, seed_data["branch_a"].id, DEV,
        [DeviceUserSnapshotRow(vendor_user_id="6301", name="Sia Rao", has_face=False)],
    )
    await db_session.commit()

    rec = await provisioning_service.reconcile(db_session, seed_data["branch_a"].id, DEV)
    assert [r.vendor_user_id for r in rec.awaiting_face_enrollment] == ["6301"]
    assert rec.drift == []


@pytest.mark.usefixtures("seed_data")
async def test_sync_snapshot_full_replace_removes_absent(db_session, seed_data):
    """Full-replace: a mirror user the device no longer holds is dropped."""
    await device_command_repo.upsert_device_user(
        db_session, branch_id=seed_data["branch_a"].id, dev_id=DEV,
        vendor_user_id="8000", name="Old User", has_face=True,
    )
    await db_session.commit()

    upserted, removed = await provisioning_service.sync_device_users(
        db_session, seed_data["branch_a"].id, DEV,
        [DeviceUserSnapshotRow(vendor_user_id="8001", name="New User", has_face=True)],
    )
    await db_session.commit()
    assert (upserted, removed) == (1, 1)

    mirror = await device_command_repo.list_device_users(db_session, seed_data["branch_a"].id, DEV)
    assert {u.vendor_user_id for u in mirror} == {"8001"}


@pytest.mark.usefixtures("seed_data")
async def test_enqueue_user_info_refresh_batches_and_reruns(db_session, seed_data):
    """Refresh queues batched GET_USER_INFO commands; a re-run clears the prior
    pending ones first so they don't pile up."""
    ids = [str(6500 + i) for i in range(12)]  # 12 ids, batch 5 -> 3 commands
    n = await provisioning_service.enqueue_user_info_refresh(
        db_session, seed_data["branch_a"].id, DEV, ids
    )
    await db_session.commit()
    assert n == 3
    pending = await device_command_repo.list_commands(
        db_session, seed_data["branch_a"].id, DEV, STATUS_PENDING
    )
    gui = [c for c in pending if c.command == "GET_USER_INFO"]
    assert len(gui) == 3
    assert gui[0].payload["usersId"] == ids[:5]

    # Re-run: prior pending cancelled, fresh set enqueued (still 3, not 6).
    n2 = await provisioning_service.enqueue_user_info_refresh(
        db_session, seed_data["branch_a"].id, DEV, ids
    )
    await db_session.commit()
    assert n2 == 3
    pending2 = await device_command_repo.list_commands(
        db_session, seed_data["branch_a"].id, DEV, STATUS_PENDING
    )
    assert len([c for c in pending2 if c.command == "GET_USER_INFO"]) == 3


@pytest.mark.usefixtures("seed_data")
async def test_apply_user_info_page_sets_has_face_drops_blob(db_session, seed_data):
    n = await provisioning_service.apply_user_info_page(
        db_session, seed_data["branch_a"].id, DEV,
        [
            {"userId": "6600", "name": "Face User", "face": "BLOB", "vaildEnd": "20401231"},
            {"userId": "6601", "name": "No Face"},
            {"name": "junk-no-id"},  # skipped
        ],
    )
    await db_session.commit()
    assert n == 2
    users = {u.vendor_user_id: u for u in await device_command_repo.list_device_users(
        db_session, seed_data["branch_a"].id, DEV)}
    assert users["6600"].has_face is True
    assert users["6600"].valid_end == "20401231"
    assert users["6601"].has_face is False


@pytest.mark.usefixtures("seed_data")
async def test_user_ids_for_refresh_all_scope(db_session, seed_data):
    await _student(db_session, seed_data, rfid="7100")
    await _student(db_session, seed_data, rfid="ABC")  # non-numeric -> excluded
    ids = await provisioning_service.user_ids_for_refresh(
        db_session, seed_data["branch_a"].id, DEV, "all"
    )
    assert "7100" in ids
    assert "ABC" not in ids


@pytest.mark.usefixtures("seed_data")
async def test_apply_user_info_page_backfills_biometrics(monkeypatch, db_session, seed_data):
    """A GET_USER_INFO page also backs up templates (encrypted) when a key is set —
    that's the one-time backfill for already-enrolled students via scope=all."""
    import app.modules.attendance.integrations.biomax.biometrics as bio
    from cryptography.fernet import Fernet

    key = Fernet.generate_key().decode()  # ONE key — a fresh one per call breaks decrypt
    monkeypatch.setattr(bio, "get_settings", lambda: type("S", (), {"BIOMAX_BIOMETRIC_KEY": key})())
    branch = seed_data["branch_a"].id
    n = await provisioning_service.apply_user_info_page(
        db_session, branch, DEV,
        [{"userId": "7200", "name": "Face U", "face": "RkFDRQ==", "photo": "UEg="},
         {"userId": "7201", "name": "No Face"}],
    )
    await db_session.commit()
    assert n == 2  # both mirrored
    row = await device_command_repo.get_biometric(db_session, DEV, "7200")
    assert row is not None and row.face_enc is not None
    assert bio.decrypt_template(row.face_enc) == "RkFDRQ=="
    assert await device_command_repo.get_biometric(db_session, DEV, "7201") is None  # no template


@pytest.mark.usefixtures("seed_data")
async def test_restore_emit_injects_templates_without_storing_cleartext(monkeypatch, db_session, seed_data):
    """Restore queues identity + a flag only (no plaintext at rest); the templates
    are decrypted and injected at emit time, leaving the stored command untouched."""
    import app.modules.attendance.integrations.biomax.biometrics as bio
    from cryptography.fernet import Fernet

    key = Fernet.generate_key().decode()  # ONE key — a fresh one per call breaks decrypt
    monkeypatch.setattr(bio, "get_settings", lambda: type("S", (), {"BIOMAX_BIOMETRIC_KEY": key})())
    branch = seed_data["branch_a"].id
    await device_command_repo.upsert_biometric(
        db_session, branch_id=branch, dev_id=DEV, vendor_user_id="7300",
        student_id=None, name="R",
        face_enc=bio.encrypt_template("RkFDRQ=="), photo_enc=None,
        fps_enc=bio.encrypt_template('["FP1"]'),
    )
    await db_session.commit()

    n = await provisioning_service.enqueue_restore(db_session, branch, DEV)
    await db_session.commit()
    assert n == 1
    cmd = next(c for c in await device_command_repo.list_commands(
        db_session, branch, DEV, STATUS_PENDING) if c.command == "SET_USER_INFO")

    # stored payload: identity + flag, NO plaintext template
    assert cmd.payload.get("restore_biometrics") is True
    assert "face" not in cmd.payload["users"][0]

    emit = await provisioning_service.build_restore_emit_payload(db_session, DEV, cmd)
    assert "restore_biometrics" not in emit          # flag stripped for the wire
    assert emit["users"][0]["face"] == "RkFDRQ=="    # template injected
    assert emit["users"][0]["fps"] == ["FP1"]        # fps decoded back to a list
    assert "face" not in cmd.payload["users"][0]     # stored command untouched


@pytest.mark.usefixtures("seed_data")
async def test_list_backed_up_users_needs_a_template(db_session, seed_data):
    branch = seed_data["branch_a"].id
    # face -> included; photo-only -> excluded
    await device_command_repo.upsert_biometric(
        db_session, branch_id=branch, dev_id=DEV, vendor_user_id="7400",
        student_id=None, name="Has Face", face_enc=b"x", photo_enc=None, fps_enc=None)
    await device_command_repo.upsert_biometric(
        db_session, branch_id=branch, dev_id=DEV, vendor_user_id="7401",
        student_id=None, name="Photo Only", face_enc=None, photo_enc=b"x", fps_enc=None)
    await db_session.commit()
    ids = {u for u, _ in await device_command_repo.list_backed_up_users(db_session, branch, DEV)}
    assert ids == {"7400"}


@pytest.mark.usefixtures("seed_data")
async def test_student_face_photo_decrypts_backup(monkeypatch, db_session, seed_data):
    """The student's face photo is decrypted from the backup (found via student_id
    or rfid) and returned as raw JPEG bytes; None when there's no photo."""
    import base64

    import app.modules.attendance.integrations.biomax.biometrics as bio
    from cryptography.fernet import Fernet

    key = Fernet.generate_key().decode()
    monkeypatch.setattr(bio, "get_settings", lambda: type("S", (), {"BIOMAX_BIOMETRIC_KEY": key})())
    branch = seed_data["branch_a"].id
    s = await _student(db_session, seed_data, rfid="8800")

    jpeg = b"\xff\xd8\xff\xe0JFIFdata"  # pretend JPEG bytes
    await device_command_repo.upsert_biometric(
        db_session, branch_id=branch, dev_id=DEV, vendor_user_id="8800",
        student_id=s.id, name="Face", face_enc=None,
        photo_enc=bio.encrypt_template(base64.b64encode(jpeg).decode()), fps_enc=None,
    )
    await db_session.commit()

    out = await provisioning_service.student_face_photo(db_session, branch, s.id)
    assert out == jpeg

    # a student with no backup -> None
    other = await _student(db_session, seed_data, rfid="8801")
    assert await provisioning_service.student_face_photo(db_session, branch, other.id) is None


def test_verify_sync_token_gate(monkeypatch):
    # Unset token -> feature disabled (503); wrong token -> 401; correct -> passes.
    monkeypatch.setattr(
        provisioning_routes, "get_settings",
        lambda: type("S", (), {"BIOMAX_SYNC_TOKEN": ""})(),
    )
    with pytest.raises(HTTPException) as off:
        provisioning_routes._verify_sync_token("anything")
    assert off.value.status_code == 503

    monkeypatch.setattr(
        provisioning_routes, "get_settings",
        lambda: type("S", (), {"BIOMAX_SYNC_TOKEN": "secret"})(),
    )
    with pytest.raises(HTTPException) as bad:
        provisioning_routes._verify_sync_token("wrong")
    assert bad.value.status_code == 401
    assert provisioning_routes._verify_sync_token("secret") is None


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


async def test_list_devices_reports_flag_and_serials(monkeypatch):
    # /devices is NOT behind the enabled gate: the UI must tell "feature off"
    # apart from "no devices configured". It reports both the flag and the
    # configured serials (sorted), leaking nothing an admin didn't already set.
    monkeypatch.setattr(
        provisioning_routes, "get_settings",
        lambda: type("S", (), {"BIOMAX_PROVISIONING_ENABLED": False})(),
    )
    monkeypatch.setattr(
        provisioning_routes, "_allowed_serials", lambda: {"DEV-B", "DEV-A"}
    )
    result = await provisioning_routes.list_devices(_user={})
    assert result.enabled is False
    assert [d.dev_id for d in result.devices] == ["DEV-A", "DEV-B"]
