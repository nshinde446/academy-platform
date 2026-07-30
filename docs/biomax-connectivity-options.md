# BioMax device ↔ our platform — connectivity options (decision doc)

**Status:** ✅ **SOLVED, 2026-07-30.** Option A is live end-to-end — the device
polls `receive_cmd` from our VPS and applies pushed users. **Owner:**
attendance/provisioning work.

## TL;DR — the winning path (proven)
Both directions now run **device → our VPS, no on-prem laptop**:
- **Read punches:** device `realtime_glog` → VPS (already live).
- **Push users:** device `receive_cmd` poll → VPS emits `SET_USER_INFO` → device
  registers the user. **Proven live:** pushed `9990009 / WEB TEST` *and* a real
  student (`2801300 / Gauravi`) from the webpage; both appear in the device's
  user table (`GetUserIdList`, count 6→7→…).
- **The unlock:** point the device's **command channel** (`serverHost:serverPort`)
  at our VPS. We did this **via the device's own local HTTP API** — `POST /bin/cmd`
  `{"cmd":"SetDeviceSetting","data":{...serverHost/serverPort/pushServerHost/
  pushServerPort/pushEnable...}}` (Digest `admin`/`admin`, port 80). This is a
  **one-time config write**, not an on-prem dependency — Option B's API turned out
  to be the *tool that configures Option A*, not a separate fallback.
- **Caveat:** this R6 acks a successful command with an **empty** `send_cmd_result`
  (echoes `trans_id`, no return code). Backend now treats "no explicit failure" as
  success; ground truth remains reconcile vs the device's user table.
- **TODO:** confirm `serverHost` **persists across a device reboot** (this unit had
  a settings-save quirk on its *physical* menu; the API write should stick).

## The goal
Our web platform must, for the BioMax R6 face terminal (`AMDB26013800122`):
1. **Read punches** from it (attendance in), and
2. **Push users** to it (userId + name — identity provisioning; the face template
   still enrols physically at the device).

## Hard constraints
- Our platform is **cloud-hosted** (Hetzner VPS, always-on).
- The device is on the **institute LAN** (behind NAT).
- **No always-on on-prem PC is guaranteed** — the coaching laptop running
  SmartOffice **cannot be kept up 24/7**. So any solution that depends on the
  laptop is not acceptable as the permanent answer.

## What we confirmed (live, 2026-07-30)

**Device port scan** (`192.168.1.7`, on the LAN via the laptop):

| Port | State | Meaning |
|---|---|---|
| **4370** ZKTeco standalone SDK | **closed** | direct `pyzk`/TCP-SDK path **not available** on this unit |
| **80** HTTP (`lighttpd` + Digest auth) | **open** | device has its **own local HTTP API/admin**, credential-gated |
| **5005** LAN SDK (binary) | **open** | BioMax/SmartOffice LAN SDK channel |
| 8080 / 22 / 23 | closed | — |

**Protocol facts** (reverse-engineered from SmartOffice's own code + logs — see
`biomax-provisioning-implementation.md` §0.6/§0.7):
- The device speaks the **AIData push protocol** (`POST /AIData.aspx`,
  `request_code`-switched). Punches (`realtime_glog`) → our VPS **work today**.
- Server→device commands ride a **device-initiated `receive_cmd` poll every ~20s**
  (proven: 773 polls to SmartOffice). A delivered command = response headers
  `response_code: OK` + numeric `trans_id` + `cmd_code: SET_USER_INFO` + JSON body;
  empty = `response_code: ERROR_NO_CMD`. Our receiver matches this (PR #55).
- The device only issues `receive_cmd` to the server its **command/cloud channel**
  is pointed at — and that is set **on the device's own menu**. There is **no
  server-side command to redirect it** (SmartOffice's vocabulary has no
  SET_SERVER; only SET_USER_INFO/GET_*/SET_TIME/DELETE_USER).

## Architecture reality
A cloud app reaches a LAN device only two ways:
1. **Device-initiated** (device → cloud push + poll) — **no on-prem box**.
2. **On-prem bridge** — a small always-on LAN box (Raspberry Pi / mini-PC, **not**
   the laptop) talks to the device over LAN and syncs outbound to our cloud.

## Options

| # | Path | Read punches | Push users | On-prem box? | Status |
|---|---|---|---|---|---|
| **A** | **AIData push, device → our VPS (both directions)** | ✅ works | ✅ **works** via `receive_cmd` poll | **none** | ✅ **PROVEN live 2026-07-30** — device command channel pointed at our VPS via the port-80 API; users pushed from the webpage land on the device |
| **B** | **Device local HTTP API (port 80, lighttpd/digest, `admin`/`admin`)** | ✅ (`GetLogDataPage`) | ✅ (`SetUserInfo`) | small dedicated box | **creds/endpoints now known** — `/bin/cmd` JSON API. Used here to *configure A*; also a viable direct-LAN bridge if ever needed |
| C | Port 5005 LAN SDK (binary) | maybe | maybe | small dedicated box | undocumented binary protocol; hardest |
| D | ZKTeco `pyzk`/4370 | — | — | — | ❌ port closed — ruled out |
| E | Buy a universal gateway (CAMS / Minop) | ✅ | ✅ | depends | paid third-party dependency |

## Decision — ✅ Option A, live

- **Punches: solved** via Option A (device→VPS). Keep it.
- **Push users: solved** via Option A. The device's command channel
  (`serverHost:serverPort`) was pointed at our VPS (`116.203.116.141:8099`) with a
  one-time `SetDeviceSetting` over the port-80 `/bin/cmd` API. The device now polls
  `receive_cmd` from us every ~20s and applies queued `SET_USER_INFO` commands.
  Platform side runs behind `BIOMAX_PROVISIONING_ENABLED=true`.
- **Option B is not needed as a running bridge** — its API was the *means to
  configure A*. It stays documented as a direct-LAN fallback (a ~₹3–4k Pi, never
  the laptop) if the device's cloud config ever can't reach our VPS.

No on-prem hardware, no always-on laptop — exactly the hard constraint.

## Next steps
1. **Verify persistence:** confirm the device keeps `serverHost` → our VPS across a
   reboot / power cycle. If it reverts, re-apply via the port-80 API (scriptable) or
   have the installer set it on the device menu once.
2. **Reconcile as ground truth:** wire the Device-sync page's "confirmed" state to
   the device user table (`GetUserIdList` / the `realtime_enroll_data` mirror) rather
   than the ambiguous empty `send_cmd_result`.
3. **Push real students** from the Device-sync page for the roster and monitor the
   queue moves to `confirmed`.

## Testing log
- 2026-07-30: port scan above. Port 80 = `lighttpd/1.4.54`, Digest realm
  `"Login"`, all paths 401 without creds. Port 5005 open (binary).
- 2026-07-30: **port 5005** accepts TCP connections but returns nothing to any
  text probe (`""`, `\x00`, HTTP, `CMD`) — it waits for a **binary SDK frame**.
  Confirmed proprietary binary LAN SDK; needs the vendor SDK/library. Hard path.
- 2026-07-30: **port 80** — every probed path (`/`, `/device.rsp`, `/info`,
  `/status`, `/csl/getuser`, `/cgi-bin/deviceinfo.cgi`, `/iclock/cdata`, …)
  returns **401**. The device requires **Digest auth on all endpoints**, so
  Option B cannot be probed further **without the device admin credentials**.
- **BLOCKED ON:** the device's port-80 admin username/password. With it, probe
  `curl --digest -u <user>:<pass> http://192.168.1.7/<path>` for a
  user-management / attendance endpoint (run by the operator so the password is
  never handled by the assistant).
- 2026-07-30: **UNBLOCKED** — device port-80 API is `POST /bin/cmd`, Digest
  `admin`/`admin`, JSON `{"cmd":...,"data":{...}}` → `{"result_code":0,...}`.
  Verified commands: `GetDeviceInfo`, `GetDeviceSetting`, `SetDeviceSetting`,
  `GetUserIdList`, `GetUserInfo`. (PowerShell strips quotes from inline `-d` —
  write the body to a file and use `curl --data-binary @file`.)
- 2026-07-30: `GetDeviceSetting` showed `serverHost=192.168.1.5:82` (SmartOffice)
  but `pushServerHost=116.203.116.141:8099` (our VPS) — i.e. punches already came
  to us, commands went to SmartOffice. Root cause of "device never polled us."
- 2026-07-30: **`SetDeviceSetting` → `serverHost=116.203.116.141:8099`** (both
  channels now our VPS). Device began `receive_cmd` polling our VPS within ~20s.
- 2026-07-30: ✅ **END-TO-END PROVEN.** Queued `SET_USER_INFO` for `9990009 / WEB
  TEST`; device fetched it (emit trans_id=445744715), applied it — `GetUserIdList`
  count 6→7 with `WEB TEST` present. Real student `2801300 / Gauravi` pushed the
  same way and registered. **Webpage → device user push works.**
- 2026-07-30: device acks success with an **empty** `send_cmd_result` (trans_id
  echoed, no return code) → backend previously mis-marked these `failed`. Fixed:
  absence of an explicit failure code now = confirmed.
