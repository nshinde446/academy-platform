# BioMax attendance (AIData push) — how it works

How the physical **BioMax R6** face terminal feeds attendance into this platform,
end to end. A student scans their face at the device; a few seconds later the row
appears on `/attendance`. No PC, no SmartOffice, no manual pull.

```
 BioMax R6         POST /AIData.aspx      aidata-proxy        FastAPI            Postgres
 (on the wall) ──────────────────────►  (port 8099)  ──────► aidata.py ──► raw_punch_logs
  face scan        plain HTTP :8099      speaks the         (allowlist)         │
                                         device dialect          │              │
                                              ▲                  └─ rebuild_after_ingest
                                              │                                 │
                                     acks only after the app          daily_attendance
                                     confirms it stored it                      │
                                                                  /attendance (auto-refresh)
```

**Why the proxy exists:** the device acks on case-sensitive response headers,
and Caddy (Go) canonicalises header keys (`response_code` → `Response_code`),
which the device rejects. Go offers no way to emit a non-canonical key, so the
terminal cannot be served through Caddy. `infra/aidata-proxy/` is a small
stdlib-only service on its own port that speaks the device's dialect verbatim
and forwards to the app. It serves **only** `/AIData.aspx`, so the rest of the
API is never exposed over plain HTTP, and it runs as a compose service
(`restart: unless-stopped`) so it survives crashes and reboots.

> **Which doc do I want?**
> This one — the R6 speaks BioMax's proprietary **AIData** protocol.
> `biomax-direct-push-setup.md` covers the *different* ZKTeco/ADMS `iclock`
> protocol (Multibio-900 and similar). They are not interchangeable: an R6 will
> never talk to `/iclock`, and a ZK device will never talk to `/AIData.aspx`.
> Both receivers are mounted, so either device type can be pointed at us.

---

## 1. The AIData protocol

There is **no public spec**. This was reverse-engineered by replaying captured
records against BioMax's own SmartOffice receiver and reading what it returned.
Everything below is verified against a live device.

### Request (device → us)

```
POST /AIData.aspx HTTP/1.0
User-Agent: Mozilla/4.0
Content-Type: application/json
request_code: realtime_glog
trans_id: RTLogSend
dev_id: AMDB26013800122
dev_model: R6

{"userId":"1000120001","name":"Nitin","time":"20260720213000",
 "inOut":"IN","ioMode":10,"doorMode":"open","verifyMode":"Face",
 "workCode":1,"logPhoto":"<base64 jpeg>"}
```

`request_code` names the message. Three are seen in the wild:

| `request_code` | `trans_id` | Meaning | What we do |
|---|---|---|---|
| `realtime_glog` | `RTLogSend` | a punch | parse + ingest |
| `realtime_enroll_data` | `RTEnrollData` | user/face mirror | ack, ignore |
| `realtime_door_status` | — | door state ping | ack, ignore |

Field notes:

- **`userId` is matched against `Student.rfid_number`.** Unknown ⇒ the punch is
  counted as `skipped_no_student` and **nothing is written**.
- **`time` is `YYYYMMDDHHMMSS` in the device's local wall-clock** (branch
  timezone, i.e. IST). We convert to tz-aware UTC on the way in.
- `inOut` is stored for reference only. Classification uses punch *ordering*
  (first/last), so an all-`IN` device still works correctly.
- `face`, `photo`, `logPhoto` are **biometric PII and are never persisted**. We
  log key names only, never the blobs.

### Response (us → device) — ⚠️ the critical part

**The ack lives entirely in HTTP response headers. The device never reads the
body.** Getting this wrong does not fail loudly — the device silently re-uploads
its whole database every ~4 seconds forever and never reports live scans.

```
HTTP/1.1 200 OK
Content-Type: application/octet-stream
response_code: OK
cmd_code:
trans_id:
                      <- empty body
```

| Header | Value | Why |
|---|---|---|
| `response_code` | `OK` | the ack — device marks the record delivered, deletes it, advances |
| `cmd_code` | **empty** | non-empty = "server has a command for you" |
| `trans_id` | **empty** | same — **echoing the request's `trans_id` back breaks it** |

Two failure modes worth burning into memory:

1. **Ack in the body** (e.g. returning the text `OK`) — device ignores it and
   loops forever. Ten different body formats were tested against the live
   device; none work. It is headers or nothing.
2. **Echoing `trans_id`** — the device reads it as a pending command, re-syncs
   its entire database instead of clearing its log, and head-of-line blocks
   every real punch behind it.

An unrecognised `request_code` yields `response_code: ERROR_INVLAID_REQUEST_CODE`
(the vendor's typo, not ours).

### Fail-safe: never ack what we didn't store

If ingest raises, we return **HTTP 500 and no ack**, so the device *retains* the
punch and retries. This matters because the device deletes its only copy on ack —
acking first meant any outage (including a routine deploy) lost punches
permanently. Conversely, records we *can't* use (blank `userId`, unparseable
time, enrollment syncs) are **acked and discarded**: refusing them would make the
device retry them forever and block real punches behind them.

---

## 2. Where the code lives

| Thing | Path |
|---|---|
| Receiver | `backend/app/modules/attendance/integrations/biomax/aidata.py` |
| Ack contract | `_ack()` in the same file |
| Router mount (no `/api/v1` prefix) | `backend/app/main.py` |
| Device allowlist / branch resolution | reused from `iclock.py` |
| Ingest → day rebuild | `biomax/service.py` → `attendance/services/daily_service.py` |
| Tests | `backend/tests/test_biomax_aidata.py` |
| Edge routing | `infra/nginx/caddy-academy.snippet` |

**Env vars** (in `.env.prod` on the server):

```
BIOMAX_DEVICE_SERIALS=AMDB26013800122     # comma-separated allowlist of dev_id
BIOMAX_BRANCH_ID=00000000-0000-0000-0000-000000000001
```

A `dev_id` outside the allowlist gets **401** — fail-safe by default.

---

## 3. Device configuration

The R6 has no "domain name" field (IP only) and won't do TLS to a bare IP, so it
pushes **plain HTTP on port 80** to the server's IP. Caddy routes only the device
endpoints to the backend; trust comes from the `dev_id` allowlist, not the
network. The payload is just an ID + timestamp.

**Menu → Comm / Network → Push Settings:**

| Setting | Value |
|---|---|
| Server / Push IP | `116.203.116.141` |
| Port | **`8099`** (the `aidata-proxy` port — **not** 80) |
| HTTPS / SSL | **OFF** |
| Real-time | **ON** |
| Cloud ID | `AMDB26013800122` (hardware, don't change) |

Port `8099` matters: on port 80 the device is served by Caddy, whose header
canonicalisation breaks the ack and leaves the terminal re-uploading forever.

Also required:

- **WiFi connected** — the device must show an IP (e.g. `192.168.1.x`). A factory
  reset wipes WiFi credentials; re-enter them or nothing is sent.
- **Clock set to current IST** — punches are stamped with the device clock.

### Enrolling a person — the one rule that matters

> **The device's User ID must exactly equal that student's `rfid_number`.**

That string is the only link between a face and a student. Enrolment steps:

1. **User → Add User**
2. **User ID** = the student's `rfid_number`, exactly (e.g. `1000120001` — ten
   digits; a single missing zero silently produces `skipped_no_student`)
3. Select **Face** and hold still until it confirms a successful capture —
   entering an ID without capturing a face saves nothing usable
4. Save, then confirm the user appears in the user list
5. Scan once — the screen should show the name/ID, not "not registered"

**Face templates cannot be pushed from the database.** They only exist on the
device, so every student must physically enrol their face once. The server can
(eventually) push *identities*; it can never push *faces*.

---

## 4. From punch to attendance row

Punches land in `raw_punch_logs`, then `rebuild_after_ingest` derives the day:

- **`first_in`** — earliest punch of the local day; **`last_out`** — latest.
- **`day_status`** — `PRESENT`, or `LATE` if `first_in` is past the grace cutoff
  (10:10 by default), or `ABSENT` via the nightly sweep if no punch exists.
- **`signoff`** — `COMPLETE` when both an in and a later out exist; `MISSING`
  when someone scanned in but never out (an **informational flag, not an
  exception** — a single scan still counts as present).
- Re-sends are **de-duplicated**, so the device's retries are harmless.
- **Manual marks always win** — rebuilds and sweeps never overwrite them.

Times are bucketed in the **branch timezone** (`branch.timezone`, default
`Asia/Kolkata`), never UTC, so a 23:30 punch lands on the right calendar day.

---

## 5. Verifying and operating

Watch punches arrive (on the server):

```bash
docker logs --since 5m academy-prod-backend-1 2>&1 | grep -i "AIData"
```

A healthy live punch looks like:

```
AIData realtime_glog from AMDB26013800122: keys=[...] userId='1000120001' time='20260720213000'
AIData punch 1000120001@2026-07-20 16:00:00+00:00 -> inserted=1 skipped_no_student=0
```

Check today's rows:

```sql
SELECT s.first_name, s.rfid_number, d.day_status, d.first_in, d.last_out, d.signoff
FROM daily_attendance d JOIN students s ON s.id = d.student_id
WHERE d.attendance_date = CURRENT_DATE AND d.first_in IS NOT NULL
ORDER BY d.first_in;
```

### Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `skipped_no_student=1` | device User ID ≠ any `rfid_number` | fix the User ID on the device (count the digits) |
| Device re-sends the same record every ~4s forever | ack wrong — body instead of headers, or non-empty `trans_id`/`cmd_code` | return the exact headers in §1 |
| Punches arrive but `time` is an old date | device clock wrong | set date/time to current IST |
| `userId` empty on punches | face enrolled without a User ID, or its user was deleted | re-enrol with a numeric User ID |
| Nothing arrives at all, no connection attempts | device offline (WiFi wiped by factory reset) or push disabled | reconnect WiFi, re-enable Push |
| `401` on every request | `dev_id` not in `BIOMAX_DEVICE_SERIALS` | add it, recreate the backend |
| Scans stop right after a factory reset | reset re-enabled HTTPS / cleared push settings | re-apply the table in §3 |

A device that can't deliver **keeps its punches and retries**, so connectivity
outages delay data, they don't lose it.

---

## 6. Limits and what's next

- **Enrolment is manual, at the device.** Faces can't come from the database.
- **Phase 2 — server → device provisioning** (push a student's ID/name so staff
  don't type them) rides the **`cmd_code`** response header. The channel is
  identified and `_ack()` is deliberately the single place that owns the
  response, but the command vocabulary is still unknown — it can be captured
  from SmartOffice the same way the ack was.
- **Header case is settled — the device IS case-sensitive.** Routing it through
  Caddy was tried and reproducibly re-loops: HTTP headers are case-insensitive
  per spec, but this firmware is not. Hence `aidata-proxy` and port `8099`.
  If you ever point the device back at port 80, attendance will silently stall.
- **One branch.** `BIOMAX_BRANCH_ID` is a single value; multi-branch needs a
  per-`dev_id` → branch map.
