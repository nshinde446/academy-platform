"""SmartOffice (SmartOfficePayroll) cloud REST client.

SmartOffice is an on-prem/cloud middleware that sits between the physical
ZKTeco-based biometric devices and us: the devices push their punches to the
SmartOffice server, and we PULL the aggregated logs from its REST API. There is
no webhook-to-our-URL in the SmartOffice API, so — like eTimeOffice — this is a
polled integration. This module is the thin HTTP layer; mapping the rows onto
our domain (Student, RawPunchLog) is ``service.py``'s job.

Auth: a single ``APIKey`` query parameter issued from the SmartOffice web app.

Reference endpoint (punch logs, by datetime range), per the vendor's
"Smart Office API Documentation" v1.0.4, section "Fetch Biometric Logs Data":
    GET {base}/api/v2/WebAPI/GetDeviceLogs?APIKey=..&FromDate=..&ToDate=..
Response (JSON array):
    [ {"EmployeeCode": "5", "LogDate": "2019-09-16 13:45:29",
       "SerialNumber": "C2689C47030A2334", "PunchDirection": "in",
       "Temperature": 97.4, "TemperatureState": "Normal"}, ... ]
Error envelope (still HTTP 200):
    {"status": false, "message": "Invalid API Key."}

The exact date format the API expects in the query string can vary by the
client's SmartOffice version, so it is isolated as ``SMARTOFFICE_DATE_FMT`` —
verify against the client's panel and adjust only here.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

import httpx

# SmartOffice's own log rows are "yyyy-MM-dd HH:mm:ss"; the range query accepts
# the same shape (its ClearLogsFromDeviceByTime example uses "yyyy-MM-dd HH:mm").
SMARTOFFICE_DATE_FMT = "%Y-%m-%d %H:%M:%S"
# Endpoint path appended to the configured base URL.
LOGS_PATH = "/api/v2/WebAPI/GetDeviceLogs"


class SmartOfficeError(RuntimeError):
    """Raised when the API returns an error envelope or a bad HTTP status."""


async def fetch_device_logs(
    *,
    base_url: str,
    api_key: str,
    from_dt: datetime,
    to_dt: datetime,
    timeout: float = 30.0,
    client: httpx.AsyncClient | None = None,
) -> list[dict[str, Any]]:
    """Pull raw biometric log rows for a datetime range. Returns the row dicts
    as-is (``EmployeeCode`` / ``LogDate`` / ``SerialNumber`` / ``PunchDirection``).

    ``client`` is injectable so tests drive this without a live API. The error
    envelope (``status: false``) is raised as ``SmartOfficeError``."""
    params = {
        "APIKey": api_key,
        "FromDate": from_dt.strftime(SMARTOFFICE_DATE_FMT),
        "ToDate": to_dt.strftime(SMARTOFFICE_DATE_FMT),
    }
    url = f"{base_url.rstrip('/')}{LOGS_PATH}"

    owns_client = client is None
    client = client or httpx.AsyncClient(timeout=timeout)
    try:
        resp = await client.get(url, params=params)
    finally:
        if owns_client:
            await client.aclose()

    if resp.status_code != 200:
        raise SmartOfficeError(
            f"SmartOffice returned HTTP {resp.status_code}: {resp.text[:200]}"
        )

    body = resp.json()
    # SmartOffice flags errors in-band even on HTTP 200: {"status": false, ...}.
    if isinstance(body, dict):
        if body.get("status") is False or body.get("result") is False:
            raise SmartOfficeError(
                f"SmartOffice error: {body.get('message') or body}"
            )
        # A few builds wrap the array under a "records"/"data" key.
        rows = body.get("records") or body.get("data") or []
        return rows if isinstance(rows, list) else []
    return body or []


def parse_log_datetime(value: str) -> datetime | None:
    """Parse a SmartOffice ``LogDate`` string to a naive (branch-local) datetime,
    or None. Tolerates a missing seconds component."""
    s = (value or "").strip()
    if not s:
        return None
    for fmt in (SMARTOFFICE_DATE_FMT, "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def day_bounds(from_date: date, to_date: date) -> tuple[datetime, datetime]:
    """Full-day [00:00:00, 23:59:59] datetime bounds for an inclusive date range."""
    return (
        datetime.combine(from_date, datetime.min.time()),
        datetime.combine(to_date, datetime.max.time()).replace(microsecond=0),
    )
