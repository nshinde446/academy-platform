# Implementation plan — BioMax device provisioning (Phase 2)

The engineering breakdown for pushing student identities to the terminal, so
staff stop typing a name + 10-digit RFID per student. This is the *how* to build;
the *why* and scope decisions live in
[`biomax-provisioning-plan.md`](./biomax-provisioning-plan.md) and are not
repeated here. Ingest (device → platform) is described in
[`biomax-attendance.md`](./biomax-attendance.md).

**Prerequisite: MET.** The device push port is `8099` and the
`infra/aidata-redirect/` stopgap is retired (2026-07-22) — the transport is
stable, so building on it no longer risks masking a silent redirect failure.

**The gate was Phase 0 — now largely CLEARED (2026-07-28).** The command
vocabulary and the registration payload were captured directly from SmartOffice's
own SQL database on the coaching laptop (see §0.6). One small piece remains — the
HTTP *wire framing* of a `SET_USER_INFO` response — which is a short oracle
capture, not a blocker to the design. The old warning still holds for the
delete path: write commands can wipe enrolled faces that our DB cannot restore,
so nothing is emitted on a guess.

---

## Phase 0 — capture the command vocabulary (the gate)

Nothing below can be finalised until we know the real `cmd_code` values, their
payload shape, and how the device reports a command's result. Same oracle method
that cracked the ack: let BioMax's own SmartOffice tell us.

### 0.6 RESULT — vocabulary captured from SmartOffice's SQL DB (2026-07-28)

The cleanest oracle turned out to be SmartOffice's **own database**, not a live
relay. With SmartOffice + MSSQL installed on the coaching laptop, its
`SmartOffice` DB (`localhost\SQLEXPRESS`) holds a `DeviceCommands` queue — the
exact server→device channel — with every command it has ever issued to our
terminal (serial `AMDB26013800122`). Read-only queries gave us the authoritative
vocabulary; no device re-pointing, no biometrics touched.

**Command vocabulary** (`DeviceCommands.DeviceCommand` = the `cmd_code`):

| `cmd_code` | meaning |
|---|---|
| `SET_TIME` | sync device clock to server |
| `RESET_ENROLL_MARK` | reset the enroll marker (part of a full user re-read) |
| `GET_LOG_DATA` | pull attendance log records |
| `GET_USER_INFO` | read the device's user table |
| **`SET_USER_INFO`** | **create / update a user — the registration command** |

No explicit delete command has been observed yet (SmartOffice hasn't issued one);
capture it via §0.4/§0.5 before ever building the delete path (Phase 5).

**Registration payload** — `cmd_code: SET_USER_INFO`, body a `users` array. The
captured example (stored in the queue as `$`-separated decimal-ASCII in
`CmdParmStr`), decoded verbatim:

```json
{"users":[{"userId":"1","name":"test","privilege":0,"card":"","pwd":"","vaildStart":"20230728","vaildEnd":"20360728"}]}
```

Field contract (note the vendor typos `vaildStart`/`vaildEnd`):

| field | required | our value |
|---|---|---|
| `userId` | **yes — hard** | the student's roll number (numeric); also `Student.rfid_number`. Empty `userId` is the zombie-record loop bug. |
| `name` | yes in practice | student name (`EmployeeName` is `NOT NULL` in SmartOffice) |
| `privilege` | default `0` | `0` = normal user |
| `card` | optional — **left empty** | physical RFID card number; we do not issue cards (see identity model) |
| `pwd` | optional | PIN; empty |
| `vaildStart`/`vaildEnd` | optional, send wide | `YYYYMMDD` validity window (e.g. `20200101`→`20401231`) so users never silently expire |

**Identity model (decided 2026-07-28) — the crux the code must honour:**

- The device `userId` is the identity key, *separate* from the authentication
  method. A punch — by face, thumb, card, or PIN — reports this `userId`, and
  `aidata.py` matches it to `Student.rfid_number`.
- **`Student.rfid_number` is a misnomer: it holds the device `userId`, not a
  physical card number.** All working punches matched this way. (Worth an
  eventual rename; out of scope here — document, don't churn.)
- **Auth = face and/or thumb, enrolled physically at the device.** Templates
  cannot be pushed. `card` stays empty — cards are not used (every
  `EmployeeRFIDNumber`/`BiometricCardNumber` in SmartOffice is blank; the 4
  enrolled users are face-only). Confirm the physical unit actually has a thumb
  sensor before promising fingerprint — capability flags say yes, `fpCount` is 0.
- **`userId` = the student's roll number, numeric.** Evidence: real userIds are
  `1000120001`/`6`/`1`; the one alphanumeric SmartOffice user (`TestEmployee1`)
  shows `userCount 6` for 7 employees — it appears **not to have synced**. Keep
  userIds numeric, unique per device, ≤ ~10 digits (the field allows 50 but
  firmware is happier short). Map alphanumeric enrollment IDs to a numeric roll.
- **Path B therefore pushes only `userId + name`** to pre-load identity, so staff
  at the device only capture the biometric — never type a name or ID.

**Device capacity** (from `Devices.DeviceInfo` JSON, model Smart2/V536, firmware
`K8D_3Y3Kbio030_3.2`, faceVer `FACE_D_400`): `userLimit 3000`, `faceLimit 3000`,
`cardLimit 3000`, `fpLimit 10000`, `logLimit 200000`, `maxBufferLen ~409600`.
**A 2000-student batch fits comfortably** (current `userCount 6`, `faceCount 4`).
The buffer limit is why bulk `SET_USER_INFO` must chunk (§1.1 / Phase 5.6).

**Why registration can't ride SmartOffice while we own the punches:** the device
has a single push target and the `cmd_code` command comes back *on the punch
response*. With the device pointed at our cloud, SmartOffice's queued commands
never reach it (`Devices.LastPing` froze when we repointed it). So Path B isn't an
add-on — it's the *only* way to register while attendance flows to us.

**Still open — one short capture:** the DB gives the command and payload but not
the HTTP *wire framing* of the response (does the JSON ride in the body or a
header? what result-message does the device send back?). Get it the same oracle
way — POST a `realtime_glog` to SmartOffice's `AIData.aspx` with a `SET_USER_INFO`
queued and record the response — via §0.4 (VPS relay) or §0.5 (local capture).
That closes Phase 0 for the write path.

### 0.1 Relay mode in `aidata-proxy`

Add a `AIDATA_RELAY_UPSTREAM` env toggle to `infra/aidata-proxy/aidata_proxy.py`.
When set, instead of forwarding to `backend:8000`, the proxy:

1. forwards the device's exact POST (headers + body) to
   `http://103.171.50.109:8080/AIData.aspx` (SmartOffice, reachable from the VPS),
2. returns SmartOffice's response **verbatim** to the device — headers included,
   uncanonicalised (the proxy already emits raw header casing, which is the whole
   reason it exists),
3. logs both directions in full to a capture file (request headers/body,
   response headers/body), **redacting `face`/`photo`/`logPhoto`/`fps` blobs to
   key-name-only** — capture is not an excuse to log biometrics.

This is a temporary, explicitly-flagged mode. Default off. It must never ship
enabled.

### 0.2 Capture procedure

With the device pointed at us in relay mode and talking to SmartOffice through
the proxy:

1. **Add a user** in SmartOffice's admin UI. Capture the `cmd_code` + payload
   SmartOffice returns and the follow-up message the device sends to report the
   result.
2. **Edit** that user (rename, change validity). Capture.
3. **Delete** the user. Capture — this is the highest-risk command and we must
   see its exact form before we ever emit one.
4. Note the **result/ack** shape for each: does the device echo a `trans_id`, a
   status code, a confirmation `request_code`? That is what Phase 3 parses.

### 0.3 Exit criteria & timebox

- **Done when** we have a confirmed create, update, and delete command with
  payloads and a confirmed result-message format, reproduced at least twice each.
- **Timebox: one focused session.** If SmartOffice doesn't cleanly reveal the
  commands (e.g. it batches them oddly, or uses a second channel), **stop and
  email BioMax for the AIData server-command spec** rather than guessing. Send
  that email at the *start* of Phase 0 in parallel — it costs nothing.

Record the captured vocabulary in a new appendix of `biomax-attendance.md`
(§ "AIData server→device commands"), the same way the ack contract is documented
there — it becomes the source of truth the code cites.

> If Phase 0 fails to produce a confirmed format, **the feature is not
> buildable** on our side and the plan stops here. Do not proceed on guesses.

### 0.4 Runbook — flipping relay mode for a live session

Relay mode ships in `aidata-proxy` (the `AIDATA_RELAY_UPSTREAM` toggle, off by
default). To run a capture session, on the VPS (`/srv/academy/repo`):

```bash
# 1. Make sure the proxy has the relay-capable code.
git -C /srv/academy/repo pull

# 2. Turn relay ON for one service only, pointed at SmartOffice.
AIDATA_RELAY_UPSTREAM=http://103.171.50.109:8080/AIData.aspx \
  docker compose -p academy-prod -f infra/compose/docker-compose.prod.yml \
  up -d --no-deps aidata-proxy
docker logs --tail 3 academy-prod-aidata-proxy-1   # should log "RELAY/CAPTURE MODE"

# 3. Watch captures while an admin adds/edits/deletes a user in SmartOffice.
docker logs -f academy-prod-aidata-proxy-1 2>&1 | grep CAPTURE

# 4. When done, turn relay OFF and return to normal ingest.
docker compose -p academy-prod -f infra/compose/docker-compose.prod.yml \
  up -d --no-deps --force-recreate aidata-proxy
```

Each `CAPTURE` line is one biometric-redacted JSON leg
(`device->smartoffice` / `smartoffice->device`) with status, original-case
headers, and the redacted body — that is where the `cmd_code` command appears.

**Session is interactive and on-site:** it needs the device on the institute
LAN, SSH to the VPS with the local key, and a person adding a user in
SmartOffice's admin UI — it cannot run as an autonomous/cloud job.

### 0.5 Runbook — local capture (SmartOffice on the coaching laptop)

**Preferred over §0.4 when SmartOffice + MSSQL run on-site.** With SmartOffice
installed on the coaching-center laptop, the capture is a same-LAN, no-cloud job:
the device points at the laptop, not the VPS, so there is no Caddy bypass, no
dynamic-IP relay, and no SSH. Same oracle, fewer moving parts.

Standalone tool: `infra/aidata-proxy/local_capture.py` (stdlib only, no Docker).
It is the local twin of relay mode — forwards each device poll verbatim to local
SmartOffice, echoes SmartOffice's response back byte-for-byte with original
header casing (the firmware is case-sensitive), and writes both legs to
`aidata_capture.log` next to the script. Biometric discipline is identical:
`face`/`photo`/`logPhoto`/`fps`/`template`/`image` are recorded as key + byte
length only, never the blob.

On the coaching laptop, from `infra/aidata-proxy/`:

```bash
python local_capture.py          # prints the laptop LAN IP + port on startup
```

Then on the R6 server/push setting, point the device at the laptop — **Server
IP = the printed LAN IP, Port = 8090 (default), Path = /AIData.aspx** — and allow
the port through Windows Firewall. Add / edit / delete a user in SmartOffice's UI
and watch for a `*** COMMAND ***` console line; the full `cmd_code` + payload is
in `aidata_capture.log`. **When done, point the device back at the VPS** so
normal cloud attendance resumes.

Config via env if defaults don't fit: `SMARTOFFICE_URL`
(default `http://127.0.0.1:8080/AIData.aspx`), `CAPTURE_PORT` (default `8090`),
`CAPTURE_FILE`.

**Only for the write path.** This re-points the device off the VPS for the
duration of the session, so live punches pause while capturing — run it in a
quiet window. Attendance ingest stays on the VPS direct-push; this laptop tool
exists solely to learn the server→device command vocabulary. Record the captured
commands in `biomax-attendance.md` (§ "AIData server→device commands") per §0.3.

---

## Phase 1 — data model

Two new tables in the attendance domain. Both carry the standard base fields
(`id`, `branch_id`, `is_deleted`, `created_at`, `updated_at`) per
`docs/db_conventions.md`, and both are **branch-isolated** — every query filters
`branch_id` (extend `tests/test_branch_isolation.py`).

### 1.1 `device_commands` — the outbound queue

| column | type | purpose |
|---|---|---|
| `id` | uuid pk | |
| `branch_id` | uuid fk | isolation |
| `dev_id` | text | target terminal (matches the ingest allowlist) |
| `command` | text | the captured `cmd_code` (`SET_USER_INFO` for register; see §0.6) |
| `payload` | jsonb | captured payload (`userId`, `name`, `privilege`, `vaildStart`/`vaildEnd`; `card` empty) |
| `student_id` | uuid fk null | provenance; null for non-student ops |
| `status` | enum | `pending` / `sent` / `confirmed` / `failed` / `cancelled` |
| `attempts` | int | delivery attempts, capped |
| `sent_at` / `confirmed_at` | timestamptz null | delivery tracking |
| `last_error` | text null | why it failed |
| `idempotency_key` | text | `(dev_id, command, userId)` dedupe within a push |

Indexes: partial index on `(dev_id, status) WHERE status = 'pending'` for fast
dequeue; unique partial on `idempotency_key WHERE status IN ('pending','sent')`
so a re-run of a bulk push doesn't double-enqueue.

**Never store face/photo in `payload`.** There is nothing biometric to push —
the payload is identity only. Enforce with a schema validator that rejects those
keys.

### 1.2 `device_users` — the reconciliation mirror

The device already uploads its own user table via `realtime_enroll_data`. Today
we ack-and-drop those. To reconcile ("who's on the device vs the platform") we
persist the **non-biometric** fields only:

| column | source | notes |
|---|---|---|
| `branch_id`, `dev_id` | resolved | isolation |
| `vendor_user_id` | `userId` | == `Student.rfid_number` |
| `name`, `privilege` | mirror | display / diff |
| `valid_start`, `valid_end` | `vaildStart`/`vaildEnd` (vendor typo) | validity |
| `has_face` | boolean | `True` if the sync carried a template — **the flag only, never the blob** |
| `last_seen_at` | ingest time | staleness |

Upsert on `(dev_id, vendor_user_id)`. This is the only new persistence of
enrollment data, and it is deliberately biometrics-free.

### 1.3 Migration

One Alembic revision creating both tables + indexes + the status enum. This is
PG-only territory (jsonb, partial indexes, native enum) — **run against Postgres
locally**, not just SQLite, before pushing (per `CLAUDE.md`).

---

## Phase 2 — backend layers

Follows the module anatomy (`api → service → repository → model/schema`). New
code lives under `attendance/integrations/biomax/` and the shared attendance
service tree; no new top-level module.

### 2.1 Repository — `repositories/device_command_repo.py`

- `enqueue(commands)` — bulk insert, honouring the idempotency unique index.
- `next_pending(dev_id)` — oldest `pending` for a device, selected
  `FOR UPDATE SKIP LOCKED` so the fast-polling device (a request every few
  seconds) can't grab the same command twice under concurrency.
- `mark_sent / mark_confirmed / mark_failed` — status transitions, bump
  `attempts`, stamp times.
- `requeue_stale_sent(older_than)` — `sent` commands never confirmed get one more
  chance, up to the attempt cap.
- Mirror table repo: `upsert_device_user`, `list_device_users(branch, dev_id)`.

### 2.2 Service — `services/provisioning_service.py`

- `enqueue_students(branch_id, dev_id, student_ids)` — resolve each student's
  `rfid_number`, build the captured create/update payload, enqueue. **Explicit
  set only** — callers pass the student IDs; there is no "push everyone
  automatically" path (see UI note, and `[[feedback_no_blind_bulk_ops]]`).
- `render_dry_run(...)` — build the exact commands **without enqueuing**, and
  diff against `device_users` so the caller sees what *would* change.
- `reconcile(branch_id, dev_id)` — returns three sets: on-platform-not-on-device,
  on-device-not-on-platform, mismatched (name/validity drift).
- `parse_command_result(record)` — Phase-0 result format → confirm/fail a queued
  command. Called from the ingest path when a result-message `request_code`
  arrives.
- `build_payload(student)` — the one place that knows the captured `SET_USER_INFO`
  shape (§0.6): `userId = rfid_number` (student roll no, numeric), `name`,
  `privilege 0`, `card ""`, a wide `vaildStart`/`vaildEnd`. Rejects any biometric
  key by construction, and asserts `userId` is non-empty + numeric.

### 2.3 Emission — the change to `_ack()` in `aidata.py`

This is the whole server→device mechanism and the only edit to the hot path.
Today `_ack()` returns `cmd_code: ""`. The change:

- On each device POST, after the punch/sync is handled and **only if ingest
  succeeded** (unchanged fail-safe ordering — a command must not ride a response
  that also NAKs a punch), call `next_pending(dev_id)`.
- If a command exists, set `cmd_code` (+ its payload, in whatever header/body
  slot Phase 0 showed) and `mark_sent`. Otherwise emit the empty `cmd_code`
  exactly as now.
- **One command per response.** The device polls constantly, so the queue drains
  quickly without batching; one-at-a-time keeps confirmation unambiguous.
- Keep `_ack()` synchronous-looking and side-effect-narrow: it consults the
  queue and marks `sent`, nothing more. The heavy lifting (enqueue, reconcile)
  is out-of-band.

Because emission threads through the same response the ingest fail-safe owns, add
a test that a **500 (ingest failed) never carries a `cmd_code`** — we must not
tell the device to mutate its user table on a response that also asks it to
retry a punch.

### 2.4 Confirmation

When the device's result-message `request_code` (captured in Phase 0) arrives on
`/AIData.aspx`, route it to `parse_command_result`:

- match it to the `sent` command (by echoed `trans_id`/userId — Phase 0 tells us
  which),
- `mark_confirmed` on success, `mark_failed` + `last_error` on device-side
  rejection,
- **cap `attempts`** so a rejected command can't loop forever — the exact trap
  the ingest side hit. A command at the cap goes `failed` and surfaces in the UI,
  never silently retries.

### 2.5 API — `api/routes.py` (attendance module)

All under `/api/v1/attendance/provisioning`, all branch-scoped, all
permission-gated per `docs/coding_rules.md`:

| method | path | purpose |
|---|---|---|
| `GET` | `/reconcile?dev_id=` | the three-way diff |
| `POST` | `/dry-run` | render commands for a student set, no enqueue |
| `POST` | `/push` | enqueue create/update for an explicit `student_ids[]` |
| `GET` | `/commands?dev_id=&status=` | queue view for the UI |
| `POST` | `/commands/{id}/cancel` | pull a still-`pending` command |
| `POST` | `/push-delete` | **separate, explicitly-confirmed** delete path (Phase 5) |

Routes stay HTTP-only — no logic, no DB (enforced by convention).

---

## Phase 3 — frontend

A provisioning surface, reached from the device/attendance admin area, using the
compact `<PageHeader>` (`[[reference_page_header_pattern]]`) with the long
explanation behind the ⓘ `InfoHint`.

- **Reconciliation table** — three tabs/filters (platform-only, device-only,
  drift). Read-only, the safe default landing view.
- **Push flow — explicit selection, never blind.** Checkboxes +
  `use-row-selection` + the shared selection bar (`[[feedback_no_blind_bulk_ops]]`,
  `[[project_academics_bulk_delete]]`); the user picks *which* students and the
  *target device*. No "push all" button.
- **Dry-run first** — the push button opens a dry-run diff ("will create N,
  update M, no deletes") behind `confirm-dialog.tsx` (never `window.confirm`)
  before anything is enqueued.
- **Command status** — per-student pending/sent/confirmed/failed, so a stuck or
  rejected push is visible, not silent.
- Type-safe, tested (vitest + a Playwright happy-path), responsive — per the
  standing frontend agreement (`[[feedback_frontend_workflow]]`).

---

## Phase 4 — safeguards (map to code)

| Safeguard | Where it's enforced |
|---|---|
| Never auto-delete | delete has its own endpoint + explicit confirm; create/update ships first (Phase 5 gates delete) |
| Dry-run | `render_dry_run` + the mandatory diff dialog before `/push` |
| Reconciliation before bulk | `reconcile` is the landing view; bulk push is disabled until a reconcile has run |
| Batch + idempotency | `idempotency_key` unique index; push is resumable and safe to re-run |
| Attempt cap | `attempts` cap in confirmation; capped commands go `failed`, never loop |
| No biometrics | `build_payload` + `payload` validator reject face/photo keys; `device_users` stores `has_face` bool only |
| Branch isolation | `branch_id` on both tables; every query filters it; extend `test_branch_isolation.py` |

---

## Phase 5 — sequencing & flags

1. **Phase 0 capture** (+ BioMax email in parallel). *Gate — do not pass without a
   confirmed format.*
2. **Migration + models + repos**, behind a `BIOMAX_PROVISIONING_ENABLED` flag
   (default off). Emission in `_ack()` is a **no-op while the flag is off** — the
   response is byte-identical to today, so shipping the plumbing can't affect
   live attendance.
3. **Mirror ingestion** — start persisting `device_users` from
   `realtime_enroll_data` (non-biometric fields). Safe on its own; enables
   reconcile.
4. **Reconcile + dry-run API + UI.** Read-only value even before any push works.
5. **Create/update push** for one student, end to end, flag on in staging.
6. **Bulk push**, batched/resumable.
7. **Delete path last**, if wanted at all — separate endpoint, explicit confirm,
   never part of a bulk sweep.

---

## Testing

- **Protocol** (`test_biomax_aidata.py`, extend): `_ack()` emits a queued
  `cmd_code` when one is pending and empty otherwise; a **500 never carries a
  command**; one-command-per-response; a `sent` command isn't re-emitted.
- **Confirmation**: result-message → confirmed/failed; attempt cap trips to
  `failed` and stops.
- **Service**: `build_payload` rejects biometric keys; `enqueue_students` is
  idempotent on re-run; `reconcile` diff correctness.
- **Branch isolation**: commands/mirror for branch A never leak into branch B.
- **No-PII**: assert nothing in `device_commands.payload` or `device_users` can
  hold a face/photo blob.
- CI runs the suite against real Postgres (jsonb, partial indexes, enum) — the
  parts SQLite won't exercise.

---

## Open risks

- **Phase 0 may not yield a format** — then the feature stops; that's an accepted
  outcome, not a failure to engineer around.
- **The device's result-message format** might be thinner than hoped (fire-and-
  forget with no per-command ack). If so, confirmation falls back to reconciling
  against the next `realtime_enroll_data` dump rather than a direct ack — the
  mirror table already gives us that.
- **A second terminal** changes `dev_id` from a constant to a real dimension;
  the queue is keyed on `dev_id` from day one so this is data, not a rewrite.
