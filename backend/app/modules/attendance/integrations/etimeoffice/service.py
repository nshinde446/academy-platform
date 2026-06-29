"""eTimeOffice → domain sync.

Pulls punch rows from the eTimeOffice cloud (``client.py``), maps each row's
IN/OUT times onto our vendor-agnostic ``PunchEvent``, and funnels them through
the *same* ``ingest_punches`` + ``rebuild_after_ingest`` path every other feeder
uses. eTimeOffice reports times in the branch's local wall-clock; we convert to
tz-aware UTC before storing (RawPunchLog is UTC).

The employee identifier (``Empcode``) is matched to ``Student.rfid_number`` —
the same join BioMax uses — so enrolling a device user = setting that student's
rfid_number to the eTimeOffice Empcode.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config.settings import get_settings
from app.modules.attendance.integrations.biomax.schemas import PunchEvent
from app.modules.attendance.integrations.biomax.service import ingest_punches
from app.modules.attendance.integrations.etimeoffice import client as eto_client
from app.modules.attendance.services import daily_service
from app.modules.attendance.time_utils import get_tz

# eTimeOffice splits a punch into a date column + separate IN/OUT time columns.
# Times may arrive bare ("10:05"), with seconds, or as a full datetime; dates in
# a few common shapes. Parse defensively — a row we can't read is skipped, not
# fatal.
_DATE_FORMATS = ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d-%b-%Y", "%d/%m/%y")
_TIME_FORMATS = ("%H:%M:%S", "%H:%M")
# Sentinels eTimeOffice uses for "no punch" in a slot.
_EMPTY_TIMES = {"", "--:--", "00:00", "0:00", "none", "null"}

DEVICE_ID = "etimeoffice"


def _get(row: dict[str, Any], *keys: str) -> str:
    """First non-empty value among case-tolerant keys."""
    lowered = {k.lower(): v for k, v in row.items()}
    for k in keys:
        v = lowered.get(k.lower())
        if v not in (None, ""):
            return str(v).strip()
    return ""


def _parse_local(date_str: str, time_str: str, tz_name: str | None) -> datetime | None:
    """Combine a date + time string into a tz-aware UTC instant, or None.

    eTimeOffice times are branch-local; we attach the branch zone then convert
    to UTC. If the time field already carries a date (full datetime), the
    date_str is ignored."""
    t = time_str.strip().lower()
    if t in _EMPTY_TIMES:
        return None

    naive: datetime | None = None
    # Full datetime in the time field?
    for df in _DATE_FORMATS:
        for tf in _TIME_FORMATS:
            try:
                naive = datetime.strptime(time_str.strip(), f"{df} {tf}")
                break
            except ValueError:
                continue
        if naive:
            break

    if naive is None:
        # Bare time — combine with the row's date column.
        parsed_date: date | None = None
        for df in _DATE_FORMATS:
            try:
                parsed_date = datetime.strptime(date_str.strip(), df).date()
                break
            except ValueError:
                continue
        if parsed_date is None:
            return None
        for tf in _TIME_FORMATS:
            try:
                tt = datetime.strptime(time_str.strip(), tf).time()
                naive = datetime.combine(parsed_date, tt)
                break
            except ValueError:
                continue

    if naive is None:
        return None
    local = naive.replace(tzinfo=get_tz(tz_name))
    return local.astimezone(timezone.utc)


def rows_to_events(rows: list[dict[str, Any]], tz_name: str | None) -> list[PunchEvent]:
    """Map eTimeOffice rows → PunchEvents (one each for a present IN and OUT)."""
    events: list[PunchEvent] = []
    for row in rows:
        empcode = _get(row, "Empcode", "EmpCode", "EmployeeCode", "PIN")
        if not empcode:
            continue
        date_str = _get(row, "DateString", "Date", "AttDate", "PunchDate")
        in_dt = _parse_local(date_str, _get(row, "INTime", "InTime", "In"), tz_name)
        out_dt = _parse_local(date_str, _get(row, "OUTTime", "OutTime", "Out"), tz_name)

        if in_dt is not None:
            events.append(PunchEvent(
                vendor_user_id=empcode, punch_timestamp=in_dt,
                direction="IN", device_id=DEVICE_ID,
            ))
        if out_dt is not None:
            events.append(PunchEvent(
                vendor_user_id=empcode, punch_timestamp=out_dt,
                direction="OUT", device_id=DEVICE_ID,
            ))
    return events


async def sync_range(
    session: AsyncSession,
    *,
    branch_id: uuid.UUID,
    from_date: date,
    to_date: date,
    http_client=None,
) -> dict[str, Any]:
    """Pull + ingest punches for a date range. Returns a summary dict.

    Raises if the API call fails (caller decides whether to swallow). Ingest is
    idempotent (5s dedup), so overlapping ranges across polls are safe."""
    settings = get_settings()
    rows = await eto_client.fetch_punch_data(
        base_url=settings.ETO_BASE_URL,
        corp_id=settings.ETO_CORP_ID,
        username=settings.ETO_USERNAME,
        password=settings.ETO_PASSWORD,
        from_date=from_date,
        to_date=to_date,
        client=http_client,
    )
    tz_name = await daily_service.branch_timezone(session, branch_id)
    events = rows_to_events(rows, tz_name)

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
    start = today - timedelta(days=max(0, settings.ETO_LOOKBACK_DAYS))
    return await sync_range(session, branch_id=branch_id, from_date=start, to_date=today)
