"""BioMax provisioning — business logic (the only place the rules live).

Builds the captured ``SET_USER_INFO`` payload, enqueues register commands for an
EXPLICIT student set, renders a dry-run diff, and reconciles platform students
against the device-user mirror. Emission to the device and result confirmation
are a separate, capture-gated increment; nothing here talks to the terminal.

Payload + identity contract: docs/biomax-provisioning-implementation.md §0.6.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.attendance.models.provisioning_models import (
    CMD_GET_USER_INFO,
    CMD_SET_USER_INFO,
    DEFAULT_VALID_END,
    DEFAULT_VALID_START,
    STATUS_PENDING,
)
from app.modules.attendance.repositories import (
    attendance_repository,
    device_command_repo,
)
from app.modules.attendance.schemas.provisioning_schemas import (
    PlannedCommand,
    ProvisionPlanResponse,
    ProvisionPushResponse,
    ReconcileResponse,
    ReconcileRow,
)
from app.modules.student.models.student_models import Student

# Device name field is short (SmartOffice EmployeeName is nvarchar(50)); truncate
# so a long full name can never be rejected by the firmware.
DEVICE_NAME_MAX = 50

# Keys that would carry biometric PII — rejected from any payload by construction.
# There is nothing biometric to push: a face template enrols physically at the
# device and can never be generated from our DB.
BIOMETRIC_KEYS = {"face", "photo", "logphoto", "fps", "template", "image"}


class PayloadError(ValueError):
    """A student can't be turned into a valid device user (bad/missing userId)."""


def device_name(student: Student) -> str:
    return f"{student.first_name} {student.last_name}".strip()[:DEVICE_NAME_MAX]


def build_user_payload(rfid: str | None, name: str) -> dict:
    """Build the wire-ready ``SET_USER_INFO`` payload for one user.

    ``userId`` = the student's ``rfid_number`` (which, despite the column name,
    is the *device userId*, not a physical card). It must be present and NUMERIC:
    an alphanumeric userId was observed not to sync to the device (§0.6). ``card``
    is left empty — students authenticate by face/thumb, not RFID cards. The
    vendor's typo'd validity keys ``vaildStart`` / ``vaildEnd`` are intentional.
    """
    user_id = (rfid or "").strip()
    if not user_id:
        raise PayloadError("student has no rfid_number (device userId)")
    if not user_id.isdigit():
        raise PayloadError(f"device userId must be numeric, got {user_id!r}")

    user = {
        "userId": user_id,
        # Cap here too (not just in device_name) so any caller is device-safe.
        "name": (name or "").strip()[:DEVICE_NAME_MAX],
        "privilege": 0,
        "card": "",
        "pwd": "",
        "vaildStart": DEFAULT_VALID_START,
        "vaildEnd": DEFAULT_VALID_END,
    }
    _assert_no_biometrics(user)
    return {"users": [user]}


def _assert_no_biometrics(user: dict) -> None:
    bad = {k for k in user if k.lower() in BIOMETRIC_KEYS}
    if bad:
        raise PayloadError(f"payload must not carry biometric keys: {sorted(bad)}")


def _idempotency_key(dev_id: str, command: str, vendor_user_id: str) -> str:
    return f"{dev_id}:{command}:{vendor_user_id}"


async def _students_in_branch(
    session: AsyncSession, branch_id: uuid.UUID, student_ids: list[uuid.UUID]
) -> list[Student]:
    if not student_ids:
        return []
    result = await session.execute(
        select(Student).where(
            Student.id.in_(student_ids),
            Student.branch_id == branch_id,
            Student.is_deleted == False,
        )
    )
    return list(result.scalars().all())


def _plan_for_student(student: Student, on_device: set[str]) -> PlannedCommand:
    """Classify what a push would do for one student, without side effects."""
    try:
        payload = build_user_payload(student.rfid_number, device_name(student))
    except PayloadError as exc:
        return PlannedCommand(
            student_id=student.id, action="skipped", reason=str(exc)
        )
    user_id = payload["users"][0]["userId"]
    action = "update" if user_id in on_device else "create"
    return PlannedCommand(
        student_id=student.id,
        vendor_user_id=user_id,
        name=payload["users"][0]["name"],
        action=action,
    )


async def render_dry_run(
    session: AsyncSession,
    branch_id: uuid.UUID,
    dev_id: str,
    student_ids: list[uuid.UUID],
) -> ProvisionPlanResponse:
    """What a push WOULD do — build every command, diff against the mirror, but
    enqueue nothing."""
    students = await _students_in_branch(session, branch_id, student_ids)
    mirror = await device_command_repo.list_device_users(session, branch_id, dev_id)
    on_device = {u.vendor_user_id for u in mirror}

    plans = [_plan_for_student(s, on_device) for s in students]
    return ProvisionPlanResponse(
        dev_id=dev_id,
        to_create=sum(1 for p in plans if p.action == "create"),
        to_update=sum(1 for p in plans if p.action == "update"),
        no_change=sum(1 for p in plans if p.action == "no_change"),
        skipped=sum(1 for p in plans if p.action == "skipped"),
        commands=plans,
    )


async def enqueue_students(
    session: AsyncSession,
    branch_id: uuid.UUID,
    dev_id: str,
    student_ids: list[uuid.UUID],
) -> ProvisionPushResponse:
    """Enqueue a register command per student in an EXPLICIT set. Idempotent: a
    student already in flight (pending/sent) for this device is skipped, so a
    re-run of a bulk push never double-enqueues."""
    students = await _students_in_branch(session, branch_id, student_ids)

    plans: list[PlannedCommand] = []
    buildable: list[tuple[Student, dict]] = []
    for student in students:
        try:
            payload = build_user_payload(student.rfid_number, device_name(student))
        except PayloadError as exc:
            plans.append(
                PlannedCommand(student_id=student.id, action="skipped", reason=str(exc))
            )
            continue
        buildable.append((student, payload))

    # Code-level idempotency (the partial-unique index is the backstop).
    candidate_ids = [p["users"][0]["userId"] for _, p in buildable]
    inflight = await device_command_repo.inflight_user_ids(
        session, dev_id, candidate_ids
    )

    rows: list[dict] = []
    for student, payload in buildable:
        user_id = payload["users"][0]["userId"]
        if user_id in inflight:
            plans.append(
                PlannedCommand(
                    student_id=student.id,
                    vendor_user_id=user_id,
                    name=payload["users"][0]["name"],
                    action="skipped",
                    reason="already queued",
                )
            )
            continue
        rows.append(
            {
                "branch_id": branch_id,
                "dev_id": dev_id,
                "command": CMD_SET_USER_INFO,
                "vendor_user_id": user_id,
                "payload": payload,
                "student_id": student.id,
                "command_status": STATUS_PENDING,
                "idempotency_key": _idempotency_key(dev_id, CMD_SET_USER_INFO, user_id),
            }
        )
        plans.append(
            PlannedCommand(
                student_id=student.id,
                vendor_user_id=user_id,
                name=payload["users"][0]["name"],
                action="create",
            )
        )

    if rows:
        await device_command_repo.enqueue(session, rows)

    return ProvisionPushResponse(
        dev_id=dev_id,
        enqueued=len(rows),
        skipped=sum(1 for p in plans if p.action == "skipped"),
        commands=plans,
    )


async def reconcile(
    session: AsyncSession, branch_id: uuid.UUID, dev_id: str
) -> ReconcileResponse:
    """Three-way diff: platform students (with a valid device userId) vs the
    device-user mirror. Until the mirror is populated (a later increment) every
    student reads as on-platform-not-on-device — which is correct."""
    result = await session.execute(
        select(Student).where(
            Student.branch_id == branch_id,
            Student.is_deleted == False,
            Student.rfid_number.isnot(None),
        )
    )
    students = list(result.scalars().all())
    platform: dict[str, Student] = {}
    for s in students:
        rfid = (s.rfid_number or "").strip()
        if rfid.isdigit():
            platform[rfid] = s

    mirror = await device_command_repo.list_device_users(session, branch_id, dev_id)
    device: dict[str, object] = {u.vendor_user_id: u for u in mirror}
    # Users the device reports a FACE template for — the ground-truth "enrolled"
    # signal once the on-site sync agent has pushed a snapshot (see
    # sync_device_users). Identity-only mirror rows (has_face False) are on the
    # device but still need a face enrolled at the terminal.
    has_face_on_device = {
        uid for uid, u in device.items() if getattr(u, "has_face", False)
    }

    # Identities we've already confirmed onto the device (per its ack). A student
    # not in the mirror but with a confirmed push isn't "unpushed" — the device
    # just hasn't mirrored them back yet, so the real next step is enrolment at
    # the terminal, not another push.
    confirmed = await device_command_repo.confirmed_user_ids(
        session, dev_id, list(platform.keys())
    )

    # A student who has ever punched is definitively enrolled WITH a face (a
    # template only exists after enrolment at the terminal), even if a mirror
    # snapshot hasn't captured them — so trust a punch as face-proof too.
    enrolled_student_ids = await attendance_repository.student_ids_with_punches(
        session, branch_id
    )

    need_push: list[ReconcileRow] = []
    awaiting_face: list[ReconcileRow] = []
    drift: list[ReconcileRow] = []
    for uid, student in platform.items():
        on_device = uid in device
        # "Enrolled" = the device holds a face for them, OR they've punched.
        enrolled = uid in has_face_on_device or student.id in enrolled_student_ids
        if enrolled:
            # Fully provisioned — the only thing to flag is a stale name on the
            # device (a push re-registers the platform name).
            if on_device and getattr(device[uid], "name", None) != device_name(student):
                drift.append(
                    ReconcileRow(
                        vendor_user_id=uid, name=device_name(student), student_id=student.id
                    )
                )
            continue
        # No face yet. If the identity is on the device (mirror) or a push was
        # confirmed, the next step is enrolment at the terminal, not another push.
        row = ReconcileRow(
            vendor_user_id=uid, name=device_name(student), student_id=student.id
        )
        if on_device or uid in confirmed:
            awaiting_face.append(row)
        else:
            need_push.append(row)

    on_device_only = [
        ReconcileRow(vendor_user_id=uid, name=getattr(u, "name", None))
        for uid, u in device.items()
        if uid not in platform
    ]

    return ReconcileResponse(
        dev_id=dev_id,
        on_platform_not_on_device=need_push,
        awaiting_face_enrollment=awaiting_face,
        on_device_not_on_platform=on_device_only,
        drift=drift,
    )


async def sync_device_users(
    session: AsyncSession,
    branch_id: uuid.UUID,
    dev_id: str,
    users: list,
) -> tuple[int, int]:
    """Rebuild the device-user mirror from a full snapshot the on-site agent read
    off the terminal (local ``GetUserIdList`` + ``GetUserInfo``). Ground truth for
    who is actually enrolled — and, via ``has_face``, who has a face — so
    reconcile's "awaiting face" / "name drift" stop depending on catching the
    device's one-time enrollment pushes. Full-replace: users the device no longer
    holds are dropped from the mirror. Returns ``(upserted, removed)``."""
    rows = [
        {
            "vendor_user_id": u.vendor_user_id,
            "name": u.name,
            "privilege": u.privilege,
            "valid_start": u.valid_start,
            "valid_end": u.valid_end,
            "has_face": u.has_face,
        }
        for u in users
    ]
    return await device_command_repo.replace_device_users(
        session, branch_id=branch_id, dev_id=dev_id, rows=rows
    )


# ── cloud-async user-info refresh (GET_USER_INFO over the receive_cmd channel) ──
# Instead of an on-site agent reading the terminal's local API, the portal queues
# GET_USER_INFO commands the device fetches on its normal VPS poll, and the device
# returns its users (incl. whether each has a face) in the send_cmd_result body.
# No on-site PC / LAN dependency. The device includes biometric blobs in that
# body; we read ONLY the has-a-template boolean and identity — never the blob.

# Batch small: each returned user carries face+photo blobs (~50 KB), and the
# device's response buffer is ~400 KB, so keep a page comfortably under it (the
# device pages via packageId as a backstop, which we follow).
USER_INFO_BATCH_SIZE = 5
# A GET_USER_INFO record counts as "has a face/biometric" if any template field is
# present — matches the on-site agent + the enrollment-mirror rule.
_FACE_FIELDS = ("face", "fps", "palm")


def _user_info_to_mirror(u: dict) -> dict | None:
    """Map one device user record (from a GET_USER_INFO result) to mirror fields —
    identity + ``has_face`` ONLY. Biometric blobs (``face``/``photo``/``fps``…) are
    never read out here, so they can't be persisted downstream."""
    uid = str(u.get("userId") or "").strip()
    if not uid:
        return None
    name = (str(u.get("name") or "").strip() or None)
    if name:
        name = name[:DEVICE_NAME_MAX]
    try:
        privilege = int(u.get("privilege") or 0)
    except (TypeError, ValueError):
        privilege = 0
    has_face = any(bool(u.get(k)) for k in _FACE_FIELDS)
    vs = str(u.get("vaildStart") or u.get("validStart") or "").strip()
    ve = str(u.get("vaildEnd") or u.get("validEnd") or "").strip()
    return {
        "vendor_user_id": uid,
        "name": name,
        "privilege": privilege,
        "has_face": has_face,
        "valid_start": vs if vs.isdigit() else None,
        "valid_end": ve if ve.isdigit() else None,
    }


async def apply_user_info_page(
    session: AsyncSession, branch_id: uuid.UUID, dev_id: str, users: list
) -> int:
    """Upsert one page of GET_USER_INFO users into the mirror (identity + has_face,
    blobs dropped). Upsert-only — a single page isn't authoritative over the whole
    table, so it never removes rows. Returns how many rows were upserted."""
    n = 0
    for u in users or []:
        if not isinstance(u, dict):
            continue
        fields = _user_info_to_mirror(u)
        if fields is None:
            continue
        await device_command_repo.upsert_device_user(
            session, branch_id=branch_id, dev_id=dev_id, **fields
        )
        n += 1
    return n


def build_user_info_command_row(
    branch_id: uuid.UUID, dev_id: str, user_ids: list[str], page_id: int = 0
) -> dict:
    """One GET_USER_INFO command row — asks the device for these users' info at the
    given page. ``vendor_user_id`` is null (batch command). The idempotency key
    carries a fresh nonce: a refresh is meant to re-run, and cross-run dedup would
    collide with a same-batch command still in-flight (``sent``) — which is exactly
    what happens when the device is draining fast — so each command gets a unique
    key. Stale PENDING from a prior run is cleared by ``enqueue_user_info_refresh``."""
    nonce = uuid.uuid4().hex[:12]
    return {
        "branch_id": branch_id,
        "dev_id": dev_id,
        "command": CMD_GET_USER_INFO,
        "vendor_user_id": None,
        "payload": {"packageId": page_id, "usersId": list(user_ids)},
        "command_status": STATUS_PENDING,
        "idempotency_key": f"{dev_id}:{CMD_GET_USER_INFO}:{page_id}:{nonce}",
    }


async def enqueue_user_info_refresh(
    session: AsyncSession,
    branch_id: uuid.UUID,
    dev_id: str,
    user_ids: list[str],
    batch_size: int = USER_INFO_BATCH_SIZE,
) -> int:
    """Queue GET_USER_INFO commands (batched) for the given device userIds. Clears
    any still-pending GET_USER_INFO for the device first so a re-trigger doesn't
    pile up. The device drains them on its normal poll and returns each user's
    has-face; the send_cmd_result handler folds the results into the mirror.
    Returns the number of commands enqueued."""
    await device_command_repo.cancel_pending_by_command(session, dev_id, CMD_GET_USER_INFO)
    ids = [i for i in user_ids if i]
    rows = [
        build_user_info_command_row(branch_id, dev_id, ids[i : i + batch_size])
        for i in range(0, len(ids), batch_size)
    ]
    if rows:
        await device_command_repo.enqueue(session, rows)
    return len(rows)


async def user_ids_for_refresh(
    session: AsyncSession, branch_id: uuid.UUID, dev_id: str, scope: str
) -> list[str]:
    """The device userIds to refresh. ``scope='awaiting'`` (default) targets only
    students still 'awaiting face' — the ones whose enrolment status might have
    changed — which keeps the pull small; ``scope='all'`` refreshes every
    platform userId."""
    if scope == "awaiting":
        rec = await reconcile(session, branch_id, dev_id)
        return [r.vendor_user_id for r in rec.awaiting_face_enrollment]
    result = await session.execute(
        select(Student).where(
            Student.branch_id == branch_id,
            Student.is_deleted == False,
            Student.rfid_number.isnot(None),
        )
    )
    ids = []
    for s in result.scalars().all():
        rfid = (s.rfid_number or "").strip()
        if rfid.isdigit():
            ids.append(rfid)
    return ids
