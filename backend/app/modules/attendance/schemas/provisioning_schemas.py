"""Request/response schemas for BioMax device provisioning."""

import uuid
from datetime import datetime

from pydantic import BaseModel


class ProvisionPushRequest(BaseModel):
    """Enqueue register (SET_USER_INFO) commands for an EXPLICIT student set.

    There is no "push everyone" — the caller always names the students and the
    target device (see docs/coding_rules + the no-blind-bulk agreement).
    """

    dev_id: str
    student_ids: list[uuid.UUID]


class ProvisionDryRunRequest(ProvisionPushRequest):
    """Same inputs as a push, but renders the plan without enqueuing anything."""


class PlannedCommand(BaseModel):
    """One student's would-be / queued registration, for dry-run + push results."""

    student_id: uuid.UUID
    vendor_user_id: str | None = None
    name: str | None = None
    action: str  # create | update | no_change | skipped
    reason: str | None = None  # why skipped (e.g. missing rfid, non-numeric)


class ProvisionPlanResponse(BaseModel):
    """Dry-run output: what a push WOULD do, no side effects."""

    dev_id: str
    to_create: int
    to_update: int
    no_change: int
    skipped: int
    commands: list[PlannedCommand]


class ProvisionPushResponse(BaseModel):
    """Push output: what was actually enqueued (idempotent — re-runs are safe)."""

    dev_id: str
    enqueued: int
    skipped: int
    commands: list[PlannedCommand]


class DeviceCommandResponse(BaseModel):
    id: uuid.UUID
    dev_id: str
    command: str
    vendor_user_id: str | None = None
    # For batch commands (GET_USER_INFO), how many userIds it targets — lets the
    # UI show "batch · N users" instead of a bare "—" when vendor_user_id is null.
    batch_user_count: int | None = None
    student_id: uuid.UUID | None = None
    command_status: str
    attempts: int
    last_error: str | None = None
    sent_at: datetime | None = None
    confirmed_at: datetime | None = None
    created_at: datetime
    model_config = {"from_attributes": True}


class ProvisionDevice(BaseModel):
    """A configured BioMax device the UI can reconcile against."""

    dev_id: str


class ProvisionDevicesResponse(BaseModel):
    """The configured devices + whether provisioning is enabled at all, so the
    UI can show the right empty/disabled state without a second call."""

    enabled: bool
    devices: list[ProvisionDevice]


class DeviceUserSnapshotRow(BaseModel):
    """One user as read from the terminal's own table (local ``GetUserInfo``).

    ``has_face`` is the whole point: the device reports whether a face template
    exists for this user (``face`` field present), which is the ground truth
    reconcile needs. Biometric blobs are NEVER sent — the agent extracts only
    presence, never the template."""

    vendor_user_id: str
    name: str | None = None
    privilege: int = 0
    has_face: bool = False
    valid_start: str | None = None
    valid_end: str | None = None


class DeviceUserSnapshotRequest(BaseModel):
    """Full snapshot of a device's user table, pushed by the on-site sync agent.
    Full-replace semantics: users absent from ``users`` are removed from the
    mirror (they were deleted on the device)."""

    dev_id: str
    users: list[DeviceUserSnapshotRow]


class DeviceUserSnapshotResponse(BaseModel):
    dev_id: str
    upserted: int
    removed: int
    total: int


class RestoreResponse(BaseModel):
    """Result of queueing a biometric restore for a (replaced/reset) device."""

    dev_id: str
    commands_enqueued: int


class DeviceStatusResponse(BaseModel):
    """The device's own latest self-reported counts (from its poll) + heartbeat."""

    dev_id: str
    last_seen_at: datetime | None = None
    user_count: int | None = None
    face_count: int | None = None
    fp_count: int | None = None
    card_count: int | None = None
    user_limit: int | None = None
    face_limit: int | None = None
    firmware: str | None = None


class BiometricStatusResponse(BaseModel):
    """How many users have a biometric backup for this device — restore coverage."""

    dev_id: str
    backed_up: int


class RefreshUserInfoResponse(BaseModel):
    """Result of queueing a cloud-async user-info refresh: how many device userIds
    were targeted and how many GET_USER_INFO commands were enqueued for the device
    to drain on its normal poll."""

    dev_id: str
    scope: str
    targeted_users: int
    commands_enqueued: int


class ReconcileRow(BaseModel):
    vendor_user_id: str
    name: str | None = None
    student_id: uuid.UUID | None = None


class ReconcileResponse(BaseModel):
    """Diff between platform students and the device's user mirror.

    ``on_platform_not_on_device`` is now *truly* un-pushed identities (no
    confirmed push). ``awaiting_face_enrollment`` are identities we've confirmed
    onto the device but which the device hasn't mirrored back — in practice
    because no face is enrolled yet, so the next action is enrolment at the
    terminal, not another push. Students who have ever punched are treated as
    fully enrolled (a face template only exists after enrolment at the terminal)
    and appear in neither bucket, regardless of the mirror."""

    dev_id: str
    on_platform_not_on_device: list[ReconcileRow]
    awaiting_face_enrollment: list[ReconcileRow] = []
    on_device_not_on_platform: list[ReconcileRow]
    drift: list[ReconcileRow]  # present on both, name/validity differs
