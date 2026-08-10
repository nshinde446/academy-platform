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

2. **On the integration machine** (same LAN as the terminal) — run
   `infra/aidata-proxy/device_user_sync.py` with Python 3.9+ (stdlib only, no
   pip installs). **It auto-discovers the terminal** on the local /24 (probes
   port 80, confirms the lighttpd Digest fingerprint), so you don't hardcode an
   IP — the terminal's DHCP address changes between networks:
   ```
   set BIOMAX_SYNC_TOKEN=<same secret as the server>
   set DRY_RUN=1                          & REM read + print counts, no write
   python device_user_sync.py
   ```
   Set `DEVICE_HOST=<ip>` only to skip discovery (faster) when you know the IP.

3. **Schedule it** so nobody runs it by hand (daily is plenty — it's not in the
   punch path). Keep the token in a small wrapper `.bat` OUTSIDE the repo and
   point a task at it:
   ```bat
   REM C:\biomax-sync\run_sync.bat
   set BIOMAX_SYNC_TOKEN=<secret>
   "<repo>\backend\.venv\Scripts\python.exe" "<repo>\infra\aidata-proxy\device_user_sync.py" >> "%~dp0sync.log" 2>&1
   ```
   ```
   schtasks /Create /SC DAILY /TN BioMaxUserSync /TR "C:\biomax-sync\run_sync.bat" /ST 21:00 /F
   ```

## Notes / limits

- The on-site machine must be **on the LAN and powered on** when the task runs.
  It's a periodic refresh, not real-time — the punch path is unaffected either
  way.
- Env vars: `DEVICE_HOST/PORT/USER/PASS`, `DEV_ID`, `PORTAL_BASE_URL`,
  `BIOMAX_SYNC_TOKEN`, `BATCH_SIZE`, `DRY_RUN`. Defaults match the current prod
  device (`AMDB26013800122`).
## Cloud-async refresh (no on-site machine)

The same mirror can be rebuilt with **no on-site PC** by pulling the device's user
table over the `receive_cmd` channel the terminal already polls on the VPS.

Trigger it (headless — same `X-BioMax-Sync-Token` as the on-site sync):
```
POST /api/v1/attendance/provisioning/refresh-user-info?dev_id=<serial>&scope=awaiting
    -H "X-BioMax-Sync-Token: <secret>"
```
- `scope=awaiting` (default) re-checks only students still "awaiting face" — small
  and cheap; `scope=all` refreshes every platform userId.
- It queues `GET_USER_INFO` commands (batched small — each returned user carries
  face/photo blobs and the device's response buffer is ~400 KB). The device drains
  them on its normal ~20 s poll and returns each user's info in `send_cmd_result`;
  the aidata receiver folds identity + `has_face` into the mirror, **dropping the
  biometric blobs**.
- Automate daily with a VPS cron hitting the endpoint (admin-authed), e.g. off
  hours. No laptop, no LAN, no Wi-Fi-isolation problem.

Captured protocol (all on `POST /AIData.aspx`):
- `receive_cmd` (device→server, ~20 s): body is a status block
  (`userCount/faceCount/fpCount/...`).
- server reply headers `cmd_code: GET_USER_INFO` + `trans_id`, body
  `{"packageId":0,"usersId":[…]}`.
- `send_cmd_result` (device→server): `cmd_return_code: OK`, body
  `{"packageId":N,"usersCount":N,"users":[{userId,name,face,fps,photo,vaildStart,
  vaildEnd,timeGroups}]}` — `face`/`fps` present ⇒ `has_face`.

## Biometric backup (encrypted, real-time)

So a lost/reset terminal can be restored **without re-enrolling every student**,
the platform backs up each enrolment's templates as they happen:

- The device pushes `realtime_enroll_data` (face/photo/fingerprint blobs) on every
  enrolment. When `BIOMAX_BIOMETRIC_KEY` is set, the receiver stores those blobs
  **Fernet-encrypted** in `device_user_biometrics` (identity mirror stays blob-free).
  No key ⇒ blobs are dropped exactly as before.
- **This is sensitive PII.** The encryption key lives ONLY in the env
  (`BIOMAX_BIOMETRIC_KEY`), so a DB dump alone can never reveal a template. Ensure
  you have consent/authority to retain it. Generate the key with:
  ```
  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
  ```
- **Real-time** covers future enrolments automatically.

### Backfill (already-enrolled students)

Students enrolled before this shipped have no `realtime_enroll_data` to catch, so
back them up over the cloud-async channel — a `GET_USER_INFO` result carries the
same face/photo/fps blobs, and (with a key set) `apply_user_info_page` stores them
encrypted. Just run a full refresh:
```
POST /attendance/provisioning/refresh-user-info?dev_id=<serial>&scope=all
    -H "X-BioMax-Sync-Token: <secret>"
```
The device drains the batches on its poll; check coverage with:
```
GET /attendance/provisioning/biometrics/status?dev_id=<serial>   (admin)
```

### Restore (replaced / reset device)

```
POST /attendance/provisioning/restore?dev_id=<serial>
    -H "X-BioMax-Sync-Token: <secret>"
```
Queues a `SET_USER_INFO` **carrying the stored template** for every backed-up
user; the device applies them on its poll, re-creating enrolled users with **no
manual re-enrollment**. The queued command holds only identity + a flag — the
template is **decrypted and injected into the wire body at emit time**, so
cleartext biometrics never sit in the queue.

> Before trusting this for DR, verify a **one-user round-trip**: back up a user,
> delete them on the device, restore, and confirm the face matches again.

## Which to use

- **On-site agent + scheduled task** — reliable when the integration PC is on the
  device's LAN (no Wi-Fi client isolation). Full-replace (also drops removed
  users).
- **Cloud-async refresh** — no on-site machine; works wherever the device reaches
  the VPS. Upsert-only (doesn't remove); heavier per-user (blob transfer), so
  prefer `scope=awaiting` for the daily run and `scope=all` occasionally.
