# Plan — push students to the BioMax device (Phase 2 provisioning)

Goal: stop staff typing a name and a 10-digit RFID into the terminal for every
student. Instead the platform pushes the identity, and the student only has to
enrol their face.

**Status: not started.** Prerequisite unmet (see §6). Attendance ingest —
device → platform — is already live; this is the reverse direction.

---

## 1. What this can and cannot do

**Can push:** `userId` (= the student's `rfid_number`), `name`, and probably
`privilege` / `timeGroups` / validity dates.

**Cannot push: the face.** A face template is biometric data produced by the
device's own sensor. Nothing in our database can be converted into one, and none
can be generated server-side. **Every student must still stand at the terminal
once.** Any plan that assumes otherwise is wrong.

So the realistic end state is:

> Student walks up → their record is **already on the device** → they enrol their
> face against it → done.

That is still worth building. It removes per-student data entry at the terminal
and, more importantly, removes a whole class of silent failure: a mistyped ID
(`100120002` for `1000120002`) produces `skipped_no_student`, which looks
identical to "nothing happened" and is tedious to trace. Pushing the ID from the
database makes that impossible by construction.

## 2. What we already know

From cracking the ingest protocol (see `docs/biomax-attendance.md`):

- **The channel exists and is identified.** The `cmd_code` response header is how
  the server hands the device a command. We keep it empty today precisely
  because a non-empty value means "server has a command for you".
- **`_ack()` in `aidata.py` owns the entire response**, deliberately. It is the
  only place that needs to change to start emitting commands.
- **We know the device's user-record shape**, because it uploads its own users to
  us in `realtime_enroll_data`: `userId`, `name`, `privilege`, `timeGroups`,
  `vaildStart`, `vaildEnd` (vendor's typo), plus face/photo blobs. A create-user
  command very likely mirrors this minus the biometrics.
- **The device polls constantly** — it POSTs every few seconds, so a command
  queue drains quickly with no push infrastructure needed.

## 3. What we do NOT know — and how to find out

Unknown: the **command vocabulary** — valid `cmd_code` values, the payload
format, and how the device reports a command's result. BioMax publishes no spec.

**Do not guess this.** Unlike the ack (where a wrong value merely meant "not
acknowledged"), these are *write* commands — a wrong guess could delete users or
corrupt the device's table.

**Step 1 — capture it from SmartOffice (the oracle method).** The same technique
that cracked the ack: SmartOffice is BioMax's own server and already speaks this
protocol correctly.

1. Put `aidata-proxy` in **relay mode**: forward the device's POSTs to
   SmartOffice (`103.171.50.109:8080`, reachable from the VPS) and return
   SmartOffice's response verbatim to the device, logging both directions.
2. With the device talking to SmartOffice through us, **add a user in
   SmartOffice's admin UI**.
3. SmartOffice will issue a create-user command in its response — we capture the
   exact `cmd_code` and payload.
4. Repeat for delete-user and any edit, and capture how the device reports the
   result back.

Then take the proxy out of relay mode. This yields a *confirmed* format rather
than a guessed one.

**Fallback:** ask BioMax for the AIData server-command spec. Worth doing in
parallel — it costs nothing but an email.

## 4. Design sketch (after §3 lands)

**Command queue** — one small table, e.g. `device_commands`:

| column | purpose |
|---|---|
| `dev_id` | which terminal |
| `command` / `payload` | what to send |
| `status` | pending / sent / confirmed / failed |
| `sent_at`, `confirmed_at`, `attempts` | delivery tracking |

**Emission** — `_ack()` checks for the oldest pending command for that `dev_id`
and sets `cmd_code` (+ payload) instead of leaving it empty; marks it `sent`.
Everything else about the ack contract stays exactly as-is.

**Confirmation** — parse the device's command-result message (format captured in
§3) and mark `confirmed`/`failed`. Retry `pending` commands that were never
confirmed; **cap attempts** so a rejected command can't loop forever, which is
the same trap the ingest side fell into.

**Source of truth** — students with an `rfid_number` in the target branch.
Enqueue on demand ("push these students to the device"), not automatically on
every student edit, so nobody accidentally rewrites the terminal.

## 5. Safeguards (non-negotiable)

- **Never auto-delete.** A create/update path is safe; a delete path can wipe
  enrolled faces — and faces cannot be restored from our DB, so a bad delete
  means re-enrolling people in person. Ship create/update first; treat delete as
  a separate, explicitly-confirmed action.
- **Dry-run mode** — render the exact commands without sending, and diff against
  the device's own `realtime_enroll_data` uploads so we can see what *would*
  change.
- **Reconciliation view** — the device already tells us its user table. Show
  "on device but not in platform" and vice versa before any bulk push.
- **Batch limits + idempotency** — pushing 1000 students should be resumable and
  safe to re-run.
- **No biometrics stored.** Unchanged: we never persist face/photo blobs.

## 6. Prerequisite — do this first

**Set the device push port to `8099`** and delete `infra/aidata-redirect/`. The
redirect is pinned to a dynamic public IP and fails silently when it changes.
Building a feature on top of a known-fragile transport just makes the eventual
failure harder to diagnose. Five minutes at the device; see
`infra/aidata-redirect/README.md`.

## 7. Sequencing

1. **Port → 8099**, retire the redirect. *(prerequisite)*
2. **Capture the command format** via the SmartOffice oracle (§3). Timeboxed —
   if it doesn't yield a clean answer, escalate to BioMax rather than guessing.
3. **Queue + emission + confirmation**, create/update only, behind a flag.
4. **Reconciliation + dry-run UI**, then a real push for one student.
5. **Bulk push**, batched and resumable.
6. Delete path last, if wanted at all.

Steps 3–6 are ordinary work. **Step 2 is the only genuine unknown**, and it
decides whether this is buildable at all — so do it before promising a date.
