# Biometric Attendance — Design & Roadmap

Status: **Design approved 2026-06-28, build pending.** Source of truth for the
biometric/day-attendance work. Supersedes the lecture-only attendance behaviour
in `app/modules/attendance`.

---

## 1. Problem & reference material

Two real exports from the institute's current (Edofox-style) face-punch system
define the target behaviour. Both are batch **25-27 CET**.

### Reference A — per-student timeline (`Aryan Parte Performance.xlsx`)
One student × many days. Columns: `Session Date`, `Conducted at`
(real punch timestamp), `Session Status` ∈ {`IN`, `OUT`, `Absent`}.

Observed truths:
- A day's **first punch → `IN`** (sign-in). Punch times range 08:15–11:39; all
  count as present.
- A day's **last punch → `OUT`** (sign-off). Appears on **only 1 of 25 days**
  (Jun 22: `09:29 IN` + `14:24 OUT`).
- **No punch all day → `Absent`**, written by an end-of-day sweep at `23:30:07`.
- **"Missed to punch out" is the norm** (24/25 days), not an error.

### Reference B — classroom day register (`Attendance Report … Edofox … .xlsx`)
One day (2026-06-26) × ~150 students. Columns: `Sr.No`, `Student Name`,
`Roll No`, `Mobile No`, `Parent Mobile No`, and a single status column headed
**`25-27 CET 07:00 - 15:00`** with values **`P` / `A`**.

Observed truths:
- The **campus day window is 07:00–15:00** (distinct from the 10:00 lecture
  start). Punches are attributed to the day from 07:00; sign-off closes by 15:00.
- The population view collapses the timeline to a single **P/A** per student.

**Conclusion:** A and B are two projections of one underlying fact — *one row
per student per day*. That row is the missing primitive.

### Formalized rules (confirmed with stakeholder 2026-06-28)
- **Day-scoped, whole population.** Compute one attendance fact per active
  student per local day from punches alone, irrespective of scheduled lectures.
- **Sign-in** = first punch of the local day within the campus window.
  - On-time `PRESENT` if `first_in ≤ lecture_start + grace` (10:00 + 10 min).
  - else `LATE`. Early punches (pre-09:00) still count as present.
- **Sign-off** = last punch of the day. If only one punch exists →
  `signoff = MISSING` (info flag, **not** a blocking exception).
- **Absent** = zero punches in the day window → materialized by a nightly sweep.
- **Then** project the day fact onto each scheduled lecture (Layer 2).

---

## 1b. Confirmed decisions (stakeholder, 2026-06-28)

These are binding; the design below conforms to them.

| # | Item | Decision |
|---|------|----------|
| 1 | **Working day** | Any of the 7 weekdays (Mon–Sun) that has **≥1 scheduled lecture for that student**. This is the denominator for attendance %. A day with no scheduled lecture is *not* a working day (even if the student punched in). |
| 2 | **Lecture records** | Create an `attendance_records` row for **every scheduled lecture**, present *and* absent — no implicit absences. |
| 3 | **Active students** | All students **enrolled in the branch for the current academic session**. |
| 4 | **Timezone** | **Stored per branch** (`branch.timezone`), default `Asia/Kolkata`. All day-bucketing uses the punch's branch tz. |
| 5 | **Parent notifications** | Send a notification for **every student marked `ABSENT` by the daily sweep**. |
| 6 | **Late grace** | On-time cutoff is **10:10 local** (10:00 + 10 min). |
| 7 | **Manual overrides** | **Never** overwritten by automated rebuilds/sweeps. |

### Daily workflow (end to end)

1. **Punches arrive** (webhook/poll) → `raw_punch_logs` (+`direction`), deduped.
2. **On ingest** → enqueue `rebuild_daily(student, today)` → upsert the student's
   `daily_attendance` row (first_in / last_out / status / signoff). Decision 7:
   skip if the row is a `MANUAL` override.
3. **Nightly sweep** at branch-local 23:30:
   a. `run_absent_sweep` → write `ABSENT/SYSTEM` for every **active** student
      (decision 3) with no row that day **that had ≥1 scheduled lecture**
      (decision 1).
   b. For each sweep-`ABSENT` student → **emit parent notification** (decision 5).
4. **Lecture projection** (decision 2): for every scheduled lecture that day,
   upsert an `attendance_records` row (PRESENT/LATE/ABSENT) by projecting the
   day fact onto the lecture window — manual marks win (decision 7).
5. **Reports** read from Layer 1; monthly % = `present_working_days /
   working_days` where working_days follows decision 1.

## 2. Architecture — two layers

```
 raw_punch_logs (+direction)         <-- vendor ingest (BioMax/Edofox), unchanged shape + direction
        │  aggregate by (student, LOCAL day)
        ▼
 daily_attendance   ── Layer 1 ──    <-- NEW. Population campus presence. Files A & B both render from this.
        │  project onto lecture [start,end] windows
        ▼
 attendance_records ── Layer 2 ──    <-- EXISTING. Per-lecture. Now DERIVED from Layer 1, manual overrides win.
```

**Layer 1 is canonical** for a student's daily attendance %. Per-lecture records
are derived by window-overlap. (Stakeholder decision: "Campus day, lectures
projected.")

### 2.1 New table — `daily_attendance`

```python
class DailyAttendance(BaseModel):
    __tablename__ = "daily_attendance"
    student_id:      Mapped[UUID]            # FK students.id
    branch_id:       Mapped[UUID]            # FK branch.id
    attendance_date: Mapped[date]            # LOCAL date (Asia/Kolkata), not UTC
    first_in:        Mapped[datetime | None] # tz-aware; NULL when absent
    last_out:        Mapped[datetime | None] # tz-aware; NULL when missing/absent
    status:          Mapped[str]             # PRESENT | LATE | ABSENT
    signoff:         Mapped[str]             # COMPLETE | MISSING | NA(absent)
    source:          Mapped[str]             # BIOMETRIC | MANUAL | SYSTEM
    override_by:     Mapped[UUID | None]     # set when a human edits
    override_at:     Mapped[datetime | None]
    # UNIQUE(student_id, attendance_date)
```

- `UNIQUE(student_id, attendance_date)` makes the aggregator an idempotent upsert.
- `source=SYSTEM` ⇒ written by the absent sweep. `MANUAL` ⇒ human override; a
  rebuild must **never** clobber a `MANUAL` row.

### 2.2 `RawPunchLog` — add direction
`PunchEvent.direction` is parsed today (`biomax/schemas.py`) but dropped on
write. Add a nullable `direction: str | None` column and persist it in
`ingest_punches`. When the device omits direction, the aggregator infers it
(first = IN, last = OUT).

### 2.3 Timezone — per branch (highest-risk correctness item)
- **Stored per branch**: add `branch.timezone: str` (default `Asia/Kolkata`)
  rather than a single global setting — branches may differ later. A
  `DEFAULT_TIMEZONE = "Asia/Kolkata"` constant backs new/unset branches.
- **All day-bucketing logic** (`attendance_date`, "first punch of the day", the
  nightly sweep boundary) computes in **that branch's local time**, then stores
  tz-aware UTC instants for `first_in`/`last_out`. A 09:29 IST punch is 04:00
  UTC — bucketing in UTC would push boundary punches to the wrong day.
- Campus window bounds (`07:00`, `15:00`) and lecture start (`10:00`) are
  **local** wall-clock; resolve against `attendance_date` in the branch tz.
- The nightly beat must fire per-branch at *that branch's* local 23:30.

---

## 3. Layer 1 aggregator

`rebuild_daily(session, student_id, local_date) -> DailyAttendance`

1. Resolve `[day_start, day_end)` = `local_date` 00:00–24:00 in `TIMEZONE`
   (campus window 07:00–15:00 used for status thresholds, not for clipping —
   keep raw first/last so an early/late punch is still visible).
2. Load that student's punches in the window, ordered.
3. `first_in = min(ts)`, `last_out = max(ts)` (NULL if only one punch).
4. `status` = PRESENT if `first_in ≤ local(10:00)+grace` else LATE.
5. `signoff` = COMPLETE if a distinct later punch exists, else MISSING.
6. Upsert by `(student_id, attendance_date)`; **skip if existing.source==MANUAL**.

`run_absent_sweep(session, branch_id, local_date)` — for every active student in
the branch with **no** `daily_attendance` row for that date, insert
`status=ABSENT, signoff=NA, source=SYSTEM, first_in=last_out=NULL`. This is the
23:30 job from Reference A.

### Scheduler (Celery — currently un-wired)
Celery is installed but there is **no app factory / beat / worker**. Stand up:
- `app/core/jobs/celery_app.py` — `Celery(...)` with `beat_schedule`.
- Nightly beat at branch-local 23:30 → `run_absent_sweep` for each branch +
  `rebuild_daily` for students who punched that day.
- Near-real-time: on punch ingest, enqueue `rebuild_daily(student, today)` so
  the register reflects punches within seconds.

---

## 4. Layer 2 — projecting onto lectures

For lecture `L[start,end]` and a student's `DailyAttendance` D on that date:

- Treat `D.last_out` as `end-of-campus-window` when `signoff==MISSING`
  (student presumed on campus through close — matches Reference A intent).
- Present iff presence interval `[first_in, effective_out]` **overlaps**
  `[start, end]`. PRESENT if `first_in ≤ start + grace`, else LATE. No overlap
  or `status==ABSENT` ⇒ ABSENT.
- **Precedence: `MANUAL_OVERRIDE` > `BIOMETRIC` (projected) > `SYSTEM` (absent).**
  A teacher's manual mark on `attendance_records` always wins and is never
  overwritten by a re-projection.

This **replaces** the current `process_raw_punches` first-punch-only logic
(`attendance_service.py:113`), which is lecture-gated, window-relative, and
models neither sign-off nor missing-out.

### 4b. Compatibility with the existing per-lecture view (NON-NEGOTIABLE)

The current product already answers "does candidate X in batch Y hold an
attendance status for this lecture?" via per-lecture `attendance_records`. The
new layer must **fulfil and feed that exact logic, never bypass it.** Hard
invariants the build must preserve:

- **Same table, same key.** Layer 2 writes `attendance_records` keyed by
  `(student_id, lecture_id)` — no new per-lecture table. The new
  `daily_attendance` is purely upstream.
- **Same read endpoints, unchanged response shape.**
  `GET /attendance/lecture/{lecture_id}` and `GET /attendance/student/{id}`
  keep returning `AttendanceRecordResponse[]` exactly as today. The frontend
  `useLectureAttendance` / `/attendance` page need **zero changes** to keep
  working; rows are now *auto-populated* instead of only hand-marked.
- **Same status & source vocabulary.** Layer 2 emits only the existing
  `VALID_ATTENDANCE_STATUSES` (PRESENT/LATE/ABSENT) and `VALID_SOURCES`
  (BIOMETRIC/SYSTEM). The day-level IN/OUT/signoff vocabulary lives **only** in
  `daily_attendance` and never appears in `attendance_records`.
- **Manual still wins.** A row written by `mark_attendance` (source=MANUAL /
  MANUAL_OVERRIDE) is never overwritten by projection or sweep (decision 7),
  mirroring today's `process_raw_punches` "skip already-marked" behaviour.
- **Existing routes stay.** `POST /attendance/process/{lecture_id}` keeps its
  route + response; its body is re-implemented to delegate to
  `project_day_onto_lecture` so the current "Process biometric punches" button
  is unchanged for the user. New endpoints are additive only.

Net: B1–B9 add a population day-attendance layer *beneath* the lecture view and
make the existing rows fill in automatically — they do not alter the contract the
current screens rely on.

---

## 5. Reports (both reference files, from Layer 1)

1. **Student day-timeline** (Reference A): student × date rows →
   `Date | In | Out | Status | Signoff`. CSV + on-screen.
2. **Classroom day register** (Reference B): batch + date → roster with
   `P/A` + `In/Out`. CSV + on-screen, header `<batch> 07:00 - 15:00`.
3. **Monthly %**: per student, `present_days / working_days` over a range —
   the canonical attendance figure, sourced from Layer 1.

---

## 6. Build plan (incremental, test-driven)

| # | Task | Notes |
|---|------|-------|
| B1 | `branch.timezone` column (default Asia/Kolkata) + per-branch local-day helpers (`local_date_of`, `day_bounds`) | unit-tested; unblocks everything (decision 4) |
| B2 | `RawPunchLog.direction` column + persist in `ingest_punches` | migration 0042 |
| B3 | `daily_attendance` table + model + migration | UNIQUE(student, date) |
| B4 | `rebuild_daily` aggregator + tests | idempotent; MANUAL-safe; status/signoff matrix |
| B5 | `run_absent_sweep` (active=enrolled-this-session, only days with ≥1 scheduled lecture) + **parent-notify each sweep-ABSENT** + tests | decisions 1, 3, 5 |
| B6 | Celery app factory + beat (per-branch-local 23:30 sweep, on-ingest rebuild) | the missing infra (decision 4) |
| B7 | Layer 2 projection `project_day_onto_lecture` — **one record per scheduled lecture, present & absent** + precedence + tests | replaces `process_raw_punches` core (decisions 2, 7) |
| B8 | Reports: student timeline + classroom register + monthly % (working_days = days with ≥1 scheduled lecture) (API) | derive from Layer 1 (decision 1) |
| B9 | Frontend: register grid (P/A), student timeline, month % | per existing /attendance UI |

Ship B1–B5 first (population day attendance stands alone and renders both
reference files); B6 makes it live; B7–B9 wire lectures + UI.

---

## 7. Open / deferred
- **Half-day**: not modeled (reference is binary P/A). Could derive from
  `last_out − first_in < N hours` later if the institute wants it.
- **Multi-branch sweep timing**: beat runs per branch-local 23:30 using
  `branch.timezone`; already supports branches in different timezones.
- **Vendor direction reliability**: store when present, infer otherwise; revisit
  once BioMax docs confirm IN/OUT semantics (see `misc/biomax-integration-email.md`).

---

## 8. Device integrations (built 2026-06-29)

Two client-owned products feed the pipeline. Both converge on one funnel —
`PunchEvent` → `ingest_punches()` (rfid_number match + 5s dedup) →
`RawPunchLog` → `rebuild_after_ingest()` → `DailyAttendance` (Layer 1) → lecture
projection (Layer 2). Neither feeder changes anything downstream.

### eTimeOffice / TeamOffice — cloud, PULL
Hosted SaaS; punches live in their cloud, so we poll their REST API.
- `integrations/etimeoffice/client.py` — `fetch_punch_data` (GET
  `{ETO_BASE_URL}/DownloadInOutPunchData?Empcode=ALL&FromDate&ToDate`, colon-joined
  `Authorization: corp:user:pass`). Field casing must be confirmed against the
  client's API panel — isolated as constants.
- `integrations/etimeoffice/service.py` — `rows_to_events` (Empcode→rfid_number,
  IN/OUT local times → tz-aware UTC PunchEvents), `sync_range`, `sync_recent`.
- Celery beat `attendance.etimeoffice_poll` every 10 min (no-op unless
  `ETO_ENABLED` + `ETO_BRANCH_ID`). Manual `POST /api/v1/attendance/etimeoffice/pull`.
- Config: `ETO_ENABLED, ETO_BASE_URL, ETO_CORP_ID, ETO_USERNAME, ETO_PASSWORD,
  ETO_LOOKBACK_DAYS, ETO_BRANCH_ID`.

### BioMax SmartOffice — on-prem, PUSH (iclock/ADMS)
Devices are ZKTeco-based and push punches in real time over the iclock protocol.
- `integrations/biomax/iclock.py` — `GET /iclock/cdata` handshake (Realtime=1),
  `POST /iclock/cdata` ATTLOG ingest (tab-separated `PIN\ttime\tstatus`),
  `GET /iclock/getrequest` command stub. Mounted with **no** `/api/v1` prefix;
  frontend `next.config.ts` proxies `/iclock/*` to the backend.
- Trust: serial allowlist `BIOMAX_DEVICE_SERIALS`; punches attributed to
  `BIOMAX_BRANCH_ID`. Unknown serial → 401. ATTLOG times are device-local → UTC.
- Device setup surfaced in the **Integrations** admin page (`/integrations`):
  push URL + copy, serial/branch env reminders, eTimeOffice status + "Pull now".

### Enrollment contract
Both match the device user id to `Student.rfid_number`. Aligning enrollment
numbers / device PINs to `rfid_number` is the one manual step per student.
