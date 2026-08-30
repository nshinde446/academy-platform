# BioMax cross-device face re-enrollment — spec

Status: **proposed** · Owner: attendance/biomax · Depends on: PR #71 (encrypted
biometric backup), #72 (backfill + restore), #73 (per-student face photo).

## 1. Why this exists

The original terminal **AMDB26013800122** died from a hardware fault. Before it
died the real-time backup had drained only **191 of ~854** enrolled faces into
`device_user_biometric` (encrypted, keyed by that device's `dev_id`). Its
replacement **AMDB25083200131** came pre-loaded and a `scope=all` backfill
captured **554** faces there.

Three cohorts of students fall out of this:

| Cohort | Where the face is | Count (approx) | Path |
|---|---|---|---|
| **A — restorable** | backed up from the OLD device only | ~191 minus overlap | **cross-device restore** (this spec, automatable) |
| **B — already good** | present on the NEW device (and backed up) | ~554 | nothing to do |
| **C — truly gone** | on neither backup (old device died first) | **~476** | **physical re-enrollment** at the terminal (worklist) |

Cohort A is the automatable win. Cohort C cannot be automated — no template
exists anywhere — but we can make it a tight, trackable worklist instead of a
guess.

## 2. Root cause: restore is single-device by construction

Today's restore (`provisioning_service.enqueue_restore`) is bound to one
`dev_id` in two spots:

1. **Enqueue** — `list_backed_up_users(session, branch_id, dev_id)` lists users
   backed up *for that device*, and `build_restore_command_row(..., dev_id, ...)`
   queues the command **on that same device**.
2. **Emit** — `build_restore_emit_payload` fetches the template with
   `get_biometric(session, dev_id, uid)`, i.e. keyed to the **target** device.

So a restore aimed at the new device finds *its own* backups (cohort B) and
never sees the old device's rows (cohort A). We need to decouple **source**
(where the template is read from) from **target** (which device the command is
queued for and drains it).

## 3. Hard prerequisite: template portability pilot

**Assumption to prove before any bulk push:** a face template captured on
AMDB26013800122 is accepted and matches on AMDB25083200131. Both are BioMax
AIFace R6, so the enrollment algorithm *should* be identical and templates
portable (this is how vendor multi-device sync works) — but we do not ship a
476-command bulk on an unverified assumption.

**Pilot (blocking gate for §5):**
1. Pick **3–5 cohort-A students** who are physically reachable.
2. Cross-device restore *only those* (the same code path, tiny set).
3. Have each punch at the new terminal; confirm a real face match (not just that
   the user row was created).
4. If matches succeed → proceed to bulk. If they fail → templates are
   device-bound; cohort A collapses into cohort C (manual), and we ship only the
   worklist half of this spec.

The design below makes the pilot and the bulk the **same** operation on a
different student set, so the pilot costs nothing extra.

## 4. Design — decouple source from target

Backward-compatible: when `source_dev_id` is omitted it equals `dev_id` and
behaviour is byte-identical to today's same-device restore.

### 4.1 Repository (`device_command_repo.py`)
- `list_backed_up_users(session, branch_id, dev_id)` → already parameterised by
  `dev_id`; call it with the **source** device. No change.
- `get_biometric(session, dev_id, vendor_user_id)` → already parameterised. The
  change is *who calls it with what* (emit reads the source), not the function.

### 4.2 Service (`provisioning_service.py`)
- `build_restore_command_row(branch_id, target_dev_id, uid, name, *, source_dev_id)`
  — carry the source in the stored payload so emit knows where to read:
  ```python
  "payload": {"users": [user], "restore_biometrics": True,
              "restore_source_dev_id": source_dev_id},
  "idempotency_key": f"{target_dev_id}:RESTORE:{source_dev_id}:{nonce}",
  ```
- New `enqueue_cross_device_restore(session, branch_id, *, source_dev_id, target_dev_id, only_missing=True)`:
  - `rows_src = list_backed_up_users(session, branch_id, source_dev_id)`
  - When `only_missing` (default), **subtract** userIds that already have a face
    on the target (from the target's `device_user` mirror where `has_face`),
    so we never re-push cohort B. This makes re-runs cheap and idempotent.
  - Build rows with `target_dev_id` + `source_dev_id`; `enqueue`.
  - Keep the existing `enqueue_restore` as a thin wrapper:
    `enqueue_cross_device_restore(source=dev_id, target=dev_id, only_missing=False)`.
- `build_restore_emit_payload` — read the source from the payload:
  ```python
  source = payload.pop("restore_source_dev_id", None) or dev_id
  bio_row = await device_command_repo.get_biometric(session, source, uid)
  ```
  Everything else (deep copy, decrypt face/photo/fps, degrade to identity-only if
  the key/backup is missing) is unchanged.

### 4.3 Route (`provisioning_routes.py`)
Extend the existing token-authed `POST /restore`:
```
POST /attendance/provisioning/restore?dev_id=<target>&source_dev_id=<old>&only_missing=true
```
- `source_dev_id` optional (defaults to `dev_id`); both must pass
  `_require_known_device` — so the **old serial stays a configured device** even
  though it's dead (it already is, from the two-device registration).
- Same gates as today: `_verify_sync_token`, `_require_biometric_key`.
- Response `RestoreResponse` gains `source_dev_id` + `commands_enqueued`. Add a
  `skipped_already_present` count so the operator sees cohort B was excluded.

### 4.4 Emit path & queue
No new mechanism — cross-device restore commands are ordinary `SET_USER_INFO`
rows on the target's queue. The device drains them on its poll exactly like a
same-device restore. The real-time backup then captures these faces **under the
new dev_id**, so after the device confirms them, cohort A becomes cohort B and a
re-run enqueues nothing.

## 5. Cohort C — the physical re-enrollment worklist

For the ~476 with no template anywhere, the deliverable is **knowing exactly who**
and tracking it down, not automation.

- **Read model** — a "needs face re-enrollment" list = platform students with a
  valid numeric RFID **minus** (has-face-on-target ∪ has-restorable-backup).
  This is `reconcile.awaiting_face_enrollment` refined by removing anyone cohort
  A can still cover. Add `provisioning_service.reenrollment_worklist(branch_id, dev_id)`.
- **Endpoint** — `GET /attendance/provisioning/reenrollment-worklist?dev_id=` →
  rows `{student_id, name, enrollment_number, batch_name, rfid}` (admin-gated).
- **UI** — a card on the **Device sync** page (and/or an export) listing the
  students to call in, with the shared row-selection + CSV export already used
  elsewhere. No blind bulk action — it's a call list, per the working agreement.
- **Progress** — the same list shrinks automatically as students enroll and the
  device mirrors `has_face=true` back, so it doubles as a burn-down.

## 6. Safety, idempotency, correctness

- **Branch isolation** — every query filters `branch_id`; both devices are in the
  same branch. Extend `tests/test_branch_isolation.py` if a new query is added.
- **Idempotency** — `only_missing` + the source-scoped idempotency key mean
  re-running restore is safe and converges; in-flight `sent` commands are already
  skipped by the push dedup.
- **No plaintext at rest** — templates are decrypted and injected only at emit
  time (unchanged); the cross-device change moves *which* row is read, not when
  it's decrypted.
- **Dead-device hygiene** — the old serial must remain configured (allow-listed)
  for `_require_known_device` to accept it as a source, but it will never poll,
  so nothing is ever queued *to* it. Document this so it isn't "cleaned up".
- **Duplicate-subject landmine** — N/A here (no subject filtering).

## 7. Testing

- `enqueue_cross_device_restore` queues on the **target** with `source_dev_id` in
  the payload; excludes userIds already faced on the target when `only_missing`.
- `build_restore_emit_payload` reads the template from the **source** device and
  injects face/photo/fps; degrades to identity-only when the source row is
  absent.
- Same-device wrapper (`enqueue_restore`) still behaves as before (regression).
- `reenrollment_worklist` excludes cohort A (restorable) and cohort B (already
  faced), includes only cohort C.
- Route: `source_dev_id` defaulting, unknown-source rejection, token/key gates.

## 8. Rollout

1. Ship §4 + §5 behind the existing provisioning flag (no migration — reuses
   `device_user_biometric` and the command queue).
2. **Pilot** (§3) on 3–5 reachable cohort-A students; verify real face matches.
3. If the pilot passes → bulk cross-device restore (`only_missing=true`), watch
   the queue drain, confirm backups re-appear under the new dev_id.
4. Publish the cohort-C worklist; staff work the call list down.
5. If the pilot fails → skip step 3; cohort A folds into the worklist.

## 9. Task list

- **X1** repo/service: `source_dev_id` plumbing + `enqueue_cross_device_restore`
  + `only_missing` exclusion; keep `enqueue_restore` as wrapper.
- **X2** emit: read `restore_source_dev_id` from payload in
  `build_restore_emit_payload`.
- **X3** route: `source_dev_id` + `only_missing` params on `POST /restore`;
  `RestoreResponse` gains `source_dev_id` + `skipped_already_present`.
- **X4** worklist: `reenrollment_worklist` service + `GET /reenrollment-worklist`
  + Device-sync card/export.
- **X5** tests (§7) + branch-isolation extension.
- **X6** pilot run + go/no-go on bulk.

**Open decision for the operator:** trigger cross-device restore via the
existing **headless token endpoint** (scriptable, matches DR tooling) or add an
explicit **admin UI button** on Device sync. Recommendation: reuse the token
endpoint for the bulk (it's a one-off migration-style action) and expose only
the **worklist** in the UI, where it has ongoing value.
