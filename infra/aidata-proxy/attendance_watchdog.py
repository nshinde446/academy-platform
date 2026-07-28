"""Attendance liveness watchdog — alert when the BioMax device goes silent.

Why this exists
---------------
With the coaching laptop out of the loop, the biometric device pushes straight
to the VPS. That's resilient, but it fails *silently*: if the device is
unplugged, the institute's internet drops, or the proxy dies, punches simply
stop and nobody notices until someone checks attendance days later. This closes
that gap — it turns silent failure into a message on your phone within minutes.

How it decides
--------------
`aidata_proxy.py` bumps a heartbeat file's mtime on **every** device contact.
The device polls every ~20s even when nobody punches, so a stale heartbeat is a
true "device/internet/proxy is down" signal — far better than "no punches",
which is normal during quiet periods.

State machine (so you get one alert, not a flood):
  UP  -> stale during working hours          => send DOWN alert,  state=DOWN
  DOWN-> healthy again                        => send RECOVERED,   state=UP
  DOWN-> still stale, REPEAT_SECONDS elapsed  => send a reminder

Outside working hours we don't alert (the device may be legitimately powered
off overnight); if it's still down when hours start, the first in-hours run
alerts.

Delivery
--------
Telegram (set TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID) and/or a generic webhook
(ALERT_WEBHOOK_URL, receives JSON). With neither set it only logs, so it's safe
to dry-run. No secrets are hardcoded.

Run it from cron every few minutes, e.g.:
    */3 * * * * /usr/bin/python3 /srv/academy/repo/infra/aidata-proxy/attendance_watchdog.py >> /var/log/attendance_watchdog.log 2>&1
"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

try:
    from zoneinfo import ZoneInfo
    _TZ = ZoneInfo(os.environ.get("WATCHDOG_TZ", "Asia/Kolkata"))
except Exception:  # zoneinfo/tzdata missing — fall back to fixed IST offset
    from datetime import timedelta
    _TZ = timezone(timedelta(hours=5, minutes=30))

HEARTBEAT_FILE = os.environ.get("AIDATA_HEARTBEAT_FILE", "/srv/academy/aidata/heartbeat")
STATE_FILE = os.environ.get("WATCHDOG_STATE_FILE", "/srv/academy/aidata/watchdog_state.json")
# How long without a device contact counts as "down". The device polls ~20s, so
# 5 min tolerates a few missed polls / a brief blip without crying wolf.
STALE_AFTER = int(os.environ.get("WATCHDOG_STALE_SECONDS", "300"))
# Only alert during working hours (local time), to avoid overnight false alarms.
WORK_START = int(os.environ.get("WATCHDOG_WORK_START_HOUR", "7"))   # 07:00
WORK_END = int(os.environ.get("WATCHDOG_WORK_END_HOUR", "22"))      # 22:00
# While still down, re-remind at most this often.
REPEAT_SECONDS = int(os.environ.get("WATCHDOG_REPEAT_SECONDS", str(2 * 3600)))

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN") or None
TELEGRAM_CHAT = os.environ.get("TELEGRAM_CHAT_ID") or None
WEBHOOK_URL = os.environ.get("ALERT_WEBHOOK_URL") or None
LABEL = os.environ.get("WATCHDOG_LABEL", "BioMax attendance")

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s watchdog %(message)s")
log = logging.getLogger("watchdog")


def _heartbeat_age() -> float | None:
    """Seconds since the last device contact, or None if the file is missing
    (never contacted / proxy never started) — treated as down."""
    try:
        return max(0.0, time.time() - os.path.getmtime(HEARTBEAT_FILE))
    except OSError:
        return None


def _load_state() -> dict:
    try:
        with open(STATE_FILE, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {"status": "UP", "last_alert_ts": 0}


def _save_state(state: dict) -> None:
    try:
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        with open(STATE_FILE, "w", encoding="utf-8") as fh:
            json.dump(state, fh)
    except OSError as exc:
        log.error("could not persist state: %s", exc)


def _within_working_hours(now_local: datetime) -> bool:
    return WORK_START <= now_local.hour < WORK_END


def _send_telegram(text: str) -> bool:
    if not (TELEGRAM_TOKEN and TELEGRAM_CHAT):
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = json.dumps({"chat_id": TELEGRAM_CHAT, "text": text}).encode()
    req = urllib.request.Request(url, data=data,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return 200 <= resp.status < 300
    except (urllib.error.URLError, OSError) as exc:
        log.error("telegram send failed: %s", exc)
        return False


def _send_webhook(payload: dict) -> bool:
    if not WEBHOOK_URL:
        return False
    req = urllib.request.Request(WEBHOOK_URL, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return 200 <= resp.status < 300
    except (urllib.error.URLError, OSError) as exc:
        log.error("webhook send failed: %s", exc)
        return False


def _alert(kind: str, text: str, extra: dict) -> None:
    """Fan out to every configured channel; always log so a dry-run is visible."""
    log.warning("ALERT[%s] %s", kind, text)
    delivered = False
    delivered |= _send_telegram(f"{LABEL}: {text}")
    delivered |= _send_webhook({"event": kind, "label": LABEL, "text": text, **extra})
    if not (TELEGRAM_TOKEN or WEBHOOK_URL):
        log.info("(no alert channel configured — logged only)")
    elif not delivered:
        log.error("alert had channels configured but NONE delivered")


def main() -> None:
    now = time.time()
    now_local = datetime.now(_TZ)
    age = _heartbeat_age()
    state = _load_state()
    status = state.get("status", "UP")
    last_alert = float(state.get("last_alert_ts", 0))

    healthy = age is not None and age <= STALE_AFTER
    age_str = "never" if age is None else f"{int(age)}s ago"
    log.info("heartbeat %s | status=%s | working_hours=%s",
             age_str, status, _within_working_hours(now_local))

    if healthy:
        if status == "DOWN":
            _alert("recovered",
                   f"attendance is back ONLINE (last contact {age_str}).",
                   {"age_seconds": age})
        _save_state({"status": "UP", "last_alert_ts": 0})
        return

    # Stale. Only escalate during working hours to avoid overnight false alarms.
    if not _within_working_hours(now_local):
        # Record DOWN silently so the first in-hours run alerts, but don't ping.
        _save_state({"status": "DOWN", "last_alert_ts": last_alert})
        log.info("stale but outside working hours — holding alert")
        return

    ts = "no contact on record" if age is None else f"last contact {age_str}"
    is_new = status != "DOWN"
    should_remind = (now - last_alert) >= REPEAT_SECONDS
    if is_new or should_remind:
        _alert("down",
               f"NO attendance data — device/internet/proxy may be down "
               f"({ts}, threshold {STALE_AFTER}s). Check the terminal & network.",
               {"age_seconds": age})
        _save_state({"status": "DOWN", "last_alert_ts": now})
    else:
        _save_state({"status": "DOWN", "last_alert_ts": last_alert})


if __name__ == "__main__":
    main()
