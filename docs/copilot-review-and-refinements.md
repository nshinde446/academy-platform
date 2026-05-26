# Review of Prompt I.docx (Copilot Chat transcript) — refinements for our project

Companion to `coaching-test-loop-roadmap.md` and
`question-bank-and-dpp-roadmap.md`. Captures the actionable parts of a
23-turn Copilot-Chat transcript (~11,000 lines) that the user asked us
to review for inclusion in our existing project. Frames each accepted
idea as a concrete enhancement on top of what we've already built,
keeping our **FastAPI + PostgreSQL + Celery + Next.js** stack as-is.

Saved 2026-05-26.

---

## Honest summary of the transcript

The document is one long thread focused entirely on **teacher
productivity tracking**. Topics, in order:

1. Lecture lifecycle (schedule → start → complete)
2. No-show detection and substitute assignment
3. Multiple-substitute handling (lecture segments)
4. Weighted subtopic completion at the topic level
5. Composite productivity scoring formulas
6. Audit logging with `correlation_id`
7. Co-teaching, disputes, overrides, risk scoring
8. Recommended tech stack (Node.js + Express / NestJS — not us)

**The transcript is silent on**:
- Question banks / DPPs / CPPs / test paper composition
- OMR sheets, answer keys, paper codes
- Per-student progress, topic mastery, weakness identification
- Study material ingestion or AI generation

So the user's interest in "question bank and test series" finds
nothing useful in this document — that direction is already covered
by our two existing roadmaps and is unaffected by this review.

---

## What we've already built that supersedes the doc

Most of the doc's recommendations are either done or already
extended past what it proposes:

| Doc proposal | Our state |
|---|---|
| Admin scheduling + oversight | Done (Tier 1 + `/lectures` + `/today`) |
| Teacher start/complete tracking | Done |
| No-show detection + substitute flow | Done (Tier 1, 4, 8) — richer (smart substitute suggestions, mutual exclusion, makeup linking) |
| Productivity dashboard | Done (`/insights`, `/today`, `/teachers/[id]`) — richer (outcomes correlation, time-weighted syllabus pace) |
| Audit logs as a table | Done (`audit_logs` + `audit_service`) |

**Tech stack disagreement**: the doc proposes Node.js + Express or
NestJS. We're on FastAPI. The doc is wrong for us; keep FastAPI.
Similarly Celery already covers what the doc calls BullMQ + Redis.

---

## What's worth pulling in — actionable enhancements

Five enhancements, scored by value. Tier 11.6 (below) bundles the
top three.

### Enhancement 1 — Weighted subtopic completion (HIGH VALUE)

The doc proposes: at schedule time, admin breaks a lecture's topic
into 3–5 subtopics, each with a weight. At lecture-end, teacher marks
each as not-started / partial / done. Completion % is computed as
Σ(covered_weight) / Σ(planned_weight).

**Why this matters for us**: our "Complete Lecture" flow is binary.
`/insights` adherence treats every completed lecture as 1.0. A 90-min
lecture where only Newton's First was covered counts the same as one
where all five planned subtopics were taught. The doc's model fixes
this without a redesign — our schema already has the table.

**Our existing schema**:

```python
# backend/app/modules/lectures/models/lecture_models.py
class LectureTopicMapping(BaseModel):
    lecture_id: UUID
    topic_id: UUID
    order: int
    branch_id: UUID
```

Nothing currently writes to this table.

**Concrete fix**:

1. Migration adds two columns:
   ```sql
   ALTER TABLE lecture_topic_mappings
     ADD COLUMN weight INT DEFAULT 100,
     ADD COLUMN coverage_pct INT DEFAULT 0;
   ```
2. **Schedule dialog** (`create-lecture-dialog.tsx`) — optional
   subtopic section with rows of `(topic, weight)`, must sum to 100.
3. **Complete dialog** — new flow that lists the planned subtopics
   with a 0/50/100 toggle per row (or a 0–100% slider). Submits an
   updated `coverage_pct` for each mapping.
4. **Derived `lecture.completion_pct`** = Σ(weight × coverage_pct / 100) / 100
5. **Insights math change**: in `lecture_repository.lecture_totals_in_range`,
   `completed_as_planned` becomes a weighted sum where each completed
   lecture contributes `completion_pct / 100` rather than 1.0.
   For lectures without subtopic data (legacy or simple schedule),
   default `completion_pct = 100` so existing behaviour is unchanged.

**Effort**: 1 backend day + 1 frontend day. Pure additive — no
breakage of existing data because absent subtopic rows default to
100%-treated.

### Enhancement 2 — Lecture segments for multi-substitute (MEDIUM, DEFER)

The doc proposes a `lecture_segments` table to represent "Prof A took
10:00–10:30, Prof B took 10:30–11:30." Each segment carries its own
teacher, time window, subtopic contribution, and productivity credit.

**Why this matters**: today our `actual_teacher_id` is single-valued
— overwriting it loses the prior substitute. Real but rare in Indian
coaching: most institutes reschedule rather than mid-lecture handover.

**Concrete fix (when prioritised)**:

```sql
CREATE TABLE lecture_segments (
  id UUID PRIMARY KEY,
  lecture_id UUID REFERENCES lectures(id),
  teacher_id UUID REFERENCES teachers(id),
  segment_start TIMESTAMPTZ NOT NULL,
  segment_end TIMESTAMPTZ NOT NULL,
  segment_type VARCHAR(20),   -- scheduled | substitute | co_teacher | gap
  reason_code VARCHAR(40),
  admin_approved_by UUID REFERENCES users(id),
  -- + base columns
);
```

API: `POST /api/v1/lectures/{id}/segments`.

Productivity calc updated to attribute credit per segment rather
than relying on `actual_teacher_id` alone.

**Effort**: 2 backend days. UI can come later — admins record via API
initially.

**Verdict**: defer until a real institute hits this case. Logging it
as a future tier rather than blocking on it.

### Enhancement 3 — `correlation_id` in audit logs (MEDIUM-HIGH VALUE)

The doc proposes that every audit row from the same request shares a
`correlation_id` so you can replay the full footprint of one admin
action across multiple tables.

**Our state**: `audit_service.log_action` exists, but `audit_logs`
has no `correlation_id` column.

**Concrete fix**:

1. Migration:
   ```sql
   ALTER TABLE audit_logs ADD COLUMN correlation_id UUID;
   CREATE INDEX ix_audit_logs_correlation_id ON audit_logs(correlation_id);
   ```
2. FastAPI middleware in `app/core/middleware/correlation.py`:
   ```python
   async def correlation_middleware(request: Request, call_next):
       request.state.correlation_id = uuid.uuid4()
       response = await call_next(request)
       response.headers["X-Correlation-ID"] = str(request.state.correlation_id)
       return response
   ```
3. `audit_service.log_action` accepts an optional `correlation_id`
   parameter; the FastAPI dependency `Request` is already in scope
   for our route handlers, so the dependency injection chain can
   forward it.
4. Logging: include `correlation_id` in every Python log message via
   a context-local logger filter.

**Effort**: half a day backend, no UI for now.

### Enhancement 4 — Structured `reason_code` enum (MEDIUM)

The doc proposes machine-readable reason codes for every state change:
`NO_SHOW_PENALTY_WAIVED`, `OVERLAP_RESOLUTION`, `SCHEDULE_CHANGE_FORCE`,
`LATE_GRACE_GRANTED`, etc.

**Our state**: `change_reason` and `no_show_reason` are already
enum-ish (`SUBSTITUTE`, `TEACHER_NO_SHOW`, etc.) — we're 70% there.

**Concrete fix**:

1. Extend `VALID_CHANGE_REASONS` and `VALID_NO_SHOW_REASONS` sets in
   `lecture_service` to include a wider set of admin-action codes.
2. New `VALID_RESCHEDULE_REASONS` set for reschedule flow.
3. Existing free-text `change_notes` field stays — the *code* names
   the bucket, the *notes* hold the narrative.

**Effort**: half a day backend, small frontend dialog tweak.

### Enhancement 5 — Composite teacher productivity score (MEDIUM)

The doc proposes a single number per teacher per period:

```
Productivity = (Completion × 0.40)
             + (Punctuality × 0.20)
             + (Attendance × 0.20)
             + (Reliability × 0.15)
             + (Extra Contribution × 0.05)
             − penalties
```

**Our state**: `/insights` shows the axes separately; `/teachers/[id]`
shows per-teacher KPIs but no rolled-up score.

**Caveat**: at the institute level, collapsing to one number hides
where the problem is. At the per-teacher level, one number on
`/teachers/[id]` is genuinely useful for a "how is this teacher
doing?" glance.

**Concrete fix**:

1. New service helper:
   ```python
   def compute_teacher_productivity_score(
       teacher_id, from_date, to_date
   ) -> dict:
       # Returns: {score: float, components: {...}, penalties: float}
   ```
2. Surface on `/teachers/[id]` as a hero card with the breakdown
   collapsible below.
3. **Don't replace** the existing axis-separated views on `/insights`
   — that decomposition stays the source of truth at the branch level.

**Effort**: 1 backend day + a card on the teacher detail page.

---

## What to explicitly skip

| Proposal | Reason |
|---|---|
| Migrate to Node.js + Express / NestJS | We're on FastAPI/Python which works. Migrating is pure cost with no upside. |
| Use BullMQ + Redis for jobs | We have Celery already. Same outcome. |
| Pino structured logging | Python's logging + a correlation_id filter is sufficient. |
| Co-teaching as a first-class concept | Edge case; defer until requested. |
| Risk scoring / dispute workflow | Premature without operational data. |
| Re-doing the lecture model | We've gone past the doc — single status pill (Tier 4.5), mutual exclusion (Tier 4.5), smart substitute (Tier 8). |

---

## Integration into the roadmap

A new tier slot: **Tier 11.6 — Productivity refinements (from
Copilot review)**, between the just-shipped Tier 11 foundation and
the upcoming Tier 12 question bank ingest. Bundles Enhancements 1,
3, 4, 5 — all FastAPI-stack-compatible, all additive.

```
Tier 11    ✅ student_responses + Question extensions          [DONE]
Tier 11.6  ⏳ Productivity refinements                          [NEW]
            ├─ Weighted subtopic completion (Enhancement 1)
            ├─ correlation_id in audit logs (Enhancement 3)
            ├─ Extended reason_code enums (Enhancement 4)
            └─ Composite productivity score on /teachers/[id] (Enhancement 5)
Tier 12    ⏳ Question bank ingest (study_material + JEEBench)
Tier 12.5  ⏳ AI generation pipeline (DeepSeek + Gemini)
Tier 13+   ⏳ DPP/CPP composer + PDFs + OMR
...
Tier 18+   ⏳ Lecture segments (Enhancement 2 — deferred)
```

**Tier 11.6 estimated**: 2.5 backend days + 1 frontend day. Pure
additive, no schema breakage.

---

## TL;DR for the next session

The Copilot transcript is well-reasoned but **a stage behind where
this project is**. The vast majority of its proposals are already
shipped or surpassed. Four enhancements are worth integrating —
bundled as Tier 11.6 and added to both existing roadmap docs.

Tier 12 (study material ingest) remains the next major slice and is
unaffected by this review.
