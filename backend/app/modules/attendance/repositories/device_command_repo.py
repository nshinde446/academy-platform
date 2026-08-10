"""Data access for the BioMax provisioning queue + device-user mirror.

Queries only — no business logic. Every read is branch-isolated where the caller
supplies a branch (``docs/db_conventions.md``) and filters soft-deleted rows.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.attendance.models.provisioning_models import (
    INFLIGHT_STATUSES,
    STATUS_CANCELLED,
    STATUS_CONFIRMED,
    STATUS_FAILED,
    STATUS_PENDING,
    STATUS_SENT,
    DeviceCommand,
    DeviceUser,
    DeviceUserBiometric,
)


# ── device_commands ───────────────────────────────────────────────────────────


async def enqueue(session: AsyncSession, rows: list[dict]) -> list[DeviceCommand]:
    """Bulk-insert command rows (already built by the service)."""
    objects = [DeviceCommand(**row) for row in rows]
    session.add_all(objects)
    await session.flush()
    return objects


async def inflight_user_ids(
    session: AsyncSession, dev_id: str, vendor_user_ids: list[str]
) -> set[str]:
    """Which of these userIds already have a pending/sent command for the device.

    Backs code-level idempotency (the DB partial-unique index is the backstop);
    a re-run of a bulk push skips users already in flight instead of erroring.
    """
    if not vendor_user_ids:
        return set()
    result = await session.execute(
        select(DeviceCommand.vendor_user_id).where(
            DeviceCommand.dev_id == dev_id,
            DeviceCommand.vendor_user_id.in_(vendor_user_ids),
            DeviceCommand.command_status.in_(INFLIGHT_STATUSES),
            DeviceCommand.is_deleted == False,
        )
    )
    return {row[0] for row in result.all() if row[0] is not None}


async def confirmed_user_ids(
    session: AsyncSession, dev_id: str, vendor_user_ids: list[str]
) -> set[str]:
    """Which of these userIds have a CONFIRMED push for the device — i.e. their
    identity has already been applied on the device (per the device's ack), even
    if the enrollment mirror hasn't reflected them yet (no face enrolled). Lets
    reconcile separate "still needs pushing" from "pushed, awaiting face"."""
    if not vendor_user_ids:
        return set()
    result = await session.execute(
        select(DeviceCommand.vendor_user_id).where(
            DeviceCommand.dev_id == dev_id,
            DeviceCommand.vendor_user_id.in_(vendor_user_ids),
            DeviceCommand.command_status == STATUS_CONFIRMED,
            DeviceCommand.is_deleted == False,
        )
    )
    return {row[0] for row in result.all() if row[0] is not None}


async def next_pending(session: AsyncSession, dev_id: str) -> DeviceCommand | None:
    """Oldest pending command for a device.

    ``skip_locked`` so the fast-polling device can't hand the same command to two
    concurrent requests (no-op on SQLite, which serialises writers anyway). Not
    wired into the ack path yet — that emission step is capture-gated.
    """
    result = await session.execute(
        select(DeviceCommand)
        .where(
            DeviceCommand.dev_id == dev_id,
            DeviceCommand.command_status == STATUS_PENDING,
            DeviceCommand.is_deleted == False,
        )
        .order_by(DeviceCommand.created_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    return result.scalar_one_or_none()


async def get_command(
    session: AsyncSession, command_id: uuid.UUID, branch_id: uuid.UUID
) -> DeviceCommand | None:
    result = await session.execute(
        select(DeviceCommand).where(
            DeviceCommand.id == command_id,
            DeviceCommand.branch_id == branch_id,
            DeviceCommand.is_deleted == False,
        )
    )
    return result.scalar_one_or_none()


async def find_by_trans_id(
    session: AsyncSession, dev_id: str, trans_id: str
) -> DeviceCommand | None:
    """Match a device's ``send_cmd_result`` back to the command we emitted.

    Keyed on the ``trans_id`` we set when the command was served (``mark_sent``)
    and echoed by the device. Device-scoped (not branch-scoped) — the device only
    knows its own ``dev_id`` and the opaque ``trans_id``. Newest send first, so a
    re-used token resolves to the latest emission."""
    if not trans_id:
        return None
    result = await session.execute(
        select(DeviceCommand)
        .where(
            DeviceCommand.dev_id == dev_id,
            DeviceCommand.trans_id == trans_id,
            DeviceCommand.is_deleted == False,
        )
        .order_by(DeviceCommand.sent_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def list_commands(
    session: AsyncSession,
    branch_id: uuid.UUID,
    dev_id: str | None = None,
    command_status: str | None = None,
    offset: int = 0,
    limit: int = 100,
) -> list[DeviceCommand]:
    stmt = select(DeviceCommand).where(
        DeviceCommand.branch_id == branch_id,
        DeviceCommand.is_deleted == False,
    )
    if dev_id:
        stmt = stmt.where(DeviceCommand.dev_id == dev_id)
    if command_status:
        stmt = stmt.where(DeviceCommand.command_status == command_status)
    stmt = stmt.order_by(DeviceCommand.created_at.desc()).offset(offset).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def mark_sent(
    session: AsyncSession, command: DeviceCommand, trans_id: str
) -> DeviceCommand:
    command.command_status = STATUS_SENT
    command.trans_id = trans_id
    command.attempts += 1
    command.sent_at = datetime.now(timezone.utc)
    await session.flush()
    return command


async def mark_confirmed(
    session: AsyncSession, command: DeviceCommand
) -> DeviceCommand:
    command.command_status = STATUS_CONFIRMED
    command.confirmed_at = datetime.now(timezone.utc)
    command.last_error = None
    await session.flush()
    return command


async def mark_failed(
    session: AsyncSession, command: DeviceCommand, error: str
) -> DeviceCommand:
    command.command_status = STATUS_FAILED
    command.last_error = error
    await session.flush()
    return command


async def cancel_pending(
    session: AsyncSession, command: DeviceCommand
) -> DeviceCommand:
    """Pull a still-pending command out of the queue. Sent commands can't be
    cancelled (already handed to the device)."""
    command.command_status = STATUS_CANCELLED
    await session.flush()
    return command


async def cancel_pending_by_command(
    session: AsyncSession, dev_id: str, command: str
) -> int:
    """Cancel all still-PENDING commands of a given kind for a device (e.g. clear
    stale GET_USER_INFO before a fresh refresh so they don't pile up). Sent ones
    are left alone — the device already has them. Returns how many were cancelled."""
    result = await session.execute(
        select(DeviceCommand).where(
            DeviceCommand.dev_id == dev_id,
            DeviceCommand.command == command,
            DeviceCommand.command_status == STATUS_PENDING,
            DeviceCommand.is_deleted == False,
        )
    )
    rows = list(result.scalars().all())
    for cmd in rows:
        cmd.command_status = STATUS_CANCELLED
    await session.flush()
    return len(rows)


# ── device_users (mirror) ─────────────────────────────────────────────────────


async def list_device_users(
    session: AsyncSession, branch_id: uuid.UUID, dev_id: str
) -> list[DeviceUser]:
    result = await session.execute(
        select(DeviceUser).where(
            DeviceUser.branch_id == branch_id,
            DeviceUser.dev_id == dev_id,
            DeviceUser.is_deleted == False,
        )
    )
    return list(result.scalars().all())


async def replace_device_users(
    session: AsyncSession,
    *,
    branch_id: uuid.UUID,
    dev_id: str,
    rows: list[dict],
) -> tuple[int, int]:
    """Rebuild the mirror for a device from a full snapshot of its user table
    (read on-site via the terminal's local API). Full-replace semantics: every
    snapshot row is upserted; any existing mirror row for this device whose
    ``vendor_user_id`` is NOT in the snapshot is soft-deleted (the user was
    removed on the device). Returns ``(upserted, removed)``.

    This is the ground-truth path: unlike the device's one-time
    ``realtime_enroll_data`` push (which we only catch if we happen to be
    listening at the moment of enrolment), a snapshot reflects exactly who is on
    the device right now — including whether each has a face (``has_face``).
    """
    seen: set[str] = set()
    for row in rows:
        await upsert_device_user(session, branch_id=branch_id, dev_id=dev_id, **row)
        seen.add(row["vendor_user_id"])

    existing = await session.execute(
        select(DeviceUser).where(
            DeviceUser.dev_id == dev_id,
            DeviceUser.branch_id == branch_id,
            DeviceUser.is_deleted == False,
        )
    )
    removed = 0
    for du in existing.scalars().all():
        if du.vendor_user_id not in seen:
            du.is_deleted = True
            removed += 1
    await session.flush()
    return len(seen), removed


async def upsert_device_user(
    session: AsyncSession,
    *,
    branch_id: uuid.UUID,
    dev_id: str,
    vendor_user_id: str,
    name: str | None = None,
    privilege: int = 0,
    valid_start: str | None = None,
    valid_end: str | None = None,
    has_face: bool = False,
) -> DeviceUser:
    """Insert or update the mirror row for one device user (identity only)."""
    result = await session.execute(
        select(DeviceUser).where(
            DeviceUser.dev_id == dev_id,
            DeviceUser.vendor_user_id == vendor_user_id,
            DeviceUser.is_deleted == False,
        )
    )
    row = result.scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if row is None:
        row = DeviceUser(
            branch_id=branch_id,
            dev_id=dev_id,
            vendor_user_id=vendor_user_id,
            name=name,
            privilege=privilege,
            valid_start=valid_start,
            valid_end=valid_end,
            has_face=has_face,
            last_seen_at=now,
        )
        session.add(row)
    else:
        row.name = name
        row.privilege = privilege
        row.valid_start = valid_start
        row.valid_end = valid_end
        row.has_face = has_face
        row.last_seen_at = now
    await session.flush()
    return row


async def get_biometric(
    session: AsyncSession, dev_id: str, vendor_user_id: str
) -> DeviceUserBiometric | None:
    result = await session.execute(
        select(DeviceUserBiometric).where(
            DeviceUserBiometric.dev_id == dev_id,
            DeviceUserBiometric.vendor_user_id == vendor_user_id,
            DeviceUserBiometric.is_deleted == False,
        )
    )
    return result.scalar_one_or_none()


async def list_backed_up_users(
    session: AsyncSession, branch_id: uuid.UUID, dev_id: str
) -> list[tuple[str, str | None]]:
    """(vendor_user_id, name) for every user that has a matchable biometric
    template backed up (face or fingerprint) — the set a restore re-pushes."""
    result = await session.execute(
        select(DeviceUserBiometric.vendor_user_id, DeviceUserBiometric.name).where(
            DeviceUserBiometric.branch_id == branch_id,
            DeviceUserBiometric.dev_id == dev_id,
            DeviceUserBiometric.is_deleted == False,
            or_(
                DeviceUserBiometric.face_enc.isnot(None),
                DeviceUserBiometric.fps_enc.isnot(None),
            ),
        )
    )
    return [(r[0], r[1]) for r in result.all()]


async def upsert_biometric(
    session: AsyncSession,
    *,
    branch_id: uuid.UUID,
    dev_id: str,
    vendor_user_id: str,
    student_id: uuid.UUID | None,
    name: str | None,
    face_enc: bytes | None,
    photo_enc: bytes | None,
    fps_enc: bytes | None,
) -> DeviceUserBiometric:
    """Insert/update the encrypted biometric backup for one user. A given
    ``realtime_enroll_data`` push may carry only some modalities, so a blob is
    overwritten ONLY when the new value is present — never wiped to NULL by a
    push that omitted it (so a prior photo survives a face-only re-enrol)."""
    result = await session.execute(
        select(DeviceUserBiometric).where(
            DeviceUserBiometric.dev_id == dev_id,
            DeviceUserBiometric.vendor_user_id == vendor_user_id,
            DeviceUserBiometric.is_deleted == False,
        )
    )
    row = result.scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if row is None:
        row = DeviceUserBiometric(
            branch_id=branch_id,
            dev_id=dev_id,
            vendor_user_id=vendor_user_id,
            student_id=student_id,
            name=name,
            face_enc=face_enc,
            photo_enc=photo_enc,
            fps_enc=fps_enc,
            captured_at=now,
        )
        session.add(row)
    else:
        if student_id is not None:
            row.student_id = student_id
        if name is not None:
            row.name = name
        if face_enc is not None:
            row.face_enc = face_enc
        if photo_enc is not None:
            row.photo_enc = photo_enc
        if fps_enc is not None:
            row.fps_enc = fps_enc
        row.captured_at = now
    await session.flush()
    return row
