"""Fleet face-sync — fan out every backed-up face to every device missing it
("enrol once, available everywhere"). Idempotent, dry-run-able."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.attendance.models.provisioning_models import (
    CMD_SET_USER_INFO,
    STATUS_CONFIRMED,
    DeviceCommand,
    DeviceUser,
    DeviceUserBiometric,
)
from app.modules.attendance.services import provisioning_service as prov

BRANCH_A = uuid.UUID("00000000-0000-0000-0000-000000000001")
DEV_A = "DEVICE-A"
DEV_B = "DEVICE-B"


async def _face_backup(db: AsyncSession, dev_id: str, uid: str, name="Person"):
    db.add(DeviceUserBiometric(
        branch_id=BRANCH_A, dev_id=dev_id, vendor_user_id=uid, name=name,
        face_enc=b"enc", captured_at=datetime.now(timezone.utc),
    ))


async def _mirror(db: AsyncSession, dev_id: str, uid: str, has_face: bool):
    db.add(DeviceUser(
        branch_id=BRANCH_A, dev_id=dev_id, vendor_user_id=uid, name="Person",
        has_face=has_face,
    ))


async def test_fleet_sync_fans_missing_faces(db_session: AsyncSession, seed_data, monkeypatch):
    monkeypatch.setattr(prov, "_live_device_serials", lambda: [DEV_A, DEV_B])
    # 9001 has a face backed up (from DEV_A) and is enrolled on DEV_A but missing on DEV_B.
    await _face_backup(db_session, DEV_A, "9001")
    await _mirror(db_session, DEV_A, "9001", has_face=True)
    await db_session.flush()

    # Dry-run: DEV_A already has it (source); DEV_B is missing it.
    plan = await prov.sync_fleet_faces(db_session, BRANCH_A, dry_run=True)
    assert plan["faces_in_pool"] == 1
    assert plan["per_device_enqueued"][DEV_A] == 0
    assert plan["per_device_enqueued"][DEV_B] == 1

    # Real run enqueues a cross-device restore for DEV_B, sourced from DEV_A.
    res = await prov.sync_fleet_faces(db_session, BRANCH_A, dry_run=False)
    assert res["total_enqueued"] == 1
    cmd = (await db_session.execute(
        select(DeviceCommand).where(
            DeviceCommand.dev_id == DEV_B, DeviceCommand.vendor_user_id == "9001"
        )
    )).scalar_one()
    assert cmd.command == CMD_SET_USER_INFO
    assert cmd.payload["restore_biometrics"] is True
    assert cmd.payload["restore_source_dev_id"] == DEV_A

    # Idempotent: re-running enqueues nothing (already in flight on DEV_B).
    again = await prov.sync_fleet_faces(db_session, BRANCH_A, dry_run=False)
    assert again["total_enqueued"] == 0


async def test_fleet_sync_skips_devices_that_already_have_the_face(
    db_session: AsyncSession, seed_data, monkeypatch
):
    monkeypatch.setattr(prov, "_live_device_serials", lambda: [DEV_A, DEV_B])
    await _face_backup(db_session, DEV_A, "9002")
    await _mirror(db_session, DEV_A, "9002", has_face=True)
    await _mirror(db_session, DEV_B, "9002", has_face=True)  # already enrolled on B too
    await db_session.flush()

    res = await prov.sync_fleet_faces(db_session, BRANCH_A, dry_run=False)
    assert res["total_enqueued"] == 0


async def _confirmed_cmd(db, dev_id, uid, *, restore: bool, key: str):
    payload = {"users": [{"userId": uid}]}
    if restore:
        payload["restore_biometrics"] = True
    db.add(DeviceCommand(
        branch_id=BRANCH_A, dev_id=dev_id, command=CMD_SET_USER_INFO,
        vendor_user_id=uid, payload=payload, command_status=STATUS_CONFIRMED,
        idempotency_key=key,
    ))


async def test_identity_push_does_not_block_face_sync(
    db_session: AsyncSession, seed_data, monkeypatch
):
    """A confirmed IDENTITY-only push must NOT count as 'has face' — the person
    still needs their face fanned out."""
    monkeypatch.setattr(prov, "_live_device_serials", lambda: [DEV_A, DEV_B])
    await _face_backup(db_session, DEV_A, "9100")
    await _confirmed_cmd(db_session, DEV_B, "9100", restore=False, key="id-9100")
    await db_session.flush()

    res = await prov.sync_fleet_faces(db_session, BRANCH_A, dry_run=True)
    assert res["per_device_enqueued"][DEV_B] == 1  # face still queued despite identity push


async def test_confirmed_face_restore_blocks_repush(
    db_session: AsyncSession, seed_data, monkeypatch
):
    """A confirmed FACE restore means the device has it — don't re-push."""
    monkeypatch.setattr(prov, "_live_device_serials", lambda: [DEV_A, DEV_B])
    await _face_backup(db_session, DEV_A, "9101")
    await _confirmed_cmd(db_session, DEV_B, "9101", restore=True, key="face-9101")
    await db_session.flush()

    res = await prov.sync_fleet_faces(db_session, BRANCH_A, dry_run=True)
    assert res["per_device_enqueued"][DEV_B] == 0  # already face-restored → skip


async def test_live_device_serials_and_sync_run_without_monkeypatch(
    db_session: AsyncSession, seed_data
):
    """Exercise the REAL _live_device_serials()/get_settings() path (the other
    tests monkeypatch it, which once hid a missing get_settings import). With no
    configured serials the fleet has no targets — it must run cleanly, not crash."""
    assert isinstance(prov._live_device_serials(), list)
    res = await prov.sync_fleet_faces(db_session, BRANCH_A, dry_run=True)
    assert res["total_enqueued"] == 0
    assert res["per_device_enqueued"] == {}
