# Students Master Import — Design (Academics auto-population)

Status: **design / not implemented**. No prod or DB changes. Captures the
deep-dive for an enriched student import template that becomes the single
source of truth for the Academics tabs (Courses, Batches, Academic Years,
Syllabus).

Related: builds on the import preview + create-missing-batches work on
branch `students/import-batch-preview`. §7–§11 incorporate a peer review
(see `misc/read_this.txt`); where this doc diverges from that review it
says so and why.

## 1. Core insight — what the enriched columns map to

The data model already has the right entities; today they're created
ad-hoc. The enriched columns let the **student import build them
bottom-up**, so the Academics tabs stay consistent ("no tangled data").

| New column | Maps to entity | Identity rule |
|---|---|---|
| `Course_opt` + `Duration` | **Course** (`courses.duration_years`) | A course's identity *includes* its duration. "NEET 2-Year" and "NEET 1-Year" are two different courses. |
| `Academic_year` (e.g. 2026-2028) | **Academic Year** rows | A 2-yr span = two AY rows (2026-27, 2027-28); a 1-yr span = one (2026-27). |
| `Syllabus` | **Subjects** under the course (syllabus *skeleton*) | Which subject set (PCB / PCM / PCMB / Foundation) attaches to the course per year. |
| `Batch` | **Batch** (cohort) | A batch instantiates one course for one start-AY. |

Critical structural fact: `Subject → Chapter → Topic → Subtopic` is **per
(course_id, academic_year_id)**. So the student import can create
**Courses, Academic Years, Subjects, and Batches** — but the *detailed
chapter/topic tree* still comes from the existing `/syllabus` import,
keyed to the same course+AY.

> **The clean separation:** student import = academic *structure*;
> syllabus import = curriculum *depth*.

## 2. Master scenario matrix (standard / "even" cases)

Class drives duration; Target+Syllabus drive the subject set; Duration
drives the AY span.

| Current_Class | Target | Duration | → Course | → AY span | → Subjects (Syllabus) |
|---|---|---|---|---|---|
| 11 | NEET | 2 Years | NEET 2-Year | 2026-2028 (2 AYs) | Physics, Chemistry, Botany, Zoology |
| 11 | JEE-Main / JEE-Adv | 2 Years | JEE 2-Year | 2026-2028 | Physics, Chemistry, Maths |
| 11 | Both | 2 Years | NEET+JEE 2-Year | 2026-2028 | PCMB (P, C, M, Bio) |
| 11 | MHT-CET (PCM) | 2 Years | MHT-CET Engg 2-Year | 2026-2028 | Physics, Chemistry, Maths |
| 11 | MHT-CET (PCB) | 2 Years | MHT-CET Pharm 2-Year | 2026-2028 | Physics, Chemistry, Biology |
| 12 | NEET | 1 Year | NEET 1-Year | 2026-2027 | P, C, Botany, Zoology (12th) |
| 12 | JEE | 1 Year | JEE 1-Year | 2026-2027 | P, C, M (12th) |
| Dropper | NEET | 1 Year | NEET Dropper | 2026-2027 | full PCB repeat |
| Dropper | JEE | 1 Year | JEE Dropper | 2026-2027 | full PCM repeat |
| 9 | Foundation | 2 Years | Foundation 9-10 | 2026-2028 | Science, Maths, Mental Ability |
| 10 | Foundation | 1 Year | Foundation 10 | 2026-2027 | Science, Maths |

**Dropper is its own course, never year-2 of a 2-Year course** — different
pacing (revision vs first-teach), different exam-date logic, different
fees. The matrix reflects this.

## 3. "Odd" cases — contradictions to catch, not silently coerce

This is where "no tangled data" is won or lost. Validate each row.

| Scenario | Why it's wrong | Rule |
|---|---|---|
| Class **12** + Duration **2 Years** | Only one academic year before the exam | **Error** — 12th/Dropper must be 1-Year |
| **Dropper** + Duration **2 Years** | Droppers do a single repeat year | **Error** |
| Class **11** + Duration **1 Year** | Finishes mid-program, before the exam | **Warn** (allow only for deliberate 11th-only crash course) |
| `Academic_year` span ≠ `Duration` | The two columns disagree | **Error** — assert `(end_year − start_year) == duration` |
| Class **12** + Duration 2yr **and** intake AY is the current/ending year | Student would miss the exam cycle entirely | **Error** unless `Academic_year` start is a future year (deferred/dropper intake) |
| `Target` = NEET but `Syllabus` = JEE | Exam and curriculum conflict | **Error** unless Target = Both |
| `Target` = **Both** but `Syllabus` = PCM (no Bio) | Incomplete for NEET half | **Error** — Both requires PCMB |
| `Target` = NEET but `Syllabus` = PCMB | Extra Maths the student won't sit | **Warn** — allowed but flagged as inefficient |
| `MHT-CET` with no PCM/PCB hint | Subject set ambiguous (engg vs pharmacy) | **Require** a stream sub-value or infer from paired Target |
| Class **9/10** + Target NEET/JEE + Duration 2yr | No "NEET 2-Year" course exists for a 9th-grader | **Error or remap** to Foundation + store `aspiration_target = NEET` |
| Same `(Name, Phone, Email)` → two `Course_opt` in one file | Possible dual-batch enrolment | **Warn** — confirm intentional (legit only for split programs) |
| Same `Batch` code → two different (Course, AY) | Batch identity collision | **Error** — see namespace decision in §6 |
| `Batch` code that exists in a **different branch** | Cross-branch contamination | **Error** — codes are per-branch only |
| Duration "2 Years" but end AY missing/uncreatable | AY row missing | Auto-create AY; if blocked, error |
| `JEE--` / `MHT--` malformed codes | Double-encoding | Normalize + surface in preview (already handled) |

## 4. Auto-update flow on import (idempotent upsert order)

Each step is get-or-create, so re-imports don't duplicate. Steps run
inside **one transaction per import** so a mid-run failure rolls back
cleanly (see §7.2 — no orphaned Course/AY rows).

```
0. Pre-flight: validate all rows (§3), build the diff, BLOCK on errors
1. Academic Years   ← parse Academic_year span → ensure each AY row (2026-27, 2027-28)
2. Course           ← (Course_opt + Duration) → ensure course w/ duration_years
3. Subjects         ← (Syllabus + class) → ensure subject set under course, per AY  [respect §8 lock]
4. Batch            ← (Batch code + course + start AY) → ensure batch (end AY = start + duration−1)
5. Student + mapping← create student (Current_Class, Target...) + StudentBatchMapping → batch
```

After a clean import the Academics tabs populate themselves consistently:

- **Academic Years** → exactly the AY rows the cohorts span (no orphans).
- **Courses** → the real catalog (NEET 2-Year, JEE 1-Year, Foundation 9-10…), each with correct `duration_years`.
- **Batches** → every cohort, linked to course + AY span + `target_exam_date`.
- **Syllabus** → subject skeletons per course/year, ready for `/syllabus`
  to fill in chapters/topics, keyed to the same course+AY.

## 5. Recommended final template

Keep all columns explicit (coaching provides master data) but **validate**
rather than re-derive.

```
Name | Current_Class | Target | Batch | Roll No | Email | Phone | Parent Mobile |
Gender | District | Caste | Username | RFIDNumber |
Duration | Syllabus | Course_opt | Academic_year |
[Enrollment_Date] | [End_AY_override]
```

- **Required**: Name, Current_Class, Target, Batch, Duration, Course_opt, Academic_year
- **Syllabus**: optional → defaults from Target (NEET→PCB, JEE→PCM, Both→PCMB); explicit value **wins** (handles MHT-CET PCM/PCB split)
- **`Enrollment_Date`** (optional) — pro-rata fees / attendance start, e.g. `2026-06-15`
- **`End_AY_override`** (optional, rare) — student joins the *second* year of a 2-Year course. Course stays 2-Year (syllabus still shows both years) but the student maps only to that one AY.
- **Allowed values to lock down**:
  - Current_Class ∈ {9, 10, 11, 12, Dropper}
  - Target ∈ {NEET, JEE-Main, JEE-Advanced, MHT-CET, Both, Foundation, Other}
  - Duration ∈ {1 Year, 2 Years}
  - Academic_year format `YYYY-YYYY`
  - Syllabus ∈ {NEET, JEE, MHT-CET-PCM, MHT-CET-PCB, Both/PCMB, Foundation}

## 6. Open decisions — master data only the coaching can define

1. **Course catalog & naming** — "NEET 2-Year" vs branded names; course codes.
2. **MHT-CET split** — separate PCM (engineering) and PCB (pharmacy/medical) tracks, or combined?
3. **Foundation durations** — class 9 = 2-year (9+10) or 1-year? Class 10 = 1-year?
4. **Subject set per syllabus** — Biology vs Botany+Zoology; MHT-CET state-board subject naming.
5. **Target exam dates per program/year** — for `target_exam_date` driving `/insights` pacing.
6. **Intake year** — all 2026 intake, or batches starting other years?
7. **Batch-code namespace** — *do batch codes repeat across intake years?*
   - If codes are reused yearly (e.g. "NEET-11-A" for both the 2026 and 2027
     cohort), uniqueness must be **per (branch_id, start_academic_year_id)**,
     and the importer must match on code + start-AY, not code alone.
   - If codes are unique forever (e.g. year-suffixed "NEET-11-A-26"),
     per-branch uniqueness is enough (current behaviour).
   - **This choice changes the batch-matching key** — confirm before build.

## 7. Operational safeguards

### 7.1 Dry-run diff before any write
Extend the existing import preview into a **confirmation matrix** the user
must accept before committing:

```
Action              | Count | Examples                | Gate
--------------------+-------+-------------------------+------
New courses         |   3   | NEET 2-Year, JEE 1-Yr   |
Existing courses    |   5   | Foundation 9-10         |
New academic years  |   2   | 2027-28                 |
New batches         |   8   | NEET-11-A, JEE-12-B     |
Batch collisions    |   1   | BATCH-X (diff course)   | BLOCK
Student duplicates  |   2   | (phone/email)           | WARN
Syllabus mismatch   |   0   |                         |
```

Plus a **sample-row transformation** so the user sees what one row creates:

```
Input:  Class 11, Target NEET, Duration 2 Years, Syllabus (empty)
Creates: Course "NEET 2-Year" (duration_years=2)
         AYs 2026-27, 2027-28
         Subjects P, C, Botany, Zoology (both AYs)
         Batch from Batch code + start AY
```

### 7.2 One transaction + import id
Run the whole import in a single transaction tagged with an `import_id`
(also stored on created students, §9). A failure after step 3 rolls back
the whole thing — no orphaned `AcademicYear` / `Course` / `Subject` rows.
The `import_id` also enables a targeted "undo this import" later.

### 7.3 Batch-code namespace
Enforce whatever §6.7 resolves to as a DB-level uniqueness constraint, so
collisions are impossible rather than merely validated.

### 7.4 Never silently overwrite syllabus
Student import must **not** mutate `subjects` for a `(course, AY)` that
already has them. If the incoming syllabus disagrees with what exists →
**error**, don't overwrite. See §8.

## 8. Syllabus boundary — explicit state machine

Per `(course_id, academic_year_id)`:

| State | Meaning | Student import may… | Syllabus import may… |
|---|---|---|---|
| `no_subjects` | skeleton not created | create the subject set | — |
| `subjects_only` | subjects exist, no chapters | validate match only (no change) | add chapters/topics |
| `has_chapters` | curriculum loaded | error on mismatch, else no-op | append only (no destructive delete) |

Add a `syllabus_locked` flag per course-year; once a syllabus import runs,
student imports can no longer touch that course-year's subjects. This makes
the import-order independence explicit instead of relying on convention.

## 9. Derived fields — store only what isn't derivable

The review suggested storing several derived fields. Applying judgment, to
avoid denormalization drift:

| Field | Verdict | Rationale |
|---|---|---|
| `aspiration_target` (student) | **Store** | Not derivable once a 9th/10th NEET aspirant is remapped to Foundation. |
| `import_source_file` + `import_id` (student) | **Store** | Pure traceability; can't be recomputed. |
| `target_exam_date` (batch) | **Already exists** | Reuse the existing column (= end-AY + exam month); don't add `expected_exam_date`. |
| `is_dropper` (student) | **Don't store** | Pure derivation of `Current_Class = 'Dropper'`. Compute in queries. |
| `program_duration_months` (course) | **Don't store** | `duration_years * 12`. Compute on read. |

These unlock queries like *"droppers who started 2026-27 targeting NEET
with incomplete syllabus coverage"* without redundant columns.

## 10. Next steps (after §6 answered)

1. **Dry-run diff + confirmation matrix** (§7.1) — highest leverage; stops accidental writes.
2. **Batch-collision detection** keyed to the §6.7 namespace decision.
3. **`syllabus_locked` flag** (§8) — protects curriculum from structure imports.
4. **Single-transaction + `import_id`** (§7.2) for clean partial-failure rollback.
5. Validated sample template (allowed-value dropdowns, one row per scenario).
6. Extend the importer preview to upsert Courses / Academic Years / Subjects (not just batches), enforcing §3.
7. Store `aspiration_target` + `import_source_file`/`import_id` (§9).
