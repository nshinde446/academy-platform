# Students Import & Roster — Master Plan (single source of truth)

Status: **authoritative plan**. Supersedes and reconciles:
- `misc/students-master-import-design.md` (academic-structure deep dive — kept for §1–§9 domain depth)
- `misc/read_this.txt` (SIS/ERP upgrade strategy — kept for the phased UX framing)

This document folds both, resolves the contradictions between them, and lays
out one execution roadmap from quick win to end. **Task tracking** for this plan
lives in the session task list (TaskCreate); the "Roadmap & tasks" section below
mirrors it so the plan is self-contained.

---

## 0. The thesis

Move from a **rigid, exact-header file importer** to a **guided data-management
ecosystem**: a forgiving import (map any file, fix inline, never lose a column),
a roster that can be filtered/bulk-edited at scale, and an academic-structure
engine that keeps Courses / AYs / Subjects / Batches consistent — "no tangled
data." Three independent reviews (the two docs above + an inline code review)
converged on this; the direction is settled. The work below is execution.

## 1. What already exists (do not rebuild)

Grounded in the current code:

- **Background import job** with progress polling — `import/start` + `import/jobs/{id}` (`backend/app/modules/student/api/routes.py:250`), model `StudentImportJob` (`student_models.py:112`).
- **Pre-commit preview / dry-run** — `import/preview` returns batch match/miss + row issues (`routes.py:199`, dialog `import-students-dialog.tsx:405`).
- **Auto-create missing batches** with per-row cohort mixing, course/exam-date derived from `Target` (`import_service.py:65`).
- **DB-level dedup** — partial unique index `uq_students_active_enrollment` (`student_models.py:18`).
- **Traceability + undo** — `import_id` on every created student; `import/{import_id}/undo` soft-deletes the unit and reclaims orphan batches (`routes.py:303`).
- **Optional batch-override columns** — `Course_opt`, `Duration`, `Academic_year`, `Syllabus` already parsed (`import_service.py:209`).
- **RBAC** — all mutating routes already gated to `super_admin` / `branch_admin`.
- **Roster** — server-side paginated/searched/sorted (`routes.py:75`), one inline-edit field (stream) in `student-table.tsx:157`.

## 2. The core problem

The importer is **fixed-header-alias matching** (`COLUMN_MAPPING` `import_service.py:30`,
`_OVERRIDE_HEADERS` `:209`). Three failure modes for a real admin:

1. **Silent data loss.** A header not in the alias maps (`Mobile`, `DOB`,
   `Father's Name`, `Category`) is dropped with **no warning anywhere**.
2. **Reachability gap.** The `Student` model has `date_of_birth`; there is a
   full `Parent` table (name/relation/occupation) and `fees_status` — none are
   in `COLUMN_MAPPING`. So "import all the columns" is impossible today.
3. **Round-trip fixes.** Errors return as a text list; the admin must edit the
   spreadsheet and re-upload instead of fixing inline.

## 3. Resolved design decisions (the contradictions both docs left open)

These were genuine forks. Decisions, with rationale, so the build is unambiguous:

| Decision | Resolution | Why |
|---|---|---|
| **Partial-accept vs. all-or-nothing** | **Two-tier.** *Student rows* commit partially — clean rows import, rejected rows are downloadable as a "fix-these" file. *Academic structure* (Courses/AYs/Subjects/Batches) stays **single-transaction**: if structure creation fails, the whole import aborts. | The current code is all-or-nothing; mature SIS are partial on rows. Splitting at the structure boundary keeps "no orphan Course/AY rows" (design §7.2) while giving admins the partial-row UX they expect. |
| **Validation grid scope** | The grid is a **relational validator**, not a cell-format checker. It runs the §6 contradiction rules *and* cross-row collision rules (same Batch code → two Courses), surfacing them inline. | A per-cell "is this a date" grid is shallow; the domain edge is cross-row cohort consistency. |
| **Auto-derive batches from a column** (read_this Phase 3) | **Dropped.** Keep explicit `Batch` codes + preview. | A "make a batch per unique Class value" rules-builder generates junk batches and is strictly worse than the explicit-code flow already shipped. |
| **Edit-offline-and-reimport vs. inline edit** | **Both, scoped.** Inline grid edit = fix a few bad cells *during* import. Export→edit→reimport = mass changes to *existing* records. Documented so we don't build the wrong one. | They serve different jobs; the docs conflated them. |
| **Batch-code namespace** (design §6.7) | **RESOLVED (client, 2026-06-23): per-branch unique.** Batch codes are arbitrary, institute-chosen *unique* names (`SPRING`, `ALPHA`, `NEET-11_A`) — they do NOT repeat across intake years, so per-branch uniqueness (the current importer behavior) stands; no per-(branch,start-AY) change needed. | If an institute ever reuses a semantic code yearly, the importer matches the existing batch; switch to per-(branch,start-year) only if that becomes a real need. |
| **Dedup beyond enrollment number** | Add **fuzzy person-match** warning: same `(lower(name), phone)` or `(lower(name), date_of_birth)` against existing live students → WARN in preview/grid (not a hard block). | Today dedup is enrollment-number-only; the same human re-entered without a roll no slips through. |
| **Reusable mapping profiles** | **Yes.** Persist a per-branch column→field mapping so a returning school maps once. | Biggest repeat-pain; cheap once the mapping UI exists. |

## 4. Field coverage to add to `COLUMN_MAPPING` (the quick win)

Model already supports these; just wire the aliases (and create a `Parent` row,
not merely stash `parent_mobile`):

- `date_of_birth` ← `DOB`, `Date of Birth`, `Birth Date`
- `parent_name` / `parent_relation` / `parent_occupation` → create a `Parent` row (model `student_models.py:96`)
- `fees_status` ← `Fees`, `Fee Status`, `Payment Status` (enum paid|due|overdue|partial)
- `enrollment_date` ← `Enrollment Date`, `Admission Date` (drives pro-rata fees/attendance start, design §5)
- `aspiration_target` ← for the §6 9th/10th-NEET remap case
- Field normalization on read: trim, title-case names, phone digit-strip, multi-format date parse.

## 5. Domain rules the grid/validator must enforce (from design §3/§6)

Carried verbatim from the deep dive — these are the "no tangled data" guarantees:

- `Class 12` or `Dropper` + `Duration 2 Years` → **Error** (only one year before exam).
- `Class 11` + `Duration 1 Year` → **Warn** (deliberate crash course only).
- `Academic_year` span ≠ `Duration` → **Error** (`(end−start) == duration`).
- `Target=NEET` but `Syllabus=JEE` → **Error** (unless `Target=Both`).
- `Target=Both` but `Syllabus=PCM` (no Bio) → **Error** (Both requires PCMB).
- `Target=NEET` + `Syllabus=PCMB` → **Warn** (extra Maths, inefficient).
- `MHT-CET` with no PCM/PCB hint → **Require** a stream value or infer from Target.
- `Class 9/10` + `Target NEET/JEE` + `Duration 2yr` → **Error or remap** to Foundation + store `aspiration_target`.
- Same `Batch` code → two different `(Course, AY)` → **Error** (collision).
- `Batch` code from a different branch → **Error** (codes are per-branch).
- Same `(Name, Phone, Email)` → two `Course_opt` → **Warn** (dual-batch enrolment).

## 6. Academic-structure upsert order (design §4 — idempotent, get-or-create)

```
0. Pre-flight: validate all rows (§5), build diff, BLOCK on structure errors
1. Academic Years   ← parse Academic_year span → ensure each AY row
2. Course           ← (Course_opt + Duration) → ensure course w/ duration_years
3. Subjects         ← (Syllabus + class) → ensure subject set per (course, AY)  [respect syllabus_locked]
4. Batch            ← (code + course + start AY) → ensure batch (end AY = start + duration−1, target_exam_date set)
5. Student + mapping← create student + StudentBatchMapping → batch  [partial-accept on rows]
```

Steps 1–4 are one transaction (all-or-nothing); step 5 is partial. **Never
overwrite a `(course, AY)` that already has subjects** — add a `syllabus_locked`
flag; once `/syllabus` import runs, student import can't touch that course-year's
subjects (design §8).

## 7. Roadmap & tasks (quick win → end)

Phases map 1:1 to the session task list. Each phase ships independently.

**Phase 0 — Quick win (backend only, low risk)**
- T1. Extend `COLUMN_MAPPING` for DOB / parent (→ Parent row) / fees_status / enrollment_date / aspiration_target + field normalization (§4).
- T2. Surface **unrecognized columns** in `import/preview` response + dialog warning (kills silent data loss).

**Phase 1 — Smart import UI**
- T3. **Column-mapping step** between upload and preview: fuzzy-guess from alias maps, admin remaps via dropdowns, unmapped columns explicit.
- T4. **Editable validation grid**: render parsed rows, run §5 relational rules per-cell, fix inline, re-validate live, partial-accept clean rows + download rejected rows.
- T5. **Reusable mapping profiles**: persist per-branch column→field mapping; auto-apply on next upload (§3).

**Phase 2 — Roster management hub**
- T6. **Bulk actions**: row checkboxes → Assign to Batch / Set Fees Status / Export / Delete (generalize the existing delete-all).
- T7. **Advanced filters + Saved Views**: class, batch, target, fees status, enrollment date; persist filter combos as named views.
- T8. **Expand inline editing** beyond stream (batch, fees status, class) using the existing `student-table.tsx` pattern.
- T9. **Export current view** (respects active filters) to CSV/Excel — the round-trip partner to import.

**Phase 3 — Academic-structure engine (backend, builds on all above)**
- T10. **Single-transaction upsert** of Courses / AYs / Subjects (§6) with `import_id` rollback on structure failure.
- T11. **`syllabus_locked` state machine** (§6/design §8) protecting curriculum from structure imports.
- T12. **Fuzzy person-dedup** warning (name+phone / name+DOB) in preview + grid (§3).
- T13. **Confirmation matrix** (design §7.1): counts of new/existing Courses, AYs, Batches, collisions (BLOCK), duplicates (WARN) + one sample-row transformation, accepted before commit.

**Cross-cutting (fold into the phase that first needs it)**
- Audit-trail visibility for bulk ops; PII care on export; "Promote Class" treated as its own validated mini-import (not a one-click toggle) — defer to a later tier.

## 8. Open items needing the client (block only the phases noted)

- ~~**Batch-code namespace**~~ — **RESOLVED 2026-06-23**: per-branch unique, arbitrary institute-chosen codes (don't repeat across years). Keep current behavior.
- ~~**Course catalog & naming**~~ — **RESOLVED 2026-06-23**: generic naming (the existing Target+Duration derivation). No catalogue table.
- **Still open (have working defaults; not blocking T10's core):** MHT-CET PCM/PCB split (current: union set on one course, per-student stream filters), Foundation durations (current: derived from class), subject sets (current: NEET=P/C/Botany/Zoology, JEE=PCM, etc.), per-programme exam dates (current: derived defaults), intake year (current: from import date / Academic_year column). These can land as config later.

**Net: T10's structural core is now unblocked** — generic course naming + per-branch
unique batch codes are settled, and #2–#6 already have sensible defaults in the
importer. T10 can build on the existing get-or-create (batches/AYs/subjects) by
adding the explicit Course catalogue upsert + single-transaction guarantee.

## 8b. Build status (2026-06-23)

Shipped + tested this session (backend pytest + frontend vitest, all green):

- **T1** ✅ COLUMN_MAPPING for DOB/fees/aspiration + name/phone/date normalization.
- **T2** ✅ unrecognized-columns surfaced in preview + dialog.
- **T3** ✅ column-mapping step: `/import/columns` detect endpoint + `column_map`
  on preview/import/start; `ColumnMapStep` UI.
- **T5** ✅ reusable per-branch mapping profiles (localStorage, auto-applied).
- **T6** ✅ roster bulk actions: `/students/bulk-update` + `/bulk-delete`,
  selection checkboxes, `BulkActionBar` (set fees/class/stream, assign batch,
  export selected, delete).
- **T7** ✅ roster filters (class/target/fees/batch on `/roster`) + Saved Views.
- **T8** ✅ inline edit extended to class + fees (generic `onFieldChange`).
- **T9** ✅ export current view to CSV (paged fetch respecting search/filters).
- **T12** ✅ fuzzy person-dedup warning (name+phone / name+DOB) in preview + import.
- **T13** ✅ confirmation matrix (`ImportConfirmMatrix`) aggregating the preview.
- **T14** ✅ parent rows + `enrollment_date` (migration 0035), reclaimed on undo.

Remaining:

- **T4** — *partial-accept already works at the row level today* (clean rows
  commit, rejected rows are reported with per-row reasons). The remaining piece
  is the **inline-editable grid** (fix bad cells in place) + a downloadable
  rejected-rows file — a larger frontend build; deferred.
- **T11** — the syllabus-overwrite protection it specifies is **already enforced
  via the derived check** (skeleton only created when a course-year has no
  subjects; undo keeps chaptered subjects — both tested). An *explicit*
  `syllabus_locked` column is a forward-looking refinement with no behavioral
  change today; deferred to avoid schema surface for a no-op.
- **T10** — **blocked on client §8 decisions** (batch-code namespace, course
  catalog naming, MHT-CET PCM/PCB split). Much of the upsert already ships
  (auto-create batches/AYs/subject skeletons, single-import transaction,
  `import_id` rollback); the catalog-naming half must not be invented.

## 9. Sequencing note

Phase 0 → 1 → 2 → 3 is deliberate: Phase 0 delivers value today with no UI risk;
Phase 1 removes ~80% of import friction; Phase 2 makes the roster a real tool;
Phase 3 is the deepest/riskiest and depends on the client answering §8. Do not
reorder Phase 3 ahead of the client answers.
