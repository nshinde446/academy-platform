# BioMax device ↔ our platform — connectivity options (decision doc)

**Status:** open decision, 2026-07-30. **Owner:** attendance/provisioning work.

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
| **A** | **AIData push, device → our VPS (both directions)** | ✅ works | via `receive_cmd` poll | **none** | build done; blocked on device-menu config pointing the command channel at our VPS |
| **B** | **Device local HTTP API (port 80, lighttpd/digest)** | likely | likely (`setUserInfo`-type) | small dedicated box | **untested — needs device admin creds + endpoint spec** |
| C | Port 5005 LAN SDK (binary) | maybe | maybe | small dedicated box | undocumented binary protocol; hardest |
| D | ZKTeco `pyzk`/4370 | — | — | — | ❌ port closed — ruled out |
| E | Buy a universal gateway (CAMS / Minop) | ✅ | ✅ | depends | paid third-party dependency |

## Decision

- **Punches: solved** via Option A (device→VPS). Keep it.
- **Push users: pursue A and B in parallel.**
  - **A (primary):** have the **BioMax installer** point the device's command
    channel at our VPS and confirm it saves. Cleanest, laptop-free; our platform
    is 100% built for it (Increments 1–4 + proxy, dormant behind
    `BIOMAX_PROVISIONING_ENABLED`). Blocked only because the on-device setting
    would not save for us tonight and the device kept auto-attaching to
    SmartOffice on the LAN.
  - **B (fallback):** the most promising *new* lead. The device has a real local
    HTTP API (port 80). With the **device admin credentials + endpoint spec**, a
    tiny **always-on on-prem bridge** (a ~₹3–4k Raspberry Pi — never the laptop)
    can push users + read punches over the LAN, **independent of the device's
    cloud config**. Needs testing.

Option A is preferred (no on-prem hardware). Option B is the resilient fallback
if the device's command channel can't be pointed at our VPS.

## Next steps
1. **A:** installer points the device command/cloud server → `attend.eduworld-livekit.duckdns.org:8443` (or `116.203.116.141:8099`), confirm a `receive_cmd` poll reaches our VPS.
2. **B:** obtain the device's **port-80 admin credentials** + any BioMax HTTP-API
   doc → probe `http://<device>/` on the LAN for a user-management endpoint → if
   present, spec a small on-prem bridge.
3. Keep the platform side dormant behind the flag until one path is live.

## Testing log
- 2026-07-30: port scan above. Port 80 = `lighttpd/1.4.54`, Digest realm
  `"Login"`, all paths 401 without creds. Port 5005 open (binary). Awaiting
  device admin creds to probe the port-80 API.
