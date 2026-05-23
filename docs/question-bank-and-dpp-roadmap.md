# Question Bank Generator + DPP/CPP Workflow — roadmap

Companion to `docs/coaching-test-loop-roadmap.md`. That roadmap covered
Tiers 11–16 (the data plumbing for tests, student responses, and analytics).
**This** doc covers the operational workflow on top of it: how
questions actually get into the question bank, how DPP/CPP papers get
composed and printed at the branch, how OMR sheets close the loop, and
how the analytics layer reads all of it together.

Saved 2026-05-24 in response to a clear product brief:

> Question bank generator using DeepSeek + Gemini APIs; DPP/CPP tabs in
> the admin portal with teacher validation before print; branded
> question papers + paper-code-specific answer keys; OMR sheets that
> can be cross-checked and uploaded back to the portal; student
> progress analytics that correlate teacher activity + attendance +
> tests as the *core* of the platform.

---

## The end-to-end workflow this builds

```
              ┌─────────────────────────────────────────┐
              │   PYQ DATASETS (free, MIT/govt source)  │
              │   JEEBench • JEE Mains PYQs • NCERT     │
              │   Exemplar • NEET PYQs                  │
              └────────────────────┬────────────────────┘
                                   │  ingest
                                   ▼
┌──────────────────────────────────────────────────────────────┐
│             QUESTION BANK GENERATION PIPELINE                │
│                                                              │
│   ┌──────────────┐    ┌────────────────┐    ┌────────────┐   │
│   │ Track A      │    │ Track B        │    │ Track C    │   │
│   │ PYQ variants │    │ Fresh text Qs  │    │ Diagram-   │   │
│   │ (DeepSeek)   │    │ (DeepSeek)     │    │ aware (Gem)│   │
│   └──────┬───────┘    └────────┬───────┘    └─────┬──────┘   │
│          └────────────┬────────┴───────────────────┘         │
│                       ▼                                      │
│               LLM-as-Judge grading                           │
│                       │                                      │
│                       ▼                                      │
│            Auto-checks (answer in options,                   │
│             distractor plausibility, leakage)                │
│                       │                                      │
│                       ▼                                      │
│              Human review queue                              │
│                       │                                      │
│                       ▼                                      │
│         APPROVED → questions table                           │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         ▼
┌────────────────────────────────────────────────────────────┐
│         DPP / CPP / TEST COMPOSER (admin portal)           │
│                                                            │
│   Filter (batch · subject · chapter · topic · difficulty)  │
│   AI-suggest or hand-pick from bank                        │
│   Save as draft                                            │
└────────────────────────┬───────────────────────────────────┘
                         │
                         ▼
                Teacher validation
                (assign, review, approve)
                         │
                         ▼
┌────────────────────────────────────────────────────────────┐
│              PDF + OMR GENERATION                          │
│                                                            │
│   Question paper PDF (branded header, paper code)          │
│   Answer key PDF (one per paper code, internal)            │
│   OMR sheet PDF (matched layout, paper-code + student-ID   │
│   bubbles)                                                 │
└────────────────────────┬───────────────────────────────────┘
                         │
                         ▼ conduct test
                         │
                         ▼
┌────────────────────────────────────────────────────────────┐
│              OMR INTAKE                                    │
│                                                            │
│   v1: CSV upload (student_id, q1..qN bubble selections)    │
│   v2: Image scan + OCR parser                              │
│                                                            │
│   → StudentResponse rows                                   │
│   → Auto-aggregate to StudentMark                          │
└────────────────────────┬───────────────────────────────────┘
                         │
                         ▼
┌────────────────────────────────────────────────────────────┐
│           STUDENT PROGRESS ANALYTICS                       │
│           (the actual "core" of the platform)              │
│                                                            │
│   Per-student: attendance × topic mastery × weakness map   │
│   Per-batch: chapter-wise performance over time            │
│   Per-teacher: did your students improve on YOUR topics?   │
│   Trend lines: Test 1 → 2 → 3 trajectory                   │
└────────────────────────────────────────────────────────────┘
```

---

## Phase A — Question Bank Generation Pipeline

### A.1 Provider strategy: DeepSeek + Gemini, complementary roles

You have API keys for both. They have non-overlapping strengths.

| Capability | Use **DeepSeek** | Use **Gemini** |
|---|---|---|
| Bulk text MCQ generation (concept, theory, numerical) | ✅ Primary | — |
| LaTeX equation generation | ✅ Primary | ✅ Backup |
| Step-by-step solution generation | ✅ Primary | ✅ Backup |
| PYQ variant generation (parameterize numbers) | ✅ Primary | — |
| LLM-as-judge for generated question quality | ✅ Primary | ✅ Cross-validate |
| **Reading PYQ diagrams** (vision) | — | ✅ Primary |
| **Reading scanned PYQ PDFs** (multimodal OCR) | — | ✅ Primary |
| **Generating questions that REUSE an existing diagram** | — | ✅ Primary |
| **Reading OMR sheet images** (Phase D v2) | — | ✅ Primary |
| Topic auto-tagging (semantic) | ✅ Primary | ✅ Backup |
| Final answer-key cross-check (independent verification) | ✅ Cross-validate | ✅ Cross-validate |

**Why two providers, not one**: cross-validation. Generate with DeepSeek,
grade with Gemini (or vice versa). If both agree, ship. If they disagree,
queue for human review. This catches hallucinations cheaply.

Cost is also a factor — DeepSeek pricing is ~10× cheaper than GPT-4 for
comparable reasoning, Gemini Flash is similarly aggressive on multimodal.
A 50k-question bank should cost **under ₹20,000 ($240)** with this stack.

### A.2 Three generation tracks (run in parallel)

#### Track A — PYQ variants (highest leverage)

**Input**: existing PYQ from `questions` table (with its diagram if any)
**Output**: 2–4 variants that test the same concept

```
PROMPT TO DEEPSEEK:

You are an expert JEE/NEET question writer. Given this original PYQ,
produce 3 variants that test the same underlying concept but differ in:
- Numerical values (if numerical)
- Phrasing of the setup
- Which quantity is being asked

Constraints:
- Keep the same difficulty level
- Keep the same chapter and topic
- Each variant must have exactly one correct answer
- Distractors must be plausible (common student mistakes)
- Output as JSON with: question_text, options[], correct_answer,
  explanation, difficulty, blooms_taxonomy

Original PYQ:
{question_text}
{options}
Correct: {correct_answer}
Topic: {topic}
```

**Volume target**: each PYQ → 3 variants. Bootstrap pool of 18,000 PYQs →
**~54,000 variant questions** over 3 months.

**Critical**: variants must NOT use the original's diagram unless we
explicitly want a Track-C-style reuse. Track A is text-only.

#### Track B — Fresh text-only questions

**Input**: (chapter, topic, difficulty, blooms_level, target_count)
**Output**: N original conceptual MCQs

```
PROMPT TO DEEPSEEK:

You are writing JEE/NEET-standard MCQs.

Topic: {topic} (chapter: {chapter}, subject: {subject})
Difficulty: {difficulty}  (EASY | MEDIUM | HARD)
Bloom's level: {blooms}  (REMEMBER | UNDERSTAND | APPLY | ANALYZE)
Count: {n}

Rules:
- Each question must have exactly 4 options, one correct
- No diagram-dependent questions in this batch
- Distractors must reflect common misconceptions, not random wrongness
- Provide a step-by-step explanation under 100 words
- Use LaTeX for equations: $...$ inline, $$...$$ display
- Output JSON array

Each item: {
  "question_text": "...",
  "options": ["...", "...", "...", "..."],
  "correct_answer": "B",
  "explanation": "...",
  "difficulty": "...",
  "blooms_taxonomy": "...",
  "concept_tags": ["...", "..."]
}
```

**Volume target**: 100 questions/day with one reviewer → ~30,000/year.

#### Track C — Diagram-reuse via Gemini Vision

**Input**: PYQ image (diagram-bearing question)
**Output**: 2–3 fresh questions that reuse the same diagram

```
PROMPT TO GEMINI VISION:

[Image: original PYQ with diagram]

This is a JEE/NEET physics question with an essential diagram.

Step 1: Describe the diagram in technical detail (objects, labels,
geometry, key variables).

Step 2: Generate 3 alternative questions that REUSE the same diagram
but ask different things:
- Change the asked quantity
- Change one input variable's value
- Ask about a related concept the same diagram supports

Output JSON:
{
  "diagram_summary": "...",
  "variants": [
    {
      "question_text": "Refer to the figure. ...",
      "options": [...], "correct_answer": "...", "explanation": "..."
    },
    ...
  ]
}
```

The original diagram image stays attached to all variants via a
`diagram_ref` column on `questions`.

**Volume target**: ~50% of PYQs have diagrams → ~9,000 PYQs × 3 variants
= **~27,000 diagram-reuse questions**.

### A.3 Quality gates (every generated question must pass)

After generation, before insertion:

1. **Auto-checks (Python)**:
   - `correct_answer` is in `options`
   - Question text doesn't leak the answer (e.g., "What is the value
     of acceleration? (A) 5 (B) 10... since acceleration is 10...")
   - Exactly 4 options
   - LaTeX renders without error
   - Length sanity check (50–800 chars for question_text)

2. **LLM-as-judge cross-check**:
   - Send the question to the *other* provider (Gemini if generated
     by DeepSeek, and vice versa)
   - Ask: "Solve this question independently. Is the marked correct
     answer actually correct? Are the distractors plausible? Score
     0–10 on quality."
   - Threshold: score ≥ 7 to auto-approve, 4–6 to human queue, <4 reject

3. **Topic confidence**:
   - Embed the question, find nearest neighbors among existing
     known-tagged questions
   - If top-1 neighbor cosine similarity > 0.85: auto-tag
   - Otherwise: human queue

4. **Deduplication**:
   - Embedding similarity ≥ 0.93 against existing question → reject
     (it's a duplicate of something already in the bank)

5. **Human review queue**:
   - Anything that fails any gate goes here
   - Admin sees a table of pending questions; review UI allows
     edit / approve / reject in bulk

### A.4 Topic mapping

The questions table already has `subject_id`, `topic_id`. For incoming
generated questions:

- AI-generated: prompt includes topic, so we know it
- PYQ ingest: source dataset usually has chapter info; map to your
  internal topics via fuzzy + LLM disambiguation pass

Pre-build a topic map JSON: `{"Mechanics": "<topic_id>", ...}` keyed on
your existing `topics` table. Generation always emits the topic name;
the ingest pipeline resolves to the UUID.

### A.5 Storage & schema additions

Minor extension to existing `Question` model:

```sql
ALTER TABLE questions ADD COLUMN source TEXT;          -- "PYQ-JEEMAIN-2019" | "AI-DEEPSEEK" | "AI-GEMINI" | "HUMAN"
ALTER TABLE questions ADD COLUMN source_ref TEXT;      -- e.g. "JEE-MAIN-2019-SHIFT1-Q47"
ALTER TABLE questions ADD COLUMN diagram_ref TEXT;     -- S3/local path to image, NULL if text-only
ALTER TABLE questions ADD COLUMN review_status TEXT;   -- "approved" | "pending_review" | "rejected"
ALTER TABLE questions ADD COLUMN quality_score FLOAT;  -- 0..10 from LLM-as-judge
ALTER TABLE questions ADD COLUMN generated_at TIMESTAMPTZ;
```

Plus a small `question_generation_jobs` table tracking each batch run
(provider, prompt template, count, success rate) for observability.

### A.6 Concrete pipeline steps to build

```
1. Ingest scripts (standalone, run from CLI or admin button):
     scripts/ingest_jeebench.py
     scripts/ingest_jee_mains_pyqs.py
     scripts/ingest_ncert_exemplar.py  (PDF parser using Gemini)
     scripts/ingest_neet_pyqs.py        (PDF parser using Gemini)

2. Generation scripts:
     scripts/generate_variants.py       (Track A — input: question IDs)
     scripts/generate_fresh.py          (Track B — input: topic + count)
     scripts/generate_diagram_reuse.py  (Track C — input: question IDs w/ diagrams)

3. Quality gates module:
     app/modules/questionbank/services/quality.py
       - run_auto_checks(question)
       - run_llm_judge(question, provider="gemini" | "deepseek")
       - topic_confidence(question)
       - is_duplicate(question)

4. Admin UI:
     /question-bank — browse, filter, search
     /question-bank/review — pending review queue with batch approve
     /question-bank/generate — launch generation job (topic, count, track)
     /question-bank/jobs — observability for past runs
```

### A.7 Cost model

Conservative estimates (DeepSeek Coder/Reasoner + Gemini Flash, late 2026 rates):

| Stage | Per question | Volume | Cost |
|---|---|---|---|
| Track A variant generation | ~$0.001 | 30,000 | ~$30 |
| Track B fresh generation | ~$0.002 | 30,000 | ~$60 |
| Track C diagram-reuse | ~$0.005 | 20,000 | ~$100 |
| LLM-as-judge (every Q) | ~$0.001 | 80,000 | ~$80 |
| **Total for ~80k question bank** | | | **~$270** (~₹22,500) |

Add human reviewer cost: 1 reviewer × 100 Q/day × 60 days × ₹500/day =
₹30,000 (~$360). **Grand total ~$630 (~₹52,500)** for an
exam-realistic ~80k question bank.

---

## Phase B — DPP/CPP Composer + Teacher Validation

### B.1 Concepts

| Paper type | Length | Source | Frequency | Purpose |
|---|---|---|---|---|
| **DPP** (Daily Practice Paper) | 10–15 Q | Today's lecture topic | Daily | After class drill |
| **CPP** (Class Practice Paper) | 5–10 Q | Last 2–3 topics | 2–3×/week | In-class quick drill |
| **Chapter Test** | 30–50 Q | Full chapter | Weekly/biweekly | Chapter assessment |
| **Full Test / Mock** | 90–180 Q | Full syllabus or part | Monthly | Exam-realism practice |

### B.2 UI design

New admin route `/papers` with three tabs: **DPP · CPP · Tests**.

```
┌─ Compose paper ──────────────────────────────────────────────┐
│  Type:  [DPP ▼]                                              │
│  Batch: [NEET 2025-A ▼]                                      │
│  Subject: [Physics ▼]                                        │
│  Chapter: [Mechanics ▼]   Topic: [Newton's Laws ▼ optional]  │
│                                                              │
│  Mix:    Easy [4] · Medium [6] · Hard [2]   Total: 12        │
│                                                              │
│  Source: ◉ Auto-pick from bank   ○ Manual select             │
│          [Generate]                                          │
└──────────────────────────────────────────────────────────────┘

┌─ Preview ────────────────────────────────────────────────────┐
│  12 questions selected. Each card shows: text, options,      │
│  correct answer, swap/remove. Click "Reshuffle" to re-pick   │
│  from the same filter.                                       │
└──────────────────────────────────────────────────────────────┘

┌─ Validation ─────────────────────────────────────────────────┐
│  Assign to teacher: [Rahul Sharma ▼]                         │
│  [Send for validation]                                       │
└──────────────────────────────────────────────────────────────┘
```

### B.3 Teacher validation flow

Teacher gets a notification (in-app + later via email/WhatsApp Tier 16).
Lands on `/papers/{paper_id}/validate`:

- Each question rendered as it'll appear on the printed paper
- Per question: ✓ Approve · ✎ Edit · ✗ Remove · ⟲ Swap with another
- Bottom: **Approve paper** (only enabled when all questions reviewed)
- Status flows: `draft → pending_validation → approved → printed → conducted → graded`

### B.4 Schema additions (Tier 12.5)

```sql
CREATE TABLE papers (
  id UUID PRIMARY KEY,
  paper_type TEXT,             -- DPP | CPP | TEST | MOCK
  paper_code TEXT,             -- "PHY-NEET-A-DPP-20260524-A" (for OMR matching)
  batch_id UUID,
  subject_id UUID,
  chapter_id UUID,             -- nullable for multi-chapter mocks
  status TEXT,                 -- draft | pending_validation | approved | printed | conducted | graded
  draft_created_by UUID,       -- admin who composed
  validation_assigned_to UUID, -- teacher
  validated_at TIMESTAMPTZ,
  approved_by UUID,
  brand_name TEXT,             -- "Bright Future Coaching"
  branch_id UUID,
  academic_year_id UUID,
  created_at, updated_at, is_deleted
);

CREATE TABLE paper_questions (
  id UUID PRIMARY KEY,
  paper_id UUID,
  question_id UUID,
  position INTEGER,
  marks_allocated FLOAT,
  branch_id UUID
);

-- Existing tests/student_marks tables continue to track the "results"
-- side; papers is the "blueprint" side. A paper that gets conducted
-- creates a row in tests pointing back to paper_id.
```

`paper_code` is the magic string that ties question paper, answer
key PDF, and OMR sheet together. Generated as
`{SUBJECT_CODE}-{BATCH_CODE}-{TYPE}-{YYYYMMDD}-{VARIANT_LETTER}` so
multiple OMR variants of the same paper can coexist (A/B/C/D shuffles
to prevent cheating).

### B.5 OMR variants for cheating prevention

For each paper, generate **4 variants** (A, B, C, D) with the same
questions in shuffled order. Same `paper_id`, four `paper_code`s. Each
student gets a random variant; the answer key for each variant is
different. Mature coaching institutes universally do this.

---

## Phase C — PDF Generation (branded papers + OMR sheets)

### C.1 Library choice: **WeasyPrint**

WeasyPrint renders HTML/CSS → PDF with strong MathJax support. The
alternative is ReportLab (lower level, more work). WeasyPrint wins
because:

- HTML templates are easier to maintain
- MathJax/KaTeX renders LaTeX equations as the same browser-renderable
  output the admin saw in preview
- CSS controls branding (header logo, color, paper code in corner)

### C.2 Three PDFs per paper

| PDF | Audience | Content |
|---|---|---|
| **Question paper** | Students | Branded header, paper code, questions in shuffled order, OMR instructions footer |
| **Answer key** | Internal | One row per question with correct option + step-by-step solution |
| **OMR sheet** | Students | Bubble grid (60Q standard, expandable), paper-code bubbles at top, student-ID bubbles |

Each PDF generated by a Jinja2 template:

```
backend/app/modules/papers/templates/
  question_paper.html      → branded layout, MathJax math, image refs to diagrams
  answer_key.html          → table format, internal-only
  omr_sheet.html           → SVG bubble grid, OMR-scanner-friendly anchor marks
```

### C.3 Branding configuration

Store on `branch` table (new column `brand_settings` JSONB):

```json
{
  "name": "Bright Future Coaching",
  "logo_url": "/uploads/branch/{id}/logo.png",
  "primary_color": "#1e40af",
  "address": "...",
  "footer_text": "Best of luck • www.brightfuture.in"
}
```

PDF templates pull from this. Admin sets it once on `/branch/settings`.

### C.4 OMR sheet layout (v1 — standard)

Standard A4 page:

- **Top band**: institute brand + paper code as 6-character bubble grid
  (`PHYDP1` etc.) — scanner reads paper_code from bubbles
- **Student ID band**: 8-digit student ID bubbles
- **Body**: 60 questions × 4 options (A/B/C/D), 4 columns of 15 rows
- **Anchor marks**: corner crosses for scanner alignment
- **Below 60Q**: extension page on demand for 90/180 Q papers

### C.5 PDF generation route

```
POST /api/v1/papers/{paper_id}/generate-pdf
  → returns three signed URLs (question / answer key / OMR sheet)
  → stores PDFs in /uploads/papers/{paper_id}/{variant}/
  → only callable when paper.status = approved
  → transitions paper.status → printed
```

---

## Phase D — OMR Intake & Cross-Check

### D.1 Two versions

**v1 (this slice)** — **CSV upload mimicking OMR scan output**:

- Branch scans physically (Addmen, ScoreExam, Verificare etc. — any
  existing tool the user has)
- Tool exports CSV: `student_id, paper_code, q1, q2, ..., qN` (option
  selected per question)
- Admin uploads CSV to portal
- Backend validates `paper_code`, matches student, computes correctness
  against answer key, writes `student_responses` + recomputes
  `student_marks`

**v2 (deferred)** — **Image upload + in-house OMR parser**:

- Upload scanned page images
- OpenCV-based bubble detection (open source, well-trodden path)
- Same output as v1
- Eliminates the dependency on external OMR software

### D.2 v1 CSV schema

```csv
paper_code,student_id,q1,q2,q3,q4,q5,...
PHY-NEET-A-DPP-20260524-A,STU0001,A,C,B,D,A,...
PHY-NEET-A-DPP-20260524-A,STU0002,B,C,B,D,C,...
```

Upload UI on `/papers/{id}/results`:
- Drag-and-drop CSV
- Preview parse with row count
- Highlight rows where `paper_code` doesn't match this paper
- Submit → backend processes async, shows progress

### D.3 Backend processing

```python
async def process_omr_csv(paper_id, csv_rows):
    paper = await get_paper(paper_id)
    answer_key = await get_answer_key(paper_id)  # {position: correct_option}
    questions = await get_paper_questions(paper_id)  # ordered

    for row in csv_rows:
        # Validate variant
        if row.paper_code != paper.code:
            errors.append(...)
            continue

        # Build StudentResponse rows
        for position, selected in enumerate(row.answers, start=1):
            q = questions[position - 1]
            is_correct = (selected == answer_key[position])
            marks = q.marks_allocated if is_correct else 0.0
            create_student_response(...)

        # Aggregate to StudentMark
        total = sum_correct_marks
        create_or_update_student_mark(student_id, paper.test_id, total)

    paper.status = "graded"
```

This is the Tier 11 endpoint (`POST /tests/{id}/responses`), generalized
for paper-coded variants.

### D.4 Cross-check guards

- Rejected if uploaded `paper_code` doesn't exist
- Rejected if student_id not in paper's batch
- Warning (not rejection) if answer count ≠ paper's question count
- Audit log every upload with file hash + admin user

---

## Phase E — Student Progress Analytics (the core)

Once student_responses are populated by Phases A–D, the analytics layer
*finally* has real signal. This is what the platform exists for.

### E.1 Per-student signals available

| Signal | Source |
|---|---|
| Attendance per subject | `lecture_attendance_mappings` already populated |
| DPP completion rate | `student_responses` joined to `papers` |
| Test scores history | `student_marks` over time |
| Per-topic mastery | `student_responses` joined to `question_topics` — % correct per topic |
| Weakness map | topics where mastery < 50% |
| Improvement velocity | slope of avg score over last N tests |
| Days since last test | freshness indicator |
| Upcoming chapter tests | `tests` table filtered by batch + scheduled_at |

### E.2 New page: `/students/[id]` (Tier 13 from the other roadmap)

```
Aman Sharma · STU-0042 · NEET 2025-A
Enrolment: Jun 2025 · Parent: 98xxxxx2

ATTENDANCE (last 30 days)
Physics:   78%  ▓▓▓▓▓▓▓░░░
Chemistry: 92%  ▓▓▓▓▓▓▓▓▓░
Biology:   45%  ▓▓▓▓░░░░░░  🔴

TEST PERFORMANCE TIMELINE (last 6 tests)
   ━━━━━━━●━━━━●━━━━━━━●━━━━━━●━━━━━━━━●━━━━━●
    65   72   68   75   71   80    avg: 71.8

TOPIC MASTERY HEATMAP
Physics
  Newton's Laws    ████████ 82%    Mechanics    ███████  70%
  Optics           ██░░░░░░ 24% 🔴 Modern Phys  █████░░░ 55%
  Thermodynamics   ██████░░ 65%    Waves        ███░░░░░ 35% 🔴

WEAKNESS LIST (auto-flagged for makeup / remedial)
  🔴 Optics — 24%, last test 2 weeks ago, chapter test in 6 days
  🔴 Waves  — 35%, hasn't been re-tested in 4 weeks
  🟡 Genetics — 48%, downward trend over 3 tests

UPCOMING
  Physics chapter test on June 1 (covers Optics + Waves — weak topics)
  → recommend: DPP-20260527 (Optics drill) was generated, not assigned
```

### E.3 Per-batch analytics extension

On `/insights`, add tabs:

- Adherence (existing)
- Outcomes (Tier 9)
- **Topic mastery** (new): per-batch heatmap of subject × chapter,
  derived from `student_responses` joined to `question_topics`
- **Item analysis** (new): per-question difficulty observed vs. tagged
  — flags questions that are too easy/hard for the bank

### E.4 The correlation question (the actual moat)

The single most valuable query the platform should answer:

> *"Did students who attended Rahul's Mechanics lectures score better
> on Mechanics topic in the most recent chapter test than students who
> attended Priya's Mechanics lectures?"*

SQL sketch:

```sql
SELECT 
  effective_teacher AS teacher,
  AVG(student_mastery_pct) AS avg_mastery,
  COUNT(DISTINCT student_id) AS n
FROM (
  SELECT 
    COALESCE(l.actual_teacher_id, l.teacher_id) AS effective_teacher,
    a.student_id,
    SUM(CASE WHEN sr.is_correct THEN 1 ELSE 0 END) * 100.0 /
      COUNT(*) AS student_mastery_pct
  FROM lectures l
  JOIN lecture_attendance_mappings a ON a.lecture_id = l.id
  JOIN student_responses sr ON sr.student_id = a.student_id
  JOIN questions q ON q.id = sr.question_id
  JOIN question_topics qt ON qt.question_id = q.id
  WHERE l.topic_id IN (topics_in_chapter('Mechanics'))
    AND qt.topic_id IN (topics_in_chapter('Mechanics'))
    AND a.attendance_status = 'PRESENT'
    AND l.lecture_status = 'completed'
    AND sr.submitted_at > l.scheduled_start  -- response came AFTER attending
  GROUP BY effective_teacher, a.student_id
) sub
GROUP BY effective_teacher
ORDER BY avg_mastery DESC;
```

This is what the user means by "core" — the platform's value isn't
recording these things, it's *correlating* them.

---

## Tier sequence (revised, integrating both roadmaps)

| Tier | Phase | What | Effort |
|---|---|---|---|
| **11** | E foundation | `student_responses` table + bulk CSV upload + auto-rollup to `student_marks` | 1 day |
| **11.5** | A.5 | Question table extensions (source, diagram_ref, review_status, quality_score) + migration | half day |
| **12** | A | Question bank ingest scripts (JEEBench, JEE Mains PYQ DB, NCERT Exemplar parser) | 2–3 days |
| **12.5** | A | Generation pipeline (DeepSeek + Gemini providers, 3 tracks, quality gates) | 3–4 days |
| **12.7** | A | Admin UI: question bank browser + review queue + generation launcher | 2 days |
| **13** | B | `papers` table + DPP/CPP/Test composer UI + teacher validation flow | 3 days |
| **13.5** | B.5 | OMR variant generation (4 shuffles per paper) | 1 day |
| **14** | C | WeasyPrint integration: question paper PDF, answer key PDF, OMR sheet PDF, brand settings | 3 days |
| **15** | D | CSV upload intake → `student_responses` → auto-aggregate, cross-check | 2 days |
| **16** | E | `/students/[id]` detail page (attendance, mastery heatmap, weakness list, upcoming) | 2 days |
| **17** | E | Item analysis + topic mastery sections on `/insights` | 2 days |
| **18** | E | Teacher × topic mastery correlation (the SQL above, rendered on `/teachers/[id]` and `/insights`) | 1 day |
| **19** | D v2 | OMR image scan parser (OpenCV) | 1 week |
| **20** | (future) | SMS/email/WhatsApp notifications on paper publish | 3–5 days |

**Estimated calendar**: 5–6 weeks for Tiers 11–18 (the operational core).
Tiers 19–20 deferred until 11–18 are proven in real institute use.

---

## Risks & open decisions

### 1. PDF rendering of LaTeX equations

WeasyPrint doesn't natively render MathJax — needs a pre-render step
that converts LaTeX to SVG (via Python `mathjax-node` shell-out or
`katex` Node helper). Worth verifying with a 1-day spike before
committing.

**Mitigation**: server-side LaTeX → SVG via `latex2svg` Python lib +
inline in HTML. Alternative: use **Typst** instead of LaTeX (newer,
faster, simpler).

### 2. OMR variant shuffle answer-key tracking

When questions shuffle between variants, the answer key must shuffle
too. Storing `paper_questions(position, paper_variant)` resolves this
but doubles row count per paper. Acceptable for the scale.

### 3. Diagram storage & rendering

Question diagrams come from PYQ datasets as images. We need:

- Storage: local `/uploads/diagrams/` (cheap), or S3/CDN later
- Rendering in question paper PDF: `<img src>` works
- Rendering in admin browser: same
- Rendering in OMR: not applicable

**Mitigation**: Hash each diagram on ingest; dedupe by hash; store
once even if reused across many questions.

### 4. AI hallucination on numerical answers

LLMs sometimes generate questions where the math doesn't actually work
(answer doesn't match the setup). LLM-as-judge catches most but not
all.

**Mitigation**:
- For numerical questions, optionally pass through SymPy to verify the
  computed answer matches the stated correct answer
- Higher human-review rate (5–10% sampling) on numerical-tagged Qs

### 5. Cost overruns on generation

If a generation run misbehaves (infinite loop, runaway batch), costs
escalate fast.

**Mitigation**:
- Hard caps per job in `question_generation_jobs` table
- Per-key spend alerts on DeepSeek + Gemini dashboards
- Human approval required before launching jobs > 1,000 questions

### 6. Topic vocabulary alignment

PYQ datasets use their own topic taxonomies. Yours uses
`topics.name`. Mismatch causes mistagging.

**Mitigation**: One-time mapping job: `{external_topic_name → internal_topic_id}`,
reviewed by a teacher before bulk ingest.

---

## Where to start (concrete first slice)

**Week 1 — Tier 11 + 11.5 + start of 12**:

1. Migration 0023 adds `student_responses` table + `Question`
   extensions (source, diagram_ref, review_status, quality_score)
2. Repository + service for `student_responses` (bulk insert, auto-rollup)
3. Endpoint `POST /api/v1/papers/{paper_id}/responses` (or `tests/{id}`
   for backward compat)
4. CLI: `python scripts/ingest_jeebench.py` — first real PYQs in the
   bank
5. Seed extension creating realistic per-question responses for the
   demo tests, so the topic mastery views have data to render

This gets the data model + first batch of real PYQs in the database.
Then we attack the generation pipeline (12, 12.5, 12.7) and the
DPP/CPP composer (13).

---

## Integration with existing surfaces

| Surface | What changes when this ships |
|---|---|
| `/home` | "DPPs needing validation" + "Tests results uploaded today" cards |
| `/today` | "DPPs / CPPs / Tests scheduled today" — already in `tests` table, extended for `papers` |
| `/lectures` | Each completed lecture gets a "Generate DPP" button → composes a DPP for today's topic |
| `/insights` | New tabs: Topic mastery, Item analysis |
| `/teachers/[id]` | New section: "Students attending your lectures perform X% better on your topics" (the correlation query) |
| `/students/[id]` | NEW — the per-student detail page (Tier 16) |
| `/question-bank` | NEW — browse, generate, review questions |
| `/papers` | NEW — DPP / CPP / Tests composer + validation queue |
| `/branch/settings` | NEW — brand config (logo, colors, footer text) |

This roadmap completes the platform's transformation from "lecture
tracker" to "coaching operations system."
