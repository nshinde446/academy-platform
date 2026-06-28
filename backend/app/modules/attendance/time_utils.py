"""Branch-local day helpers for biometric day-attendance.

All day-bucketing (which calendar day a punch belongs to, the on-time cutoff,
the campus window, the nightly sweep boundary) must be computed in the branch's
*local* time, then stored as tz-aware UTC instants. A 09:29 IST punch is 04:00
UTC — bucketing in UTC would push boundary punches to the wrong day.

See docs/biometric-attendance-design.md §2.3.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from zoneinfo import ZoneInfo

from app.core.config.settings import get_settings


@lru_cache(maxsize=64)
def get_tz(tz_name: str | None) -> ZoneInfo:
    """Resolve an IANA name to a ZoneInfo, falling back to the configured
    default for empty/unknown names so callers never crash on bad branch data."""
    settings = get_settings()
    name = tz_name or settings.DEFAULT_TIMEZONE
    try:
        return ZoneInfo(name)
    except Exception:  # noqa: BLE001 — unknown zone -> safe default
        return ZoneInfo(settings.DEFAULT_TIMEZONE)


def _as_utc(instant: datetime) -> datetime:
    """Treat a naive datetime as UTC (SQLite drops tzinfo); pass through aware."""
    if instant.tzinfo is None:
        return instant.replace(tzinfo=timezone.utc)
    return instant


def local_date_of(instant: datetime, tz_name: str | None) -> date:
    """The branch-local calendar date an instant falls on."""
    return _as_utc(instant).astimezone(get_tz(tz_name)).date()


def day_bounds(day: date, tz_name: str | None) -> tuple[datetime, datetime]:
    """UTC half-open interval [00:00, next-00:00) of a local calendar day.

    Use to query punches belonging to ``day`` in the branch tz.
    """
    tz = get_tz(tz_name)
    start_local = datetime(day.year, day.month, day.day, 0, 0, 0, tzinfo=tz)
    end_local = start_local + timedelta(days=1)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


def local_time_on(
    day: date, tz_name: str | None, hour: int, minute: int = 0
) -> datetime:
    """UTC instant for a local wall-clock time on a given local date.

    Used for the on-time cutoff (10:10), campus open/close (07:00/15:00), and
    the nightly-sweep boundary — all expressed in branch-local wall-clock.
    """
    tz = get_tz(tz_name)
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=tz).astimezone(
        timezone.utc
    )


def class_start_on(day: date, tz_name: str | None) -> datetime:
    """On-time cutoff base = local class start (default 10:00) for ``day``."""
    settings = get_settings()
    return local_time_on(
        day, tz_name,
        settings.ATTENDANCE_CLASS_START_HOUR,
        settings.ATTENDANCE_CLASS_START_MINUTE,
    )


def campus_window_on(day: date, tz_name: str | None) -> tuple[datetime, datetime]:
    """UTC [open, close) for the local campus window (default 07:00–15:00)."""
    settings = get_settings()
    return (
        local_time_on(day, tz_name, settings.ATTENDANCE_CAMPUS_OPEN_HOUR),
        local_time_on(day, tz_name, settings.ATTENDANCE_CAMPUS_CLOSE_HOUR),
    )
