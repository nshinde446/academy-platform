"""Vendor-agnostic punch event shape + BioMax-specific wrappers.

The internal ``PunchEvent`` is what every downstream component sees.
Vendor-specific payloads get normalized into a list of these before
the service writes them to ``RawPunchLog``.

When BioMax docs arrive, the only thing that changes is
``parse_biomax_webhook_payload`` below.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class PunchEvent(BaseModel):
    """Normalized punch event. One row per punch in/out."""

    # Vendor-assigned identifier for the user (typically a numeric
    # string). We match this against ``Student.rfid_number`` to resolve
    # to a Student row.
    vendor_user_id: str
    punch_timestamp: datetime
    # Optional — some vendors send IN/OUT direction, others just send a
    # punch event. We don't currently model direction; RawPunchLog
    # stores raw timestamps and the attendance aggregator infers state.
    direction: str | None = None
    # Where the punch came from (device serial, gate code, etc.).
    # Lands in RawPunchLog.device_id.
    device_id: str = "unknown"
    # Vendor's batch id if they push punches in groups — used for
    # idempotency / replay detection.
    sync_batch_id: str | None = None


class BiomaxWebhookPayload(BaseModel):
    """Top-level shape of the BioMax webhook body.

    PLACEHOLDER — replace with the real shape from vendor docs. Keeping
    this permissive so the route doesn't reject events until we know
    the actual schema. Once known, tighten the types here and the
    parser stops needing defensive try/except.
    """

    cloud_id: str | None = None
    events: list[dict[str, Any]] = Field(default_factory=list)


def parse_biomax_webhook_payload(raw: dict[str, Any]) -> list[PunchEvent]:
    """Convert a BioMax webhook body into a list of normalized
    ``PunchEvent``.

    PLACEHOLDER mapping. Once vendor docs arrive, replace the field
    extraction lines with the actual keys. Defensive on every field so
    a partial / unexpected payload doesn't 500 the whole webhook —
    bad rows are skipped, good ones still ingest.
    """
    payload = BiomaxWebhookPayload.model_validate(raw)
    out: list[PunchEvent] = []
    for ev in payload.events:
        try:
            vendor_user_id = str(ev.get("user_id") or ev.get("uid") or ev.get("EmployeeCode") or "").strip()
            ts_raw = ev.get("punch_time") or ev.get("timestamp") or ev.get("PunchTime")
            if not vendor_user_id or not ts_raw:
                continue
            ts = ts_raw if isinstance(ts_raw, datetime) else datetime.fromisoformat(str(ts_raw))
            out.append(
                PunchEvent(
                    vendor_user_id=vendor_user_id,
                    punch_timestamp=ts,
                    direction=ev.get("direction") or ev.get("InOut"),
                    device_id=str(ev.get("device_id") or ev.get("DeviceSerial") or "biomax"),
                    sync_batch_id=str(ev.get("sync_batch_id") or "") or None,
                )
            )
        except (ValueError, TypeError):
            # Skip malformed events; webhook overall still succeeds.
            continue
    return out


class AffectedPunch(BaseModel):
    """A successfully-ingested punch, surfaced so callers can rebuild the
    matching day rows without re-querying. Vendor-agnostic."""

    student_id: uuid.UUID
    punch_timestamp: datetime


class IngestResult(BaseModel):
    """What the webhook / manual import endpoints return."""

    received: int
    inserted: int
    skipped_no_student: int
    skipped_duplicate: int
    errors: list[str] = Field(default_factory=list)
    # Inserted (student, timestamp) pairs — lets the caller recompute exactly
    # the affected DailyAttendance rows (near-real-time), not the whole branch.
    affected: list[AffectedPunch] = Field(default_factory=list)
