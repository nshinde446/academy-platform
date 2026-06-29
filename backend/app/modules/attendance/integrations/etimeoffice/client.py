"""eTimeOffice / TeamOffice cloud REST client.

eTimeOffice is a hosted SaaS — the punches live in *their* cloud, so we PULL
on a schedule rather than receiving a push. This module is the thin HTTP layer:
it knows the endpoint, the auth header, and the date format, and returns the
raw punch rows. Mapping those rows onto our domain (Student, RawPunchLog) is
``service.py``'s job.

Auth: the TeamOffice Web API authenticates with the corporate account's
``CorporateID``, an API ``Username`` and ``Password``. They are sent as a
colon-joined ``Authorization`` header value. The exact tail segment
(``APIType``) and field casing can vary by the client's API-panel version, so
everything that might differ is a constant near the top — verify against the
client's actual panel and adjust here only.

Reference endpoint (punch download, by date range + employee code):
    GET {base}/DownloadInOutPunchData?Empcode=ALL&FromDate=DD/MM/YYYY&ToDate=DD/MM/YYYY
Response (JSON):
    {"InOutPunchData": [ {"Empcode": "...", "INTime": "...", "OUTTime": "...",
                          "DateString": "...", "Status": "P"} , ...],
     "Error": false, "Msg": null}
"""

from __future__ import annotations

from datetime import date
from typing import Any

import httpx

# eTimeOffice expects dd/MM/yyyy in the query string.
ETO_DATE_FMT = "%d/%m/%Y"
# Endpoint path appended to the configured base URL.
PUNCH_PATH = "/DownloadInOutPunchData"
# Key under which the rows arrive in the JSON body.
PUNCH_DATA_KEY = "InOutPunchData"


class ETimeOfficeError(RuntimeError):
    """Raised when the API returns an error envelope or a bad HTTP status."""


def build_auth_header(corp_id: str, username: str, password: str) -> str:
    """The colon-joined credential string TeamOffice expects in Authorization.

    Isolated so the one place that might need tweaking per API-panel version is
    obvious (some panels append an APIType segment)."""
    return f"{corp_id}:{username}:{password}"


async def fetch_punch_data(
    *,
    base_url: str,
    corp_id: str,
    username: str,
    password: str,
    from_date: date,
    to_date: date,
    empcode: str = "ALL",
    timeout: float = 30.0,
    client: httpx.AsyncClient | None = None,
) -> list[dict[str, Any]]:
    """Pull raw InOut punch rows for a date range. Returns the row dicts as-is.

    ``client`` is injectable so tests drive this without a live API. The error
    envelope (``Error: true``) is raised as ``ETimeOfficeError``."""
    params = {
        "Empcode": empcode,
        "FromDate": from_date.strftime(ETO_DATE_FMT),
        "ToDate": to_date.strftime(ETO_DATE_FMT),
    }
    headers = {"Authorization": build_auth_header(corp_id, username, password)}
    url = f"{base_url.rstrip('/')}{PUNCH_PATH}"

    owns_client = client is None
    client = client or httpx.AsyncClient(timeout=timeout)
    try:
        resp = await client.get(url, params=params, headers=headers)
    finally:
        if owns_client:
            await client.aclose()

    if resp.status_code != 200:
        raise ETimeOfficeError(
            f"eTimeOffice returned HTTP {resp.status_code}: {resp.text[:200]}"
        )

    body = resp.json()
    # Their envelope flags errors in-band even on HTTP 200.
    if isinstance(body, dict) and body.get("Error"):
        raise ETimeOfficeError(f"eTimeOffice error: {body.get('Msg') or body}")

    rows = body.get(PUNCH_DATA_KEY) if isinstance(body, dict) else body
    return rows or []
