# BioMax on-site test runbook — punches-in + webpage push/enrollment

A sequenced, on-site test plan for an evening session on the **institute
network**, covering the two workflows end to end:

1. **Reading live punches** (attendance-in) — already live; this is a
   confidence/regression check.
2. **Push / enrollment from the webpage** (Path B provisioning) — Increments 1–3
   are built and deployed but **dormant behind `BIOMAX_PROVISIONING_ENABLED`**,
   and the actual emission to the device (Increment 4) is **not wired yet**.

> **Read this first — what tonight can and cannot achieve.**
> You can (1) confirm punches still land, (2) validate the whole webpage push UI
> live against real device data *up to the queue* (commands enqueue and sit
> `pending` — nothing is emitted), and (3) **get the capture** that unlocks
> emission. You **cannot** fully register a student from the webpage tonight:
> that needs Increment 4, which the capture unblocks for a follow-up build.

Companion docs:
- Engineering detail + capture runbook: `biomax-provisioning-implementation.md`
  (§0.4 relay mode, §0.5 local capture).
- Live-punch transport + watchdog: `biomax-https-and-watchdog.md`.
- Progress tracker (user-facing): the master-plan artifact.

---

## 0. Before you start

- **Device** on the institute Wi-Fi. Push Server **`8443` / Https On** (or the
  plain fallback **`8099` / Https Off**), **Real Time Req On**. Only *Push
  Settings* matters — ignore the WAN screen.
- **Portal**: logged in as an **admin** (`super_admin` / `branch_admin`) — the
  **Device sync** tab is admin-only.
- **SSH** to the VPS ready:
  ```bash
  ssh -i ~/.ssh/academy_vps root@116.203.116.141
  ```
  Compose dir on the VPS: `/srv/academy/repo/infra/compose`.
- **Phase 3 only**: the SmartOffice laptop on-site, on the same LAN, with
  SmartOffice + MSSQL running.
- The liveness **watchdog stays armed** throughout
  (`/etc/cron.d/attendance-watchdog`); a brief blip during a proxy restart
  self-heals.

---

## Phase 1 — Punches still land (confidence check, ~5 min)

*Already works — no change. Proves the transport before we touch anything.*

1. On the device, scan a **known-enrolled user** whose device userId (roll
   number) exists as a student `rfid_number` on the platform.
2. On the VPS, watch ingestion:
   ```bash
   docker logs --since 3m academy-prod-aidata-proxy-1 | grep 'AIData punch'
   ```
   **Expect:** `AIData punch <userId>@<ts> -> inserted=1 skipped_no_student=0`,
   with a **distinct timestamp per scan**.
3. In the portal → **/attendance** → the student shows **PRESENT** for today.

**Pass:** distinct timestamp, `inserted=1`, present on the board.
**If it loops** (the *same* timestamp every ~4 s): the device port reverted to
`80` → it's hitting Caddy and looping. Set the port back to `8443`/`8099`.
**Rollback:** none — read-only.

---

## Phase 2 — Turn the webpage flow on & exercise it (~15 min)

*Validates Increments 1–3 live. Safe: identity-only mirror, and pushing only
fills the queue — nothing is emitted to the device.*

1. **Enable the flag** on the VPS:
   ```bash
   cd /srv/academy/repo/infra/compose
   # set BIOMAX_PROVISIONING_ENABLED=true in .env.prod
   docker compose up -d backend
   ```
   Migration `0045` is already applied, so no migrate step is needed. (Recreating
   `backend` by hand is fine here precisely because there is no new migration —
   see the "manual recreate skips migrations" landmine in `CLAUDE.md`.)
2. **Open** /attendance → **Device sync**. The status pill should read
   **"Provisioning on"**.
3. **Reconcile state:** the device-user mirror starts **empty** — the device
   only sends its user table on an enroll / re-sync event, **not** on a periodic
   poll — so every student with a numeric roll number appears under **"Need
   pushing"**. This is expected, not a bug. To populate the mirror, enroll or
   re-sync a user on the device and watch:
   ```bash
   docker logs --since 5m academy-prod-aidata-proxy-1 | grep 'enroll mirror'
   ```
   The user then moves out of "Need pushing".
4. **Exercise the push:** tick 1–2 students → **"Push to device…"** → the
   **dry-run preview** shows create/update/skip counts and per-student rows →
   **confirm**. A toast reports `Queued N`. The **Command queue** panel lists
   them as **`pending`**.
   - **They stay `pending`** — the device is **not** sent anything. Emission is
     Phase 3/4.
   - **Cancel** one pending command to confirm the cancel path.

**Pass:** tab loads, reconcile diff is sane, dry-run preview is correct, push
enqueues `pending` commands, cancel works.
**Rollback:** set `BIOMAX_PROVISIONING_ENABLED=false` in `.env.prod` and
`docker compose up -d backend`. Enqueued rows are inert; they can also be left —
nothing acts on them while the flag is off.

---

## Phase 3 — The capture (the real prize, ~30 min)

*The one gate for Increments 4 & 5. Records how a `SET_USER_INFO` command rides
in the HTTP reply and what the device sends back to confirm. Without a confirmed
format, emission cannot be built.*

1. **Flip the proxy to relay mode** (full runbook: impl-doc **§0.4**). On the
   VPS, set on the `aidata-proxy` service:
   ```
   AIDATA_RELAY_UPSTREAM=http://103.171.50.109:8080   # the institute SmartOffice
   ```
   and restart just the proxy:
   ```bash
   docker compose up -d aidata-proxy
   ```
   The proxy now relays the device through SmartOffice and logs
   **biometric-redacted CAPTURE lines** of both legs. (Alternative: the local
   capture tool `infra/aidata-proxy/local_capture.py`, impl-doc **§0.5**.)
2. **Trigger a registration:** in the SmartOffice UI, register a test user. It
   queues a `SET_USER_INFO` command; the device fetches it in the reply to its
   next push (through the relay).
3. **Capture the framing:**
   ```bash
   docker logs --since 10m academy-prod-aidata-proxy-1 | grep -i CAPTURE
   ```
   Record: **where the payload sits** (response header vs body), the exact
   `cmd_code` framing, and the device's **result-message** format on the next
   push.

**Pass:** you have the exact wire framing + result-message format.
**If Phase 0/capture yields no usable format:** per the impl doc, that is an
accepted stop point for the write path — not a bug to engineer around.

**CLEAN UP (critical — do before leaving this phase):**
```bash
# unset AIDATA_RELAY_UPSTREAM in the proxy env, then:
docker compose up -d aidata-proxy
```
Then **re-run the Phase 1 punch check** to confirm the device is back to direct
ingest into our platform.

---

## Phase 4 — Stretch: one real registration end-to-end

*Only if the capture is clean and there is time. Realistically a follow-up build
session, not live-coded on-site.*

1. Wire `_ack()` in `aidata.py` to emit one queued command from
   `device_command_repo.next_pending` in the **captured framing**, and map the
   device's result message → `mark_confirmed` / `mark_failed`.
2. Deploy, push a **single** student from the webpage, and watch them appear on
   the device (identity only — the face still enrols physically at the device).
3. Only after one clean single-student round-trip, consider the bulk path.

---

## End-of-session cleanup (do not skip)

- [ ] **Relay OFF** — `AIDATA_RELAY_UPSTREAM` unset, proxy restarted. *This is
      the one that breaks live attendance if left on.*
- [ ] **Flag** — recommended **back to `false`** until emission ships (the queue
      does nothing without it). Leave `true` only if you want staff to see the
      read-only reconcile view.
- [ ] **Device** — port `8443`/Https On (or `8099`), Real Time Req On.
- [ ] **Confirm one live punch lands** (Phase 1) before leaving.
- [ ] **Watchdog** still armed (`/etc/cron.d/attendance-watchdog`).

---

## Quick reference

| Need | Command |
|---|---|
| Watch punches | `docker logs --since 3m academy-prod-aidata-proxy-1 \| grep 'AIData punch'` |
| Watch enroll mirror | `docker logs --since 5m academy-prod-aidata-proxy-1 \| grep 'enroll mirror'` |
| Enable provisioning | set `BIOMAX_PROVISIONING_ENABLED=true` in `.env.prod` → `docker compose up -d backend` |
| Relay on (capture) | set `AIDATA_RELAY_UPSTREAM=http://103.171.50.109:8080` → `docker compose up -d aidata-proxy` |
| Relay off (cleanup) | unset `AIDATA_RELAY_UPSTREAM` → `docker compose up -d aidata-proxy` |
| Capture lines | `docker logs --since 10m academy-prod-aidata-proxy-1 \| grep -i CAPTURE` |

Device settings, ports, and the failure matrix live in
`biomax-https-and-watchdog.md`; the command vocabulary and identity model live
in `biomax-provisioning-implementation.md` §0.6.
