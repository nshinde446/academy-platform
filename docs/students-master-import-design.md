# Students Master Import — Design (Academics auto-population)

Status: **design / not implemented**. No prod or DB changes. The student
import becomes the single source of truth that builds the Academics tabs
(Courses, Batches, Academic Years, Subjects) bottom-up, with no tangled
data.

Related: builds on the import preview + create-missing-batches work on
branch `students/import-batch-preview`. This is the **corrected final**
revision — it resolves the defects found in scenario testing of the
earlier consolidated proposal (`misc/read_this.txt`).

## 0. Defect resolutions (from scenario testing)

| # | Defect found | Resolved in |
|---|---|---|
| D1 | Sample used `"1 Years"`, violating allowed `1 Year` | §4 (token normalization) |
| D2 | `Syllabus=Auto` undefined for MHT-CET (default vs stream-required collide) | §4, §6 |
| D3 | Student identity = Email+Phone (optional, family-shared) → false merges/dupes | §4, §7 |
| D4 | Batch-match key specified 3 inconsistent ways | §7 (one canonical key) |
| D5 | `End_AY_override` not representable in schema | §4 (removed v1), §11 |
| D6 | Duration encoded twice (`Course_opt` text + `Duration` col) → can disagree | §3, §6 |
| D7 | "Single transaction" vs "reject row only" contradiction | §7 (all-or-nothing) |
| D8 | `Course_opt` free text → duplicate courses; first-import validation a no-op | §3, §4 |
| D9 | `"Both/PCMB"` slash token ambiguous | §4 (→ `PCMB`) |
| D10 | `NEET+PCMB → Warn` fires on a common legit cohort | §6 (downgraded to info) |
| D11 | Class 9/10 + NEET → silent remap violates "catch, don't coerce" | §6 (`Aspiration_Target`) |
| D12 | Foundation class×duration only half-specified | §6 |
| D13 | `Enrollment_Date` Excel date landmine | §4, §7 |
| D14 | AY naming drift (`2026-27` vs existing `2026-2027`) | §7 |

## 1. Core insight — what the enriched columns map to

| Column | Maps to entity | Identity rule |
|---|---|---|
| `Course_opt` + `Duration` + dropper-flag | **Course** (`courses.duration_years`) | Course identity = program family + duration + whether it's a dropper batch. "NEET 2-Year", "NEET 1-Year", and "NEET Dropper" are three distinct courses. |
| `Academic_year` (e.g. 2026-2028) | **Academic Year** rows | A 2-yr span = two AY rows; a 1-yr span = one. |
| `Syllabus` | **Subjects** under the course | Which subject set (PCB / PCM / PCMB / Foundation) attaches per year. |
| `Batch` | **Batch** (cohort) | Identity = `(branch, normalized code, start_academic_year)` — see §7. |

`Subject → Chapter → Topic → Subtopic` is **per (course_id,
academic_year_id)**. The student import creates **Courses, Academic Years,
Subjects, Batches**; the detailed chapter/topic tree still comes from the
existing `/syllabus` import, keyed to the same course+AY.

> **Clean separation:** student import = academic *structure*; syllabus
> import = curriculum *depth*.

## 2. Master scenario matrix (standard / valid rows)

`Course_opt` is the **program family only — no duration in the text** (D6).
The Course *name/code* is derived: `code = Course_opt + Duration (+ DROP)`.

| # | Current_Class | Target | Duration | Syllabus (explicit or auto) | Course_opt | → derived Course | Academic_year |
|---|---|---|---|---|---|---|---|
| 1 | 11 | NEET | 2 Years | NEET / PCB | NEET | NEET 2-Year | 2026-2028 |
| 2 | 11 | JEE-Main/Adv | 2 Years | JEE / PCM | JEE | JEE 2-Year | 2026-2028 |
| 3 | 11 | Both | 2 Years | PCMB | NEET+JEE | NEET+JEE 2-Year | 2026-2028 |
| 4 | 11 | MHT-CET | 2 Years | MHT-CET-PCM | MHT-CET Engg | MHT-CET Engg 2-Year | 2026-2028 |
| 5 | 11 | MHT-CET | 2 Years | MHT-CET-PCB | MHT-CET Pharm | MHT-CET Pharm 2-Year | 2026-2028 |
| 6 | 12 | NEET | 1 Year | NEET / PCB | NEET | NEET 1-Year | 2026-2027 |
| 7 | 12 | JEE-Main | 1 Year | JEE / PCM | JEE | JEE 1-Year | 2026-2027 |
| 8 | Dropper | NEET | 1 Year | NEET / PCB | NEET | NEET Dropper | 2026-2027 |
| 9 | Dropper | JEE-Main | 1 Year | JEE / PCM | JEE | JEE Dropper | 2026-2027 |
| 10 | 9 | Foundation | 2 Years | Foundation | Foundation | Foundation 9-10 | 2026-2028 |
| 11 | 10 | Foundation | 1 Year | Foundation | Foundation | Foundation 10 | 2026-2027 |

**Dropper is its own course** (different pacing, exam-date, fees) — the
derivation appends `DROP` when `Current_Class = Dropper`, so it never
collides with the 1-Year 12th course.

## 3. Course identity — the derivation rule (D6, D8)

- `Course_opt` is a **controlled vocabulary**, not free text (D8):
  `{NEET, JEE, NEET+JEE, MHT-CET Engg, MHT-CET Pharm, Foundation}`.
  Validated against the enum — a typo is rejected on the first import, not
  canonicalized.
- Duration lives **only** in the `Duration` column. If `Course_opt` text
  contains a duration that disagrees with `Duration` → **error** (D6).
- Derived course `code` / `name`:
  - `NEET` + `2 Years` → "NEET 2-Year" / `NEET-2Y`
  - `NEET` + `1 Year` + Dropper → "NEET Dropper" / `NEET-DROP`
  - `Foundation` + `2 Years` (class 9) → "Foundation 9-10" / `FDN-9-10`
- A given `(Course_opt, Duration, dropper)` always resolves to **one**
  course, so re-imports are idempotent.

## 4. Final template

```
Name | Current_Class | Target | Aspiration_Target | Batch | Roll No |
Email | Phone | Parent Mobile | Gender | District | Caste | Username |
RFIDNumber | Duration | Syllabus | Course_opt | Academic_year | Enrollment_Date
```

| Column | Required | Allowed values / format | Notes |
|---|---|---|---|
| `Name` | Yes | text | |
| `Current_Class` | Yes | `9, 10, 11, 12, Dropper` | |
| `Target` | Yes | `NEET, JEE-Main, JEE-Advanced, MHT-CET, Both, Foundation, Other` | |
| `Aspiration_Target` | No | same enum as Target | For 9/10 foundation students whose eventual goal is NEET/JEE (D11). Stored, not remapped. |
| `Batch` | Yes | string | Normalized (trim/case/collapse `--`). Identity = `(branch, code, start_AY)` (§7). |
| `Roll No` | **Yes** | string | **Stable identity key** for idempotent re-import (D3). Fallback `RFIDNumber`; if both blank → treated as new + flagged. |
| `Email` | No | email | Soft hint only — **never** an identity key (D3). |
| `Phone` | No | string | Soft hint only (D3). |
| `Parent Mobile` | No | string | |
| `Gender` | No | `M, F, O` | |
| `District` / `Caste` / `Username` / `RFIDNumber` | No | text | |
| `Duration` | Yes | canonical `1 Year` \| `2 Years` | Accepts and normalizes `1`,`1yr`,`1 Years`,`2`,`2yr`,`2 Year` (D1). |
| `Syllabus` | No | `NEET, JEE, MHT-CET-PCM, MHT-CET-PCB, PCMB, Foundation` or blank=auto | Blank/`auto` derives from Target — **except MHT-CET**, which must be explicit PCM/PCB or it errors (D2, D9). |
| `Course_opt` | Yes | enum `NEET, JEE, NEET+JEE, MHT-CET Engg, MHT-CET Pharm, Foundation` | Controlled vocab, **no duration in the value** (D6, D8). |
| `Academic_year` | Yes | `YYYY-YYYY` | Span length must equal Duration. Split into 4-digit AY rows (D14). |
| `Enrollment_Date` | No | **ISO `YYYY-MM-DD`** | Importer also coerces Excel serials / `DD-MM-YYYY`; ambiguous → error (D13). Default = import date. Validated within batch span. |

`End_AY_override` is **removed in v1** (D5): student↔batch mapping has no
per-student AY scoping, so "second year only" can't be expressed. Mid-program
joiners enroll in the matching 1-Year course/batch instead. See §11 for the
schema change required if true second-year joins are needed later.

## 5. (reserved)

## 6. Odd-case validation matrix (catch, never silently coerce)

| Scenario | Rule | Message |
|---|---|---|
| Class 12 / Dropper + Duration 2 Years | **Error** | `12th/Dropper cannot be 2-Year (one year before exam)` |
| Class 11 + Duration 1 Year | **Warn** | `11th + 1-Year ends mid-program; allow only for crash course` |
| `(end_year − start_year) ≠ Duration` | **Error** | `Academic_year span ≠ Duration` |
| `Course_opt` text duration ≠ `Duration` column | **Error** (D6) | `Course_opt implies a different duration than Duration` |
| Target NEET + Syllabus JEE (or vice-versa) | **Error** | `Target/Syllabus mismatch` |
| Target Both + Syllabus not PCMB | **Error** | `Both requires PCMB (P,C,M,Bio)` |
| Target NEET + Syllabus PCMB | **Info** (not gating) (D10) | `PCMB kept alongside NEET — fine (backup stream)` |
| Target MHT-CET + Syllabus blank/auto or no PCM/PCB | **Error** (D2) | `MHT-CET needs explicit MHT-CET-PCM or MHT-CET-PCB; auto cannot resolve` |
| Class 9/10 + `Course_opt` ≠ Foundation | **Error** (D11) | `Class 9/10 must enroll in Foundation; put NEET/JEE goal in Aspiration_Target` |
| Class 10 + Duration 2 Years | **Error** (D12) | `Foundation ends at class 10; 2-Year invalid for a 10th entrant` |
| Class 9 + Duration 1 Year | **Warn** (D12) | `1-Year foundation for class 9 — confirm coaching offers it` (ties to §11.3) |
| Same `Batch` code → different `(course, start_AY)` | **Error** (D4) | `Batch code already maps to a different course/year` |
| Duration 2 Years + end AY uncreatable | **Error** | `Cannot create the second academic year` |
| Malformed `JEE--` / `MHT--` codes | Normalize + **Warn** | `Code normalized; please fix the source file` |
| `Roll No` and `RFIDNumber` both blank | **Warn** (D3) | `No stable id — row treated as new; re-import will duplicate` |

## 7. Import flow — all-or-nothing, one transaction (D4, D7, D13, D14)

```
0. Parse & normalize  (trim, code-collapse, Duration tokens (D1), date coercion (D13))
1. Validate ALL rows against §6.
     - Any ERROR  → reject the WHOLE file, write nothing (D7).
     - WARN/INFO  → surface in the preview; require explicit confirmation.
2. Build the dry-run diff (the §10 confirmation matrix).
3. On confirm, in ONE transaction (rollback on any failure):
     a. Academic Years  ← split span → ensure 4-digit AY rows (2026-2027, 2027-2028) (D14)
     b. Course          ← (Course_opt + Duration + dropper) → ensure course (§3)
     c. Subjects        ← (Syllabus + class) → ensure set per AY  [respect §8 lock; additive-only]
     d. Batch           ← match (branch, normalized code, start_AY) (D4)
                            • found + different course → ERROR collision
                            • else create under the resolved course
     e. Student         ← identity = Roll No (→ RFIDNumber → else new+flag) (D3)
     f. Mapping         ← StudentBatchMapping(student, batch); set Enrollment_Date
4. Commit only if every row succeeded; tag all created students with import_id (§9).
```

**Batch identity is exactly `(branch_id, normalized_code, start_academic_year_id)`**
— this is the single canonical key (resolves D4). Course is *asserted*
against the matched batch, not part of the key. This also resolves §11.1:
codes may repeat across intake years because `start_AY` disambiguates them.

## 8. Syllabus boundary — state machine + lock

Per `(course_id, academic_year_id)`:

| State | Student import may… | Syllabus import may… |
|---|---|---|
| `no_subjects` | create the subject set | — |
| `subjects_only` | **add** missing subjects; never delete | add chapters/topics |
| `has_chapters` (`syllabus_locked`) | no-op if subjects match; **error on conflicting** subject; additions allowed | append only |

Additions are allowed; only **conflicting/destructive** changes error (so a
coaching legitimately adding "English" later isn't blocked). An admin
override exists to correct a wrong skeleton after lock (escape hatch).

## 9. Derived fields — store only what isn't derivable

| Field | Verdict | Rationale |
|---|---|---|
| `aspiration_target` (student) | **Store** | Not derivable; the 9/10 NEET/JEE goal (D11). |
| `import_id` + `import_source_file` (student) | **Store** | Traceability; enables guarded "undo this import". |
| `target_exam_date` (batch) | **Reuse existing column** | = end-AY + exam month; don't add a new field. |
| `is_dropper` | **Don't store** | Derivation of `Current_Class = 'Dropper'`. |
| `program_duration_months` | **Don't store** | `duration_years * 12`. |

> Note on rollback (D-review §2.2): per-import undo is only safe while no
> downstream rows reference the created structure (e.g. a later syllabus
> import added chapters, or another batch reuses a created course). The
> safe guarantee is the **in-transaction** rollback in §7; post-hoc undo
> must check for dependents first.

## 10. Import preview UX

Confirmation matrix the user must accept before any write:

```
Action              | Count | Examples              | Gate
--------------------+-------+-----------------------+------
New courses         |   3   | NEET 2-Year, JEE 1-Yr |
Existing courses    |   5   | Foundation 9-10       |
New academic years  |   2   | 2027-2028             |
New batches         |   8   | NEET-11-A, JEE-12-B   |
Batch collisions    |   1   | code↔diff course      | BLOCK
Missing stable id   |   2   | (no Roll No / RFID)   | WARN
Syllabus conflicts  |   0   |                       | BLOCK
```

Plus a sample-row transformation so the user sees what one row creates
(course, AY rows, subjects, batch).

## 11. Open decisions — master data only the coaching can define

1. **Batch-code namespace** — *resolved to a default* in §7: identity is
   `(branch, code, start_AY)`, so codes may repeat across intake years.
   Confirm this matches their practice (vs year-suffixed unique codes).
2. **MHT-CET split** — confirm separate Engg (PCM) / Pharm (PCB) tracks.
3. **Foundation durations** — is class 9 a 2-year (9+10) or also 1-year?
   (drives the §6 class-9 + 1-Year warn).
4. **Subject set per syllabus** — Biology vs Botany+Zoology; MHT-CET naming.
5. **Target exam dates per program/year** — for `target_exam_date` pacing.
6. **Intake year(s)** — single 2026 intake or multiple.
7. **Second-year joins** — if genuinely needed, add `join_academic_year_id`
   to `StudentBatchMapping` (the schema change `End_AY_override` would have
   required); otherwise mid-program joiners use the 1-Year course (D5).

## 12. Sample template

A clean, spec-compliant reference lives at
`docs/students-master-import-template.sample.csv` — one row per valid
scenario, canonical `1 Year`/`2 Years`, explicit MHT-CET streams, distinct
non-overlapping phones, ISO dates, and `Course_opt` without embedded
durations. (It deliberately contains **no** `1 Years`, `Auto`+MHT-CET,
duplicate-phone, or duration-double-encoding traps.)

## 13. Next steps (after §11 answered)

1. Validation service running the §6 matrix before any write.
2. Dry-run diff + confirmation matrix (§10) — highest ROI.
3. Batch matching on the §7 canonical key; collision detection.
4. `syllabus_locked` + additive-only state machine (§8).
5. Single-transaction import + `import_id`/`import_source_file` (§7, §9).
6. Extend the importer to upsert Courses / Academic Years / Subjects.
