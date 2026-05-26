# Coaching Test Loop — roadmap (Tiers 11–16)

A coaching institute's operational core is **tests → scoring → student
progress → weakness identification**, not just lecture management. The
Plan-vs-Actual work (Tiers 1–9, plus home/today/teacher polish) covers
the lecture half well. This roadmap closes the test/student-progress
half.

Saved 2026-05-24 after a structural audit triggered by feedback that
the test conduction workflow and per-student progress tracking were
underbuilt versus mature systems (BYJU's, Vedantu, eTutor, Gyanam,
NEETprep, Addmen, ScoreExam).

---

## What the real coaching test loop looks like

Mature institutes (researched against the platforms above) follow this
sequence:

1. **Question bank** with each item tagged: subject, chapter, topic,
   difficulty, Bloom's level, concept tags
2. **Test paper generation** — pull from bank by filter (chapter-wise /
   topic-wise / DPP / CPP / mock)
3. **Conduct test** — printed OMR sheet at branch
4. **OMR scan** — software reads bubbles, compares to answer key,
   computes marks
5. **Push to portal** — per-student score + per-question correctness
6. **Notify** — SMS/email/WhatsApp to student + parent
7. **Item analysis** — which questions were too easy/hard, distractor
   effectiveness
8. **Topic mastery map per student** — % correct in each topic
9. **Weakness identification** — student is strong in Newton's Laws,
   weak in Rotational Motion
10. **Progress trend** — Test 1 → Test 2 → Test 3 trajectory per
    student / batch / topic
11. **Cross-correlation** — attendance × topic mastery × time spent in
    that subject's lectures

---

## What we already have

The schema is decent:

```
Question        — subject_id, topic_id, difficulty, blooms_taxonomy, concept_tags
QuestionTopic   — many-to-many topic tagging
Test            — batch_id, subject_id, scheduled_at, test_status
TestQuestion    — links + marks_allocated per question
StudentMark     — aggregate marks_obtained per student per test
```

Tier 9 (outcome correlation) reads `StudentMark` at the **batch
aggregate** level. That's the ceiling of what's possible without going
deeper.

---

## The three critical gaps

### Gap A — `StudentResponse` table is missing

`StudentMark` stores only the total. There's no per-question, per-student
record. Without this:

- ❌ Item analysis — which questions tripped students up
- ❌ Topic mastery — student got 60%, but where
- ❌ Weakness identification — what should this student practice next
- ❌ OMR workflow — no destination for per-question results

This is the single biggest data-model hole. Everything downstream needs
it.

### Gap B — No test generation / question bank UI

We have `Question` rows. No UI to:

- Browse the question bank
- Filter by chapter / topic / difficulty / Bloom's
- Compose a test from selected questions
- Save filters as reusable templates ("Weekly Physics Chapter Test")

Admins have to insert questions via API today.

### Gap C — No per-student surface

`/teachers/[id]` exists. `/students/[id]` doesn't. The data is there:

- Attendance records → `lecture_attendance_mappings`
- Test scores → `student_marks`
- Batch + syllabus → `student_batch_mappings` + `batch_subject_mappings`
- (After Gap A closes: topic mastery + weakness map)

But no surface for "Aman is at-risk: 35% attendance, scoring 41%,
weakest topic = Optics, chapter test in 2 weeks."

---

## Tier sequence

Build in dependency order — Tier 11 unlocks 12–14; Tier 15 replaces
the CSV-upload bridge with real OMR scanning later.

| Tier | What | Why this order | Effort |
|---|---|---|---|
| **11** | `StudentResponse` table + bulk CSV score upload + per-question marking. Auto-rolls up to `StudentMark`. | Foundation. CSV mimics OMR workflow without committing to OCR yet. | 1 day |
| **12** | Question bank UI + test paper composer (filter-based picker, save as template). | Lets admin actually create tests without API. | 2–3 days |
| **13** | `/students/[id]` detail page — attendance, score history, topic mastery heatmap, weakness list, upcoming tests, parent contact. | The "at-risk students" view. Mirrors `/teachers/[id]`. | 1 day |
| **14** | Item analysis + topic mastery insights on `/insights` (per-batch and per-teacher topic-wise performance). | Cross-references item-level results back to "which teacher taught this topic to this batch." | 1 day |
| **15** | OMR scan import (replaces CSV upload). | Real scanning. Use ScoreExam-style template detection. | 1+ week (OCR/image proc) |
| **16** | Notifications on test publish (SMS/email/WhatsApp to student + parent). | Last mile. Communications-channel work. | 3–5 days (SMTP + provider) |

---

## Integration with existing surfaces

| Surface | What this loop adds |
|---|---|
| `/home` | "Tests published this week" + "Students at risk" cards |
| `/today` | "Tests scheduled today" (data already in `tests`) |
| `/insights` | Outcome correlation gets sharper with topic-level + item-level data |
| `/teachers/[id]` | "When you taught Mechanics, your batch's Mechanics topic mastery improved by X%" |
| **NEW** `/students/[id]` | Per-student progress timeline + weakness map |
| `/lectures` and `/attendance` | The attendance loop already exists — Tier 13 just surfaces it per student |

---

## Concrete Tier 11 starter scope

When picking this back up, build:

1. **Migration `0023_student_responses.py`** — new table:
   ```
   student_responses(
     id, student_id, test_id, question_id,
     selected_answer text,
     is_correct bool,
     marks_obtained float,
     submitted_at timestamptz,
     branch_id, academic_year_id
   )
   ```
   Unique constraint on `(student_id, test_id, question_id)`.

2. **Repository helpers** in `tests` module: bulk insert responses,
   query per-student topic mastery, query item analysis.

3. **Service**: `submit_responses(test_id, payload)` that:
   - Validates each response against the test's question set
   - Marks correctness using `Question.correct_answer`
   - Inserts/updates rows in `student_responses`
   - Recomputes `StudentMark.marks_obtained` + `percentage` from the
     sum of correct marks

4. **Route**: `POST /api/v1/tests/{test_id}/responses` accepting either:
   - JSON: `[{student_id, question_id, selected_answer}, ...]`
   - CSV: header row + one row per (student, question)

5. **Frontend**: simple upload UI on the test detail/edit page —
   pick a CSV, preview parse, submit. Show per-student summary after.

6. **Seed update**: when seeding `Test` rows, also seed
   `student_responses` with deliberately-correlated correctness
   patterns (attendance and topic mastery) so demo data shows
   item analysis signal.

---

## What's deferred until after Tier 11–14

- Tier 15 (OMR scanning) — meaningful image-processing work, defer
  until the CSV-upload loop is proven
- Tier 16 (notifications) — needs SMTP + WhatsApp Business API
  decisions, defer until the team validates which channels actually
  matter
- Parent portal — completely new auth surface, defer further

---

## Where this sits next to what's done

```
DONE — Plan-vs-Actual half (lecture management)
  Tier 1   Substitute teacher
  Tier 2   LectureSession + ad-hoc/makeup
  Tier 2.5 Merge batches
  Tier 3   Adherence dashboard
  Tier 4   No-show + syllabus coverage
  Tier 4.5 Status pill collapse + mutual exclusion
  Tier 5   Today's Roster
  Tier 6   Per-teacher detail page
  Tier 6.5 Name lookups + per-teacher syllabus
  Tier 7   Time-weighted pace
  Tier 7.5 Exam date CRUD
  Tier 8   Smart substitute suggestions
  Tier 9   Outcome correlation
  Tier 10  /home polish (existing endpoints)
  Tier 11   StudentResponse + Question extensions + seed   ✅ shipped
  Tier 12   Study material ingest (organize + Gemini Vision) ✅ shipped
  Tier 12.7 Question Bank review queue UI                    ✅ shipped

NEXT
  Tier 11.6  Productivity refinements (from Copilot review)
              ├─ Weighted subtopic completion
              ├─ correlation_id in audit logs
              ├─ Extended reason_code enums
              └─ Composite productivity score on /teachers/[id]
              See docs/copilot-review-and-refinements.md
  Tier 12.5  AI generation pipeline (DeepSeek + Gemini variants)
  Tier 12.x  Question bank UI + composer (DPP/CPP creation)
  Tier 13    /students/[id] detail page
  Tier 14    Item analysis + topic mastery on /insights
  Tier 15    OMR scan import
  Tier 16    Notifications
  Tier 18+   Lecture segments (multi-substitute mid-handover)
              Deferred until real institute need surfaces.
```
