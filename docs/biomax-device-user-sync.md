# BioMax device-user sync — ground truth from the terminal

## Why this exists

The portal learns who is enrolled on the BioMax terminal only from the device's
**one-time** `realtime_enroll_data` push, sent at the instant a face is enrolled.
Anyone enrolled before we were listening (or during any downtime) is invisible to
the portal, so they show forever as **"awaiting face"** on the Device-sync screen
even though their face is on the device — and freshly enrolled faces don't reflect
back either.

This sync reads the device's **actual** user table and makes it the source of
truth, so reconcile's "awaiting face" and "name drift" reflect reality instead of
what we happened to catch.

## How it works

```
on-site machine (same LAN as the terminal)
  └─ device_user_sync.py
        ├─ POST /bin/cmd  GetUserIdList   (paged) → every userId on the device
        ├─ POST /bin/cmd  GetUserInfo     (paged) → name, validity, has_face
        └─ POST  /api/v1/attendance/provisioning/device-users/sync   (token auth)
                 → rebuilds the device_users mirror (full replace)
```

- The terminal's local API is `POST /bin/cmd`, HTTP Digest (`admin`/`admin`),
  envelope `{"result_code":0,"result_data":{"packageId":N,"users":[…]}}`;
  `packageId` is a continuation token — page until it returns `0`.
- `has_face` = the `GetUserInfo` record carries a `face`/`fps`/`palm` template.
  **Only the boolean is sent to the portal — never the biometric blob.**
- Full-replace semantics: a user the device no longer holds is dropped from the
  mirror.

Reconcile then classifies each student as:
- **enrolled** (has a face on the device, or has ever punched) → matched, or
  *name drift* if the device name differs;
- **awaiting face** (identity on the device / confirmed push, but no face yet);
- **need pushing** (no identity on the device at all).

## Setup

1. **Server** — set a shared secret and redeploy (code-only otherwise):
   ```
   BIOMAX_SYNC_TOKEN=<long random string>
   ```
   Unset = the sync endpoint returns 503 (fail-safe).

2. **On-site machine** (the institute PC on the same LAN as the terminal) — run
   `infra/aidata-proxy/device_user_sync.py` with Python 3.9+ (stdlib only, no
   pip installs):
   ```
   set DEVICE_HOST=192.168.1.8            # the terminal's LAN IP
   set BIOMAX_SYNC_TOKEN=<same secret as the server>
   python device_user_sync.py
   ```
   Add `set DRY_RUN=1` first to read the device and print counts without touching
   the portal.

3. **Schedule it** so nobody runs it by hand (daily is plenty — it's not in the
   punch path):
   ```
   schtasks /Create /SC DAILY /TN BioMaxUserSync ^
     /TR "python C:/path/device_user_sync.py" /ST 21:00
   ```

## Notes / limits

- The on-site machine must be **on the LAN and powered on** when the task runs.
  It's a periodic refresh, not real-time — the punch path is unaffected either
  way.
- Env vars: `DEVICE_HOST/PORT/USER/PASS`, `DEV_ID`, `PORTAL_BASE_URL`,
  `BIOMAX_SYNC_TOKEN`, `BATCH_SIZE`, `DRY_RUN`. Defaults match the current prod
  device (`AMDB26013800122`).
- A later, fully-cloud variant can pull the same table over the `receive_cmd`
  channel (no on-site machine), once its `GET_USER_INFO` response format is
  captured on-device. This local-API agent is the reliable path today.
