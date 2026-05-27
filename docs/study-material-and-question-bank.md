# Study Material + Question Bank organization — roadmap

Companion to `docs/question-bank-and-dpp-roadmap.md` (which covers
generation, paper composition, OMR) and
`docs/coaching-test-loop-roadmap.md` (Tiers 11–16, the data plumbing).

**This** doc covers the *content organization layer* underneath both:

- How study material (PDFs, Word docs, images, text) gets uploaded,
  filed, and made browseable by admins.
- How the Question Bank tab consumes that organization so questions can
  be filtered by class / subject / topic / exam type / batch.
- How the test composer queries the bank via the same facets.

Saved 2026-05-27 in response to a clear product brief from the user:

> I want folders/buckets visible to the admin whenever they upload new
> data for a batch. Sorted by class. Each folder contains subject-wise
> DPP/CPP, Question Bank, Topic-wise. The Question Bank tab should be
> wired so all study material for NEET / JEE / Advanced etc. is sorted
> enough to track, and the test composer can use as much prep data as
> they want when building tests.

---

## What we have today (recap)

- `study_material/extracted/<subject>/class-<N>/<chapter>/<file>.pdf` —
  ~8 NCERT-topic-wise workbook PDFs sitting on disk.
- `backend/scripts/ingest_studymat.py` extracts MCQs from those PDFs
  into the `questions` table with `source = "studymat:<slug>"` and
  `source_ref = "<doc_path>#p<page>q<qnum>"`.
- 719 questions in `questions` table; 673 with `correct_answer` set
  (Phase H), 46 flagged `pending_review`.
- `/question-bank` UI lists questions with status/difficulty/source
  filters (three-pane layout from Phase D).
- No upload UI. No batch linkage. No class/subject/topic facets in the
  question-bank filter rail. No storage abstraction — files are placed
  on disk manually.

This roadmap is what's needed to lift that into a real
admin-facing content management layer.

---

## Three design calls

These were debated 2026-05-27 and resolved as follows. Future tiers
should not re-litigate without strong reason.

### 1. Storage backend — local FS now, behind a thin interface

- Files live on the VPS at `study_material/<year>/<class>/<subject>/<category>/<material-id>--<filename>`.
- All reads/writes go through a `StorageBackend` interface in
  `backend/app/core/storage/` with two implementations:
  - `LocalFilesystemBackend` (used today, prod + dev)
  - `S3Backend` stub (one method body, to be filled when we need it)
- The interface returns presigned URLs / streams, never raw filesystem
  paths to callers.

**Why:** zero new infra, easy to back up via `pg_dump` + `tar`, files
already live on the VPS. The interface keeps the eventual migration to
S3 / MinIO / Vercel Blob a one-class change. Object storage is the
right answer at ~hundreds of GB or when we want CDN — neither is true
now.

### 2. Scope — shared material library + many-to-many to batches

- A `materials` row is the canonical unit (one file = one row).
- `material_batches(material_id, batch_id)` join table links materials
  to as many batches as needed.
- Tagging is what scopes — `class`, `subject`, `topic`, `exam_types[]`
  on the material row, plus the batch join.

**Why:** same NCERT Class-11 Physics PDF feeds NEET-A, NEET-B, JEE-A,
and JEE-B in the same year. Per-batch silos force the admin to
re-upload identical files 4× and lose deduplication. The shared model
also makes "this PDF is used by 3 batches; deleting will break their
DPPs" answerable in one query.

### 3. Categories — fixed enum, no per-batch custom buckets

```python
class MaterialCategory(str, Enum):
    NCERT      = "ncert"
    DPP        = "dpp"          # daily practice problems
    CPP        = "cpp"          # cumulative practice problems
    TOPIC_WISE = "topic_wise"   # chapter MCQs / topic drills
    PYQ        = "pyq"          # previous year questions
    NOTES      = "notes"        # theory, formula sheets
    OTHER      = "other"        # escape valve, audited
```

**Why:** fixed enums keep filters consistent across batches. Lets the
test composer write `WHERE category IN ('dpp', 'cpp')` without
worrying about typos like "DPP" vs "Daily Practice". Custom
per-batch buckets sound flexible but always end in 7 batches each
calling DPP something slightly different and the composer can't filter
cleanly. `OTHER` is the escape valve for genuinely odd items; if
`OTHER` count climbs past a threshold, that's a signal to add a new
enum value, not to open the floodgates.

---

## Data model

New / changed tables. All additions go in a single Alembic migration
to keep the rollback path clean.

### `materials` (new)

```sql
CREATE TABLE materials (
    id              UUID PRIMARY KEY,
    filename        VARCHAR(500) NOT NULL,    -- as uploaded
    storage_key     VARCHAR(800) NOT NULL UNIQUE,  -- "<year>/class-11/physics/dpp/<uuid>--file.pdf"
    mime_type       VARCHAR(120) NOT NULL,
    size_bytes      BIGINT NOT NULL,
    sha256          CHAR(64) NOT NULL,        -- dedup + integrity
    academic_year_id UUID REFERENCES academic_years(id),
    class_label     VARCHAR(8) NOT NULL,      -- "10" | "11" | "12" | "drop"
    subject_id      UUID NOT NULL REFERENCES subjects(id),
    topic           VARCHAR(120),             -- free text for now; canonicalize later
    category        VARCHAR(20) NOT NULL,     -- MaterialCategory enum
    exam_types      TEXT[] NOT NULL DEFAULT '{}',  -- ["neet", "jee_main", ...]
    description     TEXT,
    status          VARCHAR(20) NOT NULL DEFAULT 'uploaded',
        -- uploaded | ingesting | ingested | ingest_failed | archived
    ingest_error    TEXT,
    question_count  INTEGER NOT NULL DEFAULT 0,  -- denormalized for list view perf
    uploaded_by     UUID NOT NULL REFERENCES users(id),
    uploaded_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_deleted      BOOLEAN NOT NULL DEFAULT false
);

CREATE INDEX ix_materials_browse
    ON materials (academic_year_id, class_label, subject_id, category)
    WHERE is_deleted = false;

CREATE INDEX ix_materials_sha256 ON materials (sha256);
```

**Notes:**
- `sha256` lets the upload endpoint detect "you already uploaded this
  exact file" and refuse with a link to the existing material row.
- `question_count` is denormalized to keep the materials list page
  cheap; refresh on every successful ingest.
- `exam_types` as `TEXT[]` is fine until we need to filter by exam at
  scale; switch to a join table only if EXPLAIN says so.

### `material_batches` (new)

```sql
CREATE TABLE material_batches (
    material_id   UUID NOT NULL REFERENCES materials(id) ON DELETE CASCADE,
    batch_id      UUID NOT NULL REFERENCES batches(id) ON DELETE CASCADE,
    linked_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    linked_by     UUID NOT NULL REFERENCES users(id),
    PRIMARY KEY (material_id, batch_id)
);
```

### `questions` (extend)

```sql
ALTER TABLE questions
    ADD COLUMN material_id UUID REFERENCES materials(id),
    ADD COLUMN exam_types  TEXT[] NOT NULL DEFAULT '{}';

CREATE INDEX ix_questions_material ON questions (material_id);
CREATE INDEX ix_questions_exam_types ON questions USING GIN (exam_types);
```

- `material_id` is nullable so legacy 719 rows continue to work;
  backfill happens in the migration (match `source_ref`'s doc path
  against `materials.storage_key`).
- `exam_types` per question defaults to inheriting from the parent
  material at ingest time. Lets PYQ datasets tag individual questions
  more precisely later.

---

## Storage layout

```
study_material/
├── 2026-27/                      ← academic_year.code or .id
│   ├── class-11/
│   │   ├── physics/
│   │   │   ├── ncert/
│   │   │   │   └── <material-uuid>--work-energy-power.pdf
│   │   │   ├── dpp/
│   │   │   │   ├── <material-uuid>--week-1.pdf
│   │   │   │   └── <material-uuid>--week-2.pdf
│   │   │   ├── topic_wise/
│   │   │   ├── pyq/
│   │   │   ├── notes/
│   │   │   └── other/
│   │   ├── chemistry/...
│   │   ├── biology/...
│   │   └── mathematics/...
│   ├── class-12/...
│   └── drop/                      ← year-drop / repeater material
└── 2027-28/...
```

- Material UUID prefix avoids filename collisions and gives a path
  back to the DB row from the file alone.
- Directory layout is the canonical truth for *humans* SSHing in; the
  DB is the canonical truth for the application. The two are kept in
  sync by the `StorageBackend` write path — never by direct file
  manipulation.
- Existing `study_material/extracted/` content gets migrated into this
  layout as part of M1's data backfill.

---

## UI surfaces

### `/materials` — new admin page

Layout mirrors `/question-bank` (three-pane familiar to the user):

```
┌──────────────────────────────────────────────────────────────────┐
│  Study Materials                              [+ Upload]   ⌘K    │
│  ─────────────────────────────────────────────────────────────── │
│  ┌──────────────┐  ┌────────────────────────────┐  ┌──────────┐ │
│  │ FILTER RAIL  │  │ MATERIALS LIST             │  │ PREVIEW  │ │
│  │              │  │                            │  │          │ │
│  │ Year ▼       │  │ ☐ work-energy-power.pdf    │  │ filename │ │
│  │ Class ▼      │  │   class-11 · physics · ncert│  │ class    │ │
│  │ Subject ▼    │  │   3.2 MB · 120 questions   │  │ subject  │ │
│  │ Category     │  │                            │  │ category │ │
│  │  ◉ All       │  │ ☐ dpp-week-1.pdf           │  │ exams    │ │
│  │  ◯ NCERT     │  │   class-11 · physics · dpp │  │ batches  │ │
│  │  ◯ DPP       │  │   1.1 MB · 0 questions     │  │          │ │
│  │  ◯ CPP       │  │                            │  │ [Ingest] │ │
│  │  ◯ TopicWise │  │ ☐ ...                      │  │ [Link to │ │
│  │  ◯ PYQ       │  │                            │  │  batches]│ │
│  │  ◯ Notes     │  │                            │  │ [Delete] │ │
│  │              │  │                            │  │          │ │
│  │ Exam types   │  │                            │  │          │ │
│  │  ☐ NEET      │  │                            │  │          │ │
│  │  ☐ JEE Main  │  │                            │  │          │ │
│  │  ☐ JEE Adv   │  │                            │  │          │ │
│  │  ☐ Boards    │  │                            │  │          │ │
│  │              │  │                            │  │          │ │
│  │ Batches      │  │                            │  │          │ │
│  │  ☐ NEET-A    │  │                            │  │          │ │
│  │  ☐ JEE-B     │  │                            │  │          │ │
│  └──────────────┘  └────────────────────────────┘  └──────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

Sidebar entry: **Content → Materials** (sits above "Question Bank").

### Upload flow

Click `+ Upload` →

1. **Drag & drop multiple files.** Server returns sha256 per file
   during upload; if a file matches an existing material's sha256, the
   row in the dialog shows "Already exists — linking to <name>".
2. **Bulk-set tags**: year (default = current academic year), class
   dropdown, subject dropdown, category radio group, exam_types
   checkboxes, batches multi-select.
3. **Per-file overrides**: collapse-able row for each file lets the
   user override topic / category individually.
4. **Submit**: server writes files, creates `materials` rows, links to
   batches, and queues an ingest job per file.

Auto-ingest by default; admin can untick "Ingest now" to defer (handy
for Notes / PDFs that have no questions to extract).

### `/question-bank` — add facets

Extend the left filter rail. New facets above the existing
Status / Difficulty / Source group:

- **Class** (radio: All / 10 / 11 / 12 / Drop)
- **Subject** (dropdown)
- **Topic** (typeahead, populated from distinct topics within filtered
  subject)
- **Exam type** (chips: NEET / JEE Main / JEE Adv / Boards / CET / ...)
- **Batch** (typeahead, optional — "questions linked to this batch's
  materials")
- **Material** (typeahead — drills down to one PDF's questions)

Backend exposes facet counts so each option shows `(123)` next to it
and zeroes are dimmed. Same pattern as the current Source facet.

### Test composer — query the bank by these facets

When the admin builds a DPP / CPP / Test:

- "Pick from NEET-tagged Class-11 Physics, topic = Mechanics,
  difficulty = Medium, 30 questions" → one query.
- "All questions linked to NEET-A batch's materials, excluding ones
  used in last 2 papers" → one query (composer already tracks paper
  history per `docs/question-bank-and-dpp-roadmap.md`).

The composer doesn't need to know about files — it queries
`questions` with the new joins.

---

## Implementation phases

Each phase ships as one or two focused PRs. Don't bundle.

### M1 — Schema, storage backend, upload API

- Alembic migration: `materials`, `material_batches`, extend
  `questions`.
- `app/core/storage/` with `StorageBackend` interface +
  `LocalFilesystemBackend`.
- `POST /api/v1/materials` (multipart upload), `GET /api/v1/materials`
  (list + facets), `GET /api/v1/materials/{id}`, `POST
  /api/v1/materials/{id}/ingest`, `DELETE /api/v1/materials/{id}`.
- Backfill task: walk `study_material/extracted/` and create
  `materials` rows for the existing 8 PDFs, then run
  `UPDATE questions SET material_id = ... WHERE source_ref LIKE ...`.
- Tests: upload happy path, dedup-on-sha256, list + facet counts,
  ingest queued, backfill idempotent.
- **Definition of done**: existing 719 questions all have
  `material_id` set; nothing else changes.

### M2 — Materials browser UI

- `/materials` page (three-pane).
- Upload modal with drag-drop, bulk + per-file tagging, batch linking.
- Preview pane: file metadata, "Ingest", "Re-ingest", "Link to
  batches", "Delete" (soft).
- File preview: PDF inline via iframe; images inline; Word/text shows
  a "Download" CTA.
- Sidebar wiring: add **Materials** entry under Content.
- **Definition of done**: admin can upload 5 new PDFs end-to-end via
  the UI and see them in the list, sorted by class → subject →
  category.

### M3 — Question Bank facets

- Backend: add `class`, `subject`, `topic`, `exam_type`, `batch`,
  `material_id` query params to `GET /api/v1/questions`.
- Backend: facet endpoint `GET /api/v1/questions/facets` returns
  counts per filter option for the current filter set.
- Frontend: extend the filter rail with the new facets; preserve URL
  state so filters are linkable.
- **Definition of done**: admin can filter "Class-11 Physics NEET DPP
  Medium" and get the matching question list.

### M4 — Batch linkage in test composer

- Composer reads from same facet API; defaults to "this batch's linked
  materials" when composing for a specific batch.
- "Available questions" counter updates live as facets change.
- **Definition of done**: composing a DPP for NEET-A only surfaces
  questions from materials linked to that batch (or globally tagged
  NEET).

Each phase is 1–3 dev days. M1 unblocks M2–M4.

---

## Open questions

These don't block M1. Resolve before the phase that needs them.

- **Auto-ingest on upload**: M1 ships with manual "Ingest" button. M2
  will add a checkbox in the upload modal; M3 may switch the default
  to `true` once ingest is reliable end-to-end.
- **Topics taxonomy**: free-text `topic` column for now. When we hit
  ~20 batches with inconsistent topic strings, promote to a canonical
  `topics` table and run a normalization pass.
- **Quotas / limits**: not enforced in M1. Add per-day upload caps and
  total storage caps in a later tier if abuse becomes real.
- **Deletion semantics**: soft-delete in M1 (`is_deleted = true`,
  storage file kept). Hard-delete (purge file + cascade-soft-delete
  questions) as a later admin action.
- **Multi-branch / multi-tenant**: out of scope. Today one Postgres
  database = one institute. If we go multi-tenant, materials gain a
  `tenant_id` and storage paths get prefixed.
- **OCR for images / scanned PDFs**: not in M1. The current ingest
  pipeline (`ingest_studymat.py`, `extract_keys_ai.py`,
  `derive_missing_answers.py`) already handles text + vision via
  Gemini; the same pipeline runs against any material flagged
  category=NCERT/PYQ/TopicWise. Images uploaded under category=Notes
  don't get ingested unless explicitly requested.

---

## Relationship to existing roadmaps

- `coaching-test-loop-roadmap.md` Tiers 11–16: untouched. This doc is
  the layer underneath the question bank that those tiers already
  assume exists.
- `question-bank-and-dpp-roadmap.md`: the generation + composer +
  print + OMR pipeline reads from `questions`. That doesn't change;
  this doc just gives questions a richer set of facets to be filtered
  by.
- `copilot-review-and-refinements.md` Tier 11.6: orthogonal — that
  covers teacher productivity scoring; this covers content.

When in doubt: this doc owns "how content gets in"; the question-bank
roadmap owns "how questions get out into papers".
