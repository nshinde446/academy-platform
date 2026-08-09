"""BioMax device-user sync — read the terminal's REAL user table and push it to
the portal as ground truth (run on-site, on the institute LAN).

Why
---
The portal only learns who is enrolled on the device from the device's *one-time*
``realtime_enroll_data`` push, sent the moment a face is enrolled. Anyone enrolled
before we were listening (or during any downtime) is invisible to the portal, so
they show forever as "awaiting face" even though their face is on the device — and
newly enrolled faces don't reflect back. This tool fixes that at the source: it
reads the device's own user table and tells the portal exactly who's there.

How
---
The R6 exposes a local HTTP API on port 80 (``lighttpd``, HTTP Digest, default
``admin`` / ``admin``): ``POST /bin/cmd`` with ``{"cmd":..,"data":..}`` returns
``{"result_code":0,"result_data":{"packageId":N,"users":[..]}}``. ``packageId`` is
a continuation token — keep calling until it comes back ``0``.

1. ``GetUserIdList`` (paged) → every ``userId`` on the device.
2. ``GetUserInfo`` for those ids (batched + paged) → name, validity, and whether a
   FACE template exists (the ``face`` field is present/non-null).
3. POST the snapshot (identity + ``has_face`` only — NEVER the biometric blob) to
   the portal's ``/attendance/provisioning/device-users/sync``, authenticated by a
   shared token, which rebuilds the mirror.

The device must be reachable on the LAN this machine is on. Only reads the device
(no writes to it) and sends the portal no biometric data — just presence.

Run it (Windows / any Python 3.9+, stdlib only — no pip installs)
-----------------------------------------------------------------
    set DEVICE_HOST=192.168.1.8
    set BIOMAX_SYNC_TOKEN=<the same secret set on the server>
    python device_user_sync.py

Env vars (all optional except the token):
    DEVICE_HOST        device LAN IP/host  (default: AUTO-DISCOVER on the /24)
    DEVICE_PORT        device HTTP port            (default 80)
    DEVICE_USER        local-API user              (default admin)
    DEVICE_PASS        local-API password          (default admin)
    DEV_ID             device Cloud ID / serial    (default AMDB26013800122)
    PORTAL_BASE_URL    portal base                 (default https://app.eduworld-livekit.duckdns.org)
    BIOMAX_SYNC_TOKEN  shared secret (REQUIRED)
    BATCH_SIZE         userIds per GetUserInfo call (default 50)
    DRY_RUN            "1" to print counts and skip the portal POST

Schedule it (so nobody runs it by hand): Windows Task Scheduler, e.g. daily —
    schtasks /Create /SC DAILY /TN BioMaxUserSync /TR "python C:/path/device_user_sync.py" /ST 21:00
"""

from __future__ import annotations

import concurrent.futures
import json
import os
import socket
import sys
import urllib.error
import urllib.request

# ── config ────────────────────────────────────────────────────────────────────
# DEVICE_HOST empty => auto-discover the terminal on the LAN (its DHCP IP changes
# between networks — .8 at one site, .14 at another — so a hardcoded IP breaks a
# scheduled run; discovery makes it self-locating).
DEVICE_HOST = os.environ.get("DEVICE_HOST", "")
DEVICE_PORT = os.environ.get("DEVICE_PORT", "80")
DEVICE_USER = os.environ.get("DEVICE_USER", "admin")
DEVICE_PASS = os.environ.get("DEVICE_PASS", "admin")
DEV_ID = os.environ.get("DEV_ID", "AMDB26013800122")
PORTAL_BASE_URL = os.environ.get(
    "PORTAL_BASE_URL", "https://app.eduworld-livekit.duckdns.org"
).rstrip("/")
SYNC_TOKEN = os.environ.get("BIOMAX_SYNC_TOKEN", "")
BATCH_SIZE = int(os.environ.get("BATCH_SIZE", "50"))
DRY_RUN = os.environ.get("DRY_RUN", "") == "1"

# Resolved once the device is located (env host or discovery); functions read it.
DEVICE_BASE = ""
# The presence of ANY of these on a GetUserInfo record means a biometric template
# exists. We record only THAT it exists; the blob itself is never read out or sent.
FACE_KEYS = ("face", "fps", "palm")


def _base(host: str) -> str:
    return f"http://{host}:{DEVICE_PORT}"


def _is_biomax(host: str) -> bool:
    """True iff ``host`` is the BioMax terminal — its ``/bin/cmd`` answers with a
    lighttpd HTTP-Digest challenge (``realm="Login"``). Cheap fingerprint that
    won't false-match a random web server or the SmartOffice/IIS box."""
    try:
        req = urllib.request.Request(
            f"{_base(host)}/bin/cmd",
            data=b"{}",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=2)
    except urllib.error.HTTPError as exc:
        auth = exc.headers.get("WWW-Authenticate", "") or ""
        server = exc.headers.get("Server", "") or ""
        return exc.code == 401 and "Digest" in auth and "lighttpd" in server.lower()
    except Exception:
        return False
    return False


def _local_subnet() -> str | None:
    """This machine's private /24 base (e.g. '192.168.1'), via the default route."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        return None
    finally:
        s.close()
    parts = ip.split(".")
    return ".".join(parts[:3]) if len(parts) == 4 else None


def discover_device() -> str | None:
    """Find the terminal on the local /24: probe port 80 in parallel, then confirm
    each open host is the BioMax by its Digest fingerprint. Returns the IP or None."""
    base3 = _local_subnet()
    if not base3:
        return None

    def open80(i: int) -> str | None:
        host = f"{base3}.{i}"
        try:
            with socket.create_connection((host, 80), timeout=0.4):
                return host
        except Exception:
            return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=64) as ex:
        candidates = [h for h in ex.map(open80, range(1, 255)) if h]
    for host in candidates:
        if _is_biomax(host):
            return host
    return None


def _device_opener() -> urllib.request.OpenerDirector:
    """An HTTP opener that answers the device's Digest auth challenge."""
    mgr = urllib.request.HTTPPasswordMgrWithDefaultRealm()
    mgr.add_password(None, DEVICE_BASE, DEVICE_USER, DEVICE_PASS)
    return urllib.request.build_opener(urllib.request.HTTPDigestAuthHandler(mgr))


def _cmd(opener: urllib.request.OpenerDirector, cmd: str, data: dict) -> dict:
    """POST one ``/bin/cmd`` and return ``result_data`` (raises on device error)."""
    body = json.dumps({"cmd": cmd, "data": data}).encode("utf-8")
    req = urllib.request.Request(
        f"{DEVICE_BASE}/bin/cmd",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with opener.open(req, timeout=30) as resp:
        parsed = json.loads(resp.read().decode("utf-8", errors="replace"))
    if parsed.get("result_code") != 0:
        raise RuntimeError(f"device {cmd} failed: result_code={parsed.get('result_code')}")
    return parsed.get("result_data") or {}


def fetch_user_ids(opener) -> list[str]:
    """Page GetUserIdList until packageId comes back 0; return every userId."""
    ids: list[str] = []
    package_id = 0
    while True:
        rd = _cmd(opener, "GetUserIdList", {"packageId": package_id})
        for u in rd.get("users") or []:
            uid = str(u.get("userId") or "").strip()
            if uid:
                ids.append(uid)
        package_id = rd.get("packageId") or 0
        if package_id == 0:
            break
    return ids


def fetch_user_info(opener, ids: list[str]) -> list[dict]:
    """GetUserInfo for a list of ids, batched and paged. Extracts identity +
    ``has_face`` only — biometric blobs are dropped immediately, never returned."""
    rows: list[dict] = []
    for start in range(0, len(ids), BATCH_SIZE):
        batch = ids[start : start + BATCH_SIZE]
        package_id = 0
        while True:
            rd = _cmd(
                opener, "GetUserInfo", {"packageId": package_id, "usersId": batch}
            )
            for u in rd.get("users") or []:
                uid = str(u.get("userId") or "").strip()
                if not uid:
                    continue
                has_face = any(u.get(k) not in (None, "") for k in FACE_KEYS)
                rows.append(
                    {
                        "vendor_user_id": uid,
                        "name": (str(u.get("name") or "").strip() or None),
                        "privilege": int(u.get("privilege") or 0),
                        "has_face": has_face,
                        "valid_start": _digits(u.get("vaildStart") or u.get("validStart")),
                        "valid_end": _digits(u.get("vaildEnd") or u.get("validEnd")),
                    }
                )
            package_id = rd.get("packageId") or 0
            if package_id == 0:
                break
    return rows


def _digits(value: object) -> str | None:
    s = str(value or "").strip()
    return s if s.isdigit() else None


def post_snapshot(rows: list[dict]) -> dict:
    """POST the snapshot to the portal (token-authenticated)."""
    body = json.dumps({"dev_id": DEV_ID, "users": rows}).encode("utf-8")
    req = urllib.request.Request(
        f"{PORTAL_BASE_URL}/api/v1/attendance/provisioning/device-users/sync",
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-BioMax-Sync-Token": SYNC_TOKEN,
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def resolve_device_host() -> str | None:
    """Pick the terminal's address: the configured DEVICE_HOST if it really is the
    terminal, otherwise auto-discover it on the LAN (its IP changes per network)."""
    if DEVICE_HOST:
        if _is_biomax(DEVICE_HOST):
            return DEVICE_HOST
        print(f"DEVICE_HOST {DEVICE_HOST} isn't answering as the terminal — discovering…")
    else:
        print("No DEVICE_HOST set — discovering the terminal on the LAN…")
    host = discover_device()
    if host:
        print(f"  found terminal at {host}")
    return host


def main() -> int:
    global DEVICE_BASE
    if not SYNC_TOKEN and not DRY_RUN:
        print("ERROR: set BIOMAX_SYNC_TOKEN (the shared secret configured on the server).")
        return 2
    host = resolve_device_host()
    if not host:
        print("ERROR: could not find the BioMax terminal on this network.")
        print("Is this machine on the SAME LAN as the terminal (no Wi-Fi client isolation)?")
        return 1
    DEVICE_BASE = _base(host)
    print(f"Reading device {DEV_ID} at {DEVICE_BASE} …")
    opener = _device_opener()
    try:
        ids = fetch_user_ids(opener)
        print(f"  {len(ids)} user ids on device")
        rows = fetch_user_info(opener, ids)
    except urllib.error.URLError as exc:
        print(f"ERROR: cannot reach the device at {DEVICE_BASE}: {exc}")
        print("Is this machine on the same LAN as the terminal? Is the IP/port right?")
        return 1
    with_face = sum(1 for r in rows if r["has_face"])
    print(f"  {len(rows)} users read · {with_face} with a face · {len(rows) - with_face} identity-only")

    if DRY_RUN:
        print("DRY_RUN=1 — not posting to the portal.")
        return 0
    try:
        result = post_snapshot(rows)
    except urllib.error.HTTPError as exc:
        print(f"ERROR: portal rejected the snapshot: HTTP {exc.code} {exc.read().decode('utf-8', 'replace')}")
        return 1
    except urllib.error.URLError as exc:
        print(f"ERROR: cannot reach the portal at {PORTAL_BASE_URL}: {exc}")
        return 1
    print(
        f"Synced: upserted={result.get('upserted')} removed={result.get('removed')} "
        f"total={result.get('total')}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
