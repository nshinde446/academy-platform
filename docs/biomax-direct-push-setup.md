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
- **Device serial** (the `SN` the device sends): on the device's **Network**
  screen, the **`Cloud ID`** value (e.g. a 16-char hex string like
  `95068A9657DD5458`). Comma-separate multiple devices. If unsure, do a test
  punch (Part 3) and read the `SN=` value from the backend log.
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
3. **Point it at us** — on this BioMax face model the menu is
   **`Network → Push Settings`** (the same Network screen shows `Cloud ID`,
   `Wi-Fi`, and an **`Https`** toggle). Push Settings is the same Server-IP +
   Port pair BioMax's own cloud uses (`www.bmxcloud.in` / `8001`) — just point
   it at us instead:
   - **Server Address / Server IP**: **`<app-domain>`** (host only — no
     `https://`, no `/iclock`; the firmware appends `/iclock/...`)
   - **Server Port**: **`443`**
   - **Enable Domain Name**: **ON** (lets you enter a domain, not just an IP)
   - **Https**: **ON** (this model supports it — confirmed on the Network screen)
   - Enable push / real-time: **ON** (label may be `Push`, `Enable`, or
     `Realtime`)
   - `Proxy`: **OFF**

   (Older/other BioMax firmwares instead put this under `Comm → Cloud Server
   Setting` with `Enable Domain Name` + `Server Address` + `Server Port`, or
   `Settings → Network → Server IP/Port + Realtime Req: Yes` — same idea.)
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
- **HTTPS support.** This BioMax model exposes an `Https` toggle on the Network
  screen, so use **443 + Https ON**. (Some older BioMax/ZKTeco firmwares are
  HTTP-only — if a different unit won't connect on 443, it needs an nginx rule
  accepting `/iclock/*` over plain HTTP:80 → backend; punches then travel in
  plaintext, mitigated by the serial allowlist.)
- **No SIM on the Multibio-900** — it depends on the institute's WiFi/LAN
  internet. Shore that up, or choose a 4G model for internet-independent push.
- **Serial must match exactly** what the device sends as `SN` (its Cloud Number).

## First-device test checklist (printable)

A single-device on-site smoke test. Goal: **one real face punch appears on
`/attendance` as the right student, on the right day, within ~30s.**

### Before you go (from your desk)
- [ ] Backend reachable at `https://<app-domain>` (open it in a browser).
- [ ] SSH access to the VPS confirmed.
- [ ] `BIOMAX_BRANCH_ID` set + verified:
      `docker exec academy-prod-backend-1 printenv BIOMAX_BRANCH_ID`.
- [ ] Pick **one test student**; set their `rfid_number` in the roster to a value
      you'll use as the device User ID (e.g. `9001`).
- [ ] Have: device admin passcode, institute **WiFi SSID + password**, a
      phone/laptop to watch `/attendance` and a terminal for backend logs.

### On-site (in order)
1. [ ] Power the device, connect WiFi (`Menu → Comm/Network → WiFi`) →
      **WiFi/online icon shows**.
2. [ ] Read the **Serial / Cloud Number** (`Menu → Comm → Cloud Number` or the
      back sticker) → write it here: `________________`.
3. [ ] Add it to the allowlist and reload:
      ```bash
      cd <repo>/infra/compose && nano .env.prod   # BIOMAX_DEVICE_SERIALS=<serial>
      docker compose -p academy-prod -f docker-compose.prod.yml --env-file .env.prod up -d --force-recreate backend
      docker exec academy-prod-backend-1 printenv BIOMAX_DEVICE_SERIALS
      ```
4. [ ] Set the device **clock + timezone to IST** (`Settings → Device → Time`).
5. [ ] Point it at us (**`Network → Push Settings`**): Server Address =
      **`<app-domain>`**, Port = **`443`**, **Https = ON**, enable push/realtime.
      Save → reboot if asked → **cloud/connected icon shows**.
6. [ ] Enroll one face with **User ID = the test student's `rfid_number`**
      (`9001`).
7. [ ] Start watching:
      ```bash
      docker logs -f --tail=20 academy-prod-backend-1 | grep -i iclock
      ```
      and open `/attendance` (today, the test student's batch) in a browser.
8. [ ] **Do a test face punch.**

### Pass criteria
- [ ] Log shows `GET /iclock/cdata?SN=…` then `POST /iclock/cdata` → `OK: 1`.
- [ ] `/attendance` shows the test student **PRESENT** within ~30s.
- [ ] The date/time on the record is correct (IST).

### If it fails — symptom → fix
| Symptom in log / UI | Cause | Fix |
|---|---|---|
| No `GET /iclock` at all | Device can't reach server | WiFi/internet down; port 443 blocked or firmware is HTTP-only (try 80 + nginx rule); wrong domain |
| `401 Unknown … serial` | Serial not allowlisted | Copy the `SN=` from the log into `BIOMAX_DEVICE_SERIALS`, recreate backend (step 3) |
| `503 … BRANCH_ID` | `BIOMAX_BRANCH_ID` unset | Set it, recreate backend |
| `POST … OK: 1` but student not on register | `rfid_number` ≠ device User ID | Align them (step 6 / roster) |
| Record on the wrong day | Device clock/timezone wrong | Fix step 4 |
| Connected icon, no punches arrive | Real-time push off | Set `Realtime Req = Yes` (step 5) |

### After a green test
- [ ] Add every other device's serial to `BIOMAX_DEVICE_SERIALS` (comma-separated).
- [ ] Enroll all students (`rfid_number` = device User ID).
- [ ] Decide **HTTPS vs HTTP** for the fleet (if the unit only connected on 80,
      request the nginx `/iclock` HTTP rule).

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
