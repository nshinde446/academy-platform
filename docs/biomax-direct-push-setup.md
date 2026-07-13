# BioMax direct-push attendance setup (no PC)

How to make a **BioMax Multibio-900** (or any BioMax/ZKTeco face terminal) push
punches straight to this platform in real time — **no SmartOffice, no PC, no
agent**. The device itself pushes each punch over the internet to our already-live
`/iclock` endpoint (the ZKTeco/ADMS "push" protocol).

```
 BioMax device ──(ADMS push over HTTPS)──► /iclock/cdata ──► ingest ──► DailyAttendance
   on the wall, always on                  (already deployed)          → /attendance live-refreshes
```

The receiving side is **already built and deployed** (`app/modules/attendance/
integrations/biomax/iclock.py`); this doc is just how to point a device at it and
set two env vars.

## Why this device works well for it

The Multibio-900 (per its spec sheet + BioMax docs):

- **Push data / ADMS: yes** — "push data feature ensures real-time sync". Points
  at a custom server. ✔ direct push.
- **Offline buffer: 200,000 logs** — if the internet or our server is briefly
  down, the device stores punches and re-sends on reconnect (~600+ days at ~300/
  day). Outages *delay*, they don't lose data.
- **Connectivity: WiFi / TCP-IP / USB — no SIM.** So it must sit on the
  institute's network **with internet**. (For a fully WiFi-independent setup a
  SIM/4G model like the N-Uface 602 would be needed.)
- Linux, ZKTeco-family, TCP/IP port 4370 — so the Raspberry-Pi `pyzk` fallback
  (below) also works if direct push is ever blocked.

## Part 1 — Backend env (once)

The direct-push path needs exactly two backend vars. **Where:** `infra/compose/
.env.prod` on the Hetzner VPS.

**1a. Get the values**
- **Device serial** (the `SN` the device sends): on the device, `Menu → Comm/
  Network → Cloud Number` (or the sticker on the back). Comma-separate multiple
  devices. If unsure, do a test punch (Part 3) and read the `SN=` value from the
  backend log.
- **Branch UUID**: while logged into the app, open
  `https://<app-domain>/api/v1/auth/me` → copy `branch_roles[0].branch_id`.

**1b. Edit `.env.prod` on the VPS**
```bash
ssh <you>@<vps-host>
cd <repo>/infra/compose
nano .env.prod
```
```ini
BIOMAX_DEVICE_SERIALS=ABC123456789      # comma-separated for >1 device
BIOMAX_BRANCH_ID=<the-branch-uuid>
```
Fail-safe: empty `BIOMAX_DEVICE_SERIALS` rejects every device (401); empty
`BIOMAX_BRANCH_ID` returns 503. Both must be set.

**1c. Apply** (env is baked at container creation — recreate, not restart)
```bash
docker compose -p academy-prod -f docker-compose.prod.yml --env-file .env.prod up -d --force-recreate backend
docker exec academy-prod-backend-1 printenv BIOMAX_DEVICE_SERIALS BIOMAX_BRANCH_ID
```

## Part 2 — Device menu (once, at the device)

Exact labels vary by firmware; BioMax face terminals use one of these two layouts
— use whichever your unit shows. The server URL you point at is the same one the
**Integrations tab** shows as "Device server URL": `https://<app-domain>` (host
only — the firmware appends `/iclock/...` itself).

1. **Log in as admin** on the device (Menu → admin auth).
2. **Get it online:** `Menu → Comm/Network → WiFi` → enable, pick the network,
   enter the password (or plug in Ethernet). It needs **internet**.
3. **Point it at us** — either:
   - **Layout A (touch / SmartOffice-cloud models): `Comm → Cloud Server Setting`**
     - `Enable Domain Name`: **ON**
     - `Server Address`: **`<app-domain>`** (host only — no `https://`, no `/iclock`)
     - `Server Port`: **`443`**
     - `Enable HTTPS/SSL`: **ON** (if present, paired with 443)
     - `Proxy`: **OFF**
   - **Layout B (`Settings → Network`, per the BioMax firmware manual):**
     - `Server IP`: **`<app-domain>`** (or its IP)
     - `Server Port`: **`443`**
     - `Realtime Req`: **`Yes`**  ← this is what enables real-time push
4. **Save** → reboot if prompted. The device should show a **cloud/connected**
   icon once it handshakes.
5. **Set the clock:** `Settings → Device → Time` — set correct local date/time
   (and timezone if the model has one) to **IST**. Punch times are read as
   device-local and converted to UTC, so a wrong clock = wrong day.
6. **Punch interval (optional):** `Settings → Rec. Rule → Punch interval` — the
   device already suppresses repeat punches within N minutes; our server also
   dedups a 5s window, so either is fine.
7. **Enroll users** so each person's **device User ID = their `rfid_number`** in
   the app. That is the only mapping that resolves a punch to a student.

## Part 3 — Verify

1. Do a **test face punch** on the device.
2. Watch the **/attendance** register (it auto-refreshes ~12s) — the punch should
   appear within seconds.
3. If nothing shows, check the backend log:
   ```bash
   docker logs --tail=50 academy-prod-backend-1 | grep -i iclock
   ```
   - Expect `GET /iclock/cdata?SN=…` (handshake) then `POST /iclock/cdata` (ATTLOG).
   - **401** → the `SN` isn't in `BIOMAX_DEVICE_SERIALS` (copy it from the log
     into the env, redo Part 1c).
   - **503** → `BIOMAX_BRANCH_ID` unset.
   - **Nothing at all** → the device can't reach the server (network / port /
     HTTP-vs-HTTPS — see below).

## Gotchas

- **One ADMS server per device.** Pointing it here means it won't also feed
  SmartOffice. That's intended (no PC). If the institute still needs SmartOffice
  for payroll, keep SmartOffice and use the agent/pyzk path instead.
- **HTTP-only firmware.** Some BioMax/ZKTeco firmwares don't do HTTPS. Try `443`
  first; if it won't connect, the unit is HTTP-only and needs an nginx rule that
  accepts `/iclock/*` over plain HTTP:80 → backend (punches then travel in
  plaintext — mitigated by the serial allowlist). Ask the platform admin to add
  it.
- **No SIM on the Multibio-900** — it depends on the institute's WiFi/LAN
  internet. Shore that up, or choose a 4G model for internet-independent push.
- **Serial must match exactly** what the device sends as `SN` (its Cloud Number).

## Fallbacks (if direct push is blocked)

Both feed the same ingest pipeline; no downstream changes.

- **Raspberry Pi + `pyzk`** on the LAN talks to the device over TCP/IP 4370
  (`live_capture`) and forwards to us — a $35 always-on box instead of a PC. Use
  if the firmware won't push to a custom URL, or SmartOffice must coexist.
- **SmartOffice + on-prem agent** (`agent/smartoffice/`) — reads SmartOffice's
  SQL and pushes to `/attendance/smartoffice/ingest`. Use only if the institute
  keeps SmartOffice.

## References

- Device server URL is also shown/copyable on the in-app **Integrations** tab.
- Receiver: `backend/app/modules/attendance/integrations/biomax/iclock.py`.
- Env vars: `BIOMAX_DEVICE_SERIALS`, `BIOMAX_BRANCH_ID` (see
  `infra/compose/.env.prod.example`).
