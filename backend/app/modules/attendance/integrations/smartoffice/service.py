"""SmartOffice → domain sync.

Pulls biometric log rows from the SmartOffice cloud (``client.py``), maps each
row onto our vendor-agnostic ``PunchEvent``, and funnels them through the *same*
``ingest_punches`` + ``rebuild_after_ingest`` path every other feeder uses.
SmartOffice reports ``LogDate`` in the device's local wall-clock (the branch tz);
we convert to tz-aware UTC before storing (RawPunchLog is UTC).

The ``EmployeeCode`` is matched to ``Student.rfid_number`` — the same join BioMax
and eTimeOffice use — so enrolling a device user = setting that student's
rfid_number to the SmartOffice EmployeeCode.

Branch attribution: SmartOffice's ``GetDeviceLogs`` returns punches for *all*
devices on the account, tagged with ``SerialNumber``. For a single-site rollout
we attribute everything to the configured ``SMARTOFFICE_BRANCH_ID`` and,
optionally, ignore rows from serials outside ``SMARTOFFICE_DEVICE_SERIALS``.
Per-serial → per-branch mapping (multi-branch) is a later refinement.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config.settings import get_settings
from app.modules.attendance.integrations.biomax.schemas import PunchEvent
from app.modules.attendance.integrations.biomax.service import ingest_punches
from app.modules.attendance.integrations.smartoffice import client as so_client
from app.modules.attendance.services import daily_service
from app.modules.attendance.time_utils import get_tz


def _get(row: dict[str, Any], *keys: str) -> str:
    """First non-empty value among case-tolerant keys."""
    lowered = {k.lower(): v for k, v in row.items()}
    for k in keys:
        v = lowered.get(k.lower())
        if v not in (None, ""):
            return str(v).strip()
    return ""


def rows_to_events(
    rows: list[dict[str, Any]],
    tz_name: str | None,
    allowed_serials: set[str] | None = None,
) -> list[PunchEvent]:
    """Map SmartOffice log rows → PunchEvents (one per punch).

    ``allowed_serials`` (when given and non-empty) filters out punches from any
    device serial not on the list. A row we can't read (no code / bad date) is
    skipped, not fatal."""
    events: list[PunchEvent] = []
    for row in rows:
        empcode = _get(row, "EmployeeCode", "Empcode", "EmpCode", "PIN")
        if not empcode:
            continue
        serial = _get(row, "SerialNumber", "Serial", "DeviceSerial")
        if allowed_serials and serial and serial not in allowed_serials:
            continue

        naive = so_client.parse_log_datetime(_get(row, "LogDate", "PunchTime", "LogTime"))
        if naive is None:
            continue
        ts_utc = naive.replace(tzinfo=get_tz(tz_name)).astimezone(timezone.utc)

        events.append(
            PunchEvent(
                vendor_user_id=empcode,
                punch_timestamp=ts_utc,
                direction=_get(row, "PunchDirection", "Direction") or None,
                device_id=serial or "smartoffice",
            )
        )
    return events


def _allowed_serials() -> set[str]:
    raw = get_settings().SMARTOFFICE_DEVICE_SERIALS or ""
    return {s.strip() for s in raw.split(",") if s.strip()}


async def sync_range(
    session: AsyncSession,
    *,
    branch_id: uuid.UUID,
    from_date: date,
    to_date: date,
    http_client=None,
) -> dict[str, Any]:
    """Pull + ingest punches for an inclusive date range. Returns a summary dict.

    Raises ``SmartOfficeError`` if the API call fails (caller decides whether to
    swallow). Ingest is idempotent (5s dedup), so overlapping ranges across polls
    are safe."""
    settings = get_settings()
    from_dt, to_dt = so_client.day_bounds(from_date, to_date)
    rows = await so_client.fetch_device_logs(
        base_url=settings.SMARTOFFICE_BASE_URL,
        api_key=settings.SMARTOFFICE_API_KEY,
        from_dt=from_dt,
        to_dt=to_dt,
        client=http_client,
    )
    tz_name = await daily_service.branch_timezone(session, branch_id)
    events = rows_to_events(rows, tz_name, _allowed_serials())

    result = await ingest_punches(session, events, branch_id)
    rebuilt = await daily_service.rebuild_after_ingest(
        session,
        branch_id=branch_id,
        affected=[(a.student_id, a.punch_timestamp) for a in result.affected],
        tz_name=tz_name,
    )
    return {
        "rows": len(rows),
        "events": len(events),
        "inserted": result.inserted,
        "skipped_no_student": result.skipped_no_student,
        "skipped_duplicate": result.skipped_duplicate,
        "days_rebuilt": rebuilt,
        "from_date": from_date.isoformat(),
        "to_date": to_date.isoformat(),
    }


async def sync_recent(session: AsyncSession, *, branch_id: uuid.UUID) -> dict[str, Any]:
    """Poll the lookback window up to today (what the scheduled job calls)."""
    settings = get_settings()
    today = datetime.now(timezone.utc).astimezone(
        get_tz(await daily_service.branch_timezone(session, branch_id))
    ).date()
    start = today - timedelta(days=max(0, settings.SMARTOFFICE_LOOKBACK_DAYS))
    return await sync_range(session, branch_id=branch_id, from_date=start, to_date=today)
