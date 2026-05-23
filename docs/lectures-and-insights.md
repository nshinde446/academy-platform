# Lectures & Insights — Admin Guide

This doc covers the two pages a coaching-institute admin uses every day to
schedule classes and judge how things actually went:

1. `/lectures` — schedule, run, and reconcile lectures
2. `/insights` — Plan-vs-Actual adherence dashboard

It also calls out **what's missing** for true productivity measurement. Read
the [Gaps](#gaps---what-this-system-cant-tell-you-today) section before
making personnel decisions from this data.

---

## 1. Lectures page (`/lectures`)

### Header actions

Three buttons in the page header, each opens a different dialog:

| Button | When to use | Origin recorded |
|---|---|---|
| **Schedule Lecture** | Normal planning — admin schedules a future class for one batch. | (creates a plan, no session yet) |
| **Merge Lectures** | After-the-fact: two scheduled lectures (different batches) were taught together. | session.origin = `planned`, multi-plan link |
| **Record Makeup** | After-the-fact: a class happened that has no matching plan (or fills a cancelled plan). | `makeup` if linked to a missed plan, otherwise `ad_hoc` |

### Row actions, by status

Each row in the lectures table shows different buttons based on
`lecture_status`. The table below is the source of truth for what an admin
can do at any given moment:

| Status | Start | Complete | Cancel | No-Show | Substitute | Attendance | Delete |
|---|---|---|---|---|---|---|---|
| `scheduled`   | ✅ | — | ✅ | ✅ | ✅ (Edit Sub if set) | ✅ | ✅ |
| `started`     | — | ✅ | ✅ | — | ✅ | ✅ | ✅ |
| `paused`      | — | ✅ | ✅ | — | ✅ | ✅ | ✅ |
| `completed`   | — | — | — | — | ✅ | ✅ | ✅ |
| `cancelled`   | — | — | — | — | — | ✅ | ✅ |
| `no_show`     | — | — | — | — | — | ✅ | ✅ |
| `rescheduled` | (re-becomes scheduled) | — | — | — | — | ✅ | ✅ |

### Visual indicators

- **Teacher cell** when a substitute is recorded:
  - scheduled teacher shown ~~strikethrough~~, smaller
  - actual teacher shown **bold**
  - badge with the reason (`SUBSTITUTE`, `SUBJECT_SWAP`, `TOPIC_CHANGE`, `COMBINED_BATCH`, `OTHER`)
- **Status badge**:
  - `started` → green
  - `completed` / `paused` → neutral grey
  - `cancelled` / `no_show` → red (distinct paths, same color)
  - `scheduled` / `rescheduled` → blue/primary

### Recorded sessions table

Below the lecture table, a second table appears once any sessions have been
recorded. It shows actual teaching events (makeups, ad-hoc, merged) with
their origin badge.

---

## 2. Insights page (`/insights`)

Date-range picker at the top (defaults to last 30 days). Everything below
is filtered to that window on `scheduled_start` for lectures and
`actual_start` for sessions.

### KPI cards (4)

| Card | Formula | Tone thresholds |
|---|---|---|
| **Adherence** | `completed_as_planned / planned` | ≥80% green, ≥60% default, ≥40% warning, <40% red |
| **Substitute rate** | `substituted / planned` | 0% green, >0% default, ≥15% warning, ≥30% red |
| **No-show rate** | `no_show / planned` | 0% default, >0% warning, ≥10% red |
| **Cancellation rate** | `cancelled / planned` | ≥15% red, else default |

`completed_as_planned` deliberately excludes substituted lectures — a class
that ran but with a different teacher is *not* "as planned" from the
adherence perspective.

### Recorded sessions breakdown

A single card showing four counts:

- **Planned (linked)** — sessions tied to one scheduled lecture (normal flow)
- **Makeup** — sessions recorded against a cancelled / missed plan
- **Ad-hoc** — unplanned classes with no original schedule
- **Merged** — sessions with 2+ linked plans (combined-batch teaching)

### Teacher leaderboard

Top 10 teachers sorted by **substitute-out rate** descending. Higher = bigger
plan-vs-actual gap. Columns:

- **Planned** — lectures scheduled with this teacher in the window
- **Sub out** — of those, how many were actually delivered by someone else
- **Sub in** — lectures this teacher delivered as a substitute for someone else
- **Cancelled** — admin-cancelled lectures originally with this teacher
- **Sub rate** — `sub_out / planned` (the sort key)

### Syllabus coverage

Per-batch table sorted by coverage % ascending (worst-coverage first).

- **Total topics** = topics under the batch's mapped subjects (via
  `batch_subject_mappings` → `subjects` → `chapters` → `topics`)
- **Delivered** = distinct `topic_id`s across completed lectures AND
  recorded sessions for that batch
- **Coverage %** = `delivered / total`

Coverage bar tone: ≥75% green, ≥50% primary, ≥25% amber, <25% red.

---

## 3. Test scenarios (admin POV)

Each scenario walks through the happy path and what the data should look
like in `/insights` afterwards.

### Scenario 1 — Normal completion

> *Rahul takes Physics for NEET-A on Tuesday 10am as scheduled. Class
> finishes on time.*

1. Schedule Lecture: batch NEET-A, teacher Rahul, subject Physics, Tue 10am
2. Row appears in `scheduled` status
3. At 10am, admin clicks **Start** → status flips to `started` (green)
4. At 11am, admin clicks **Complete** → status flips to `completed`

**Insights effect**: `planned` +1, `completed_as_planned` +1, adherence
moves up.

---

### Scenario 2 — Substitute (last-minute teacher swap)

> *Rahul is sick. Priya covers Physics for NEET-A. The class still runs.*

1. The scheduled row exists with `teacher_id = Rahul`
2. Priya teaches the class and admin clicks **Start** then **Complete**
3. Admin clicks **Substitute** on the now-completed row
4. Dialog: pick Priya, reason `SUBSTITUTE`, optional notes
5. Row's Teacher cell now shows ~~Rahul~~ / **Priya** + `SUBSTITUTE` badge

**Insights effect**:
- `planned` +1, `substituted` +1, `completed_as_planned` NOT incremented
- Adherence rate falls; substitute rate rises
- Rahul shows in the teacher leaderboard as +1 `Sub out`; Priya as +1 `Sub in`

**Note**: This is the only Tier-1 flow. The other flows below all live in
the Tier 2+ session model.

---

### Scenario 3 — Teacher no-show

> *Rahul didn't come. No substitute arranged. Class never happened.*

1. The scheduled row exists at, say, Tue 10am
2. After the time has passed, admin clicks **No-Show** on the row
3. Dialog: reason `TEACHER_NO_SHOW`, optional notes
4. Row status flips to `no_show` (red)

**Insights effect**: `planned` +1, `no_show` +1. No-show rate KPI ticks up.

**Why this is distinct from Cancel**: cancellation is *intentional* (admin
decided not to hold the class). No-show is a *failure*. Conflating them
hides teacher-reliability problems.

---

### Scenario 4 — Student no-show

> *Holiday declared. Rahul came but no students showed up.*

1. **No-Show** → reason `STUDENT_NO_SHOW`
2. Same destination status (`no_show`), but the reason captures that this
   was a student / scheduling problem, not a teacher one

**Insights effect**: same as Scenario 3 today — the reason is recorded but
**not yet broken out in the dashboard**. See [Gap #5](#gap-5-no-show-reason-breakdown).

---

### Scenario 5 — External cancellation (power outage etc.)

> *Power out for 2 hours; classes for that slot couldn't happen.*

1. **No-Show** → reason `EXTERNAL`
2. Same as above — recorded but not yet broken out

---

### Scenario 6 — Intentional cancellation (institute holiday)

> *Institute closed for board exams. Admin cancels affected lectures.*

1. **Cancel** on each scheduled row
2. Status flips to `cancelled`

**Insights effect**: `cancelled` +N, no_show **not** incremented. The
distinction matters — these cancellations don't reflect teacher
reliability.

---

### Scenario 7 — Makeup class

> *Tuesday's class was a no-show. On Saturday, Rahul takes the missed
> content with NEET-A as a makeup.*

1. On Saturday after the makeup happened: header → **Record Makeup**
2. Dialog: pick the Tuesday no-show lecture as "Linked missed lecture"
3. Batch / subject / teacher prefill from the linked plan
4. Set actual start/end to Saturday's actual times
5. Submit

**Insights effect**:
- Session created with `origin = makeup`
- Sessions breakdown card shows Makeup +1
- The Tuesday lecture stays as `no_show` in the lecture table (its
  attendance was zero, the actual teaching was the Saturday session)
- Syllabus coverage: the topic taught on Saturday now counts as
  "delivered" for NEET-A

---

### Scenario 8 — Pure ad-hoc class

> *Extra revision class organised at the last minute. No plan existed.*

1. Header → **Record Makeup**
2. Leave "Linked missed lecture" blank
3. Fill batch, teacher, subject, times
4. Submit

**Insights effect**:
- Session created with `origin = ad_hoc`
- Sessions breakdown card shows Ad-hoc +1
- Adherence KPIs unchanged (no plan, so denominator doesn't move)
- Syllabus coverage: the topic counts as delivered

---

### Scenario 9 — Merged batches

> *NEET-A and NEET-B scheduled separately at the same hour. Rahul takes
> both batches together in one room.*

1. Header → **Merge Lectures**
2. Tick both NEET-A and NEET-B rows in the checklist
3. Subject locks to NEET-A's subject (must match across selections)
4. Teacher / classroom / window auto-fill from NEET-A; edit if needed
5. Submit

**Insights effect**:
- One session created with `lecture_ids = [A, B]`, `batch_ids = [A, B]`,
  `origin = planned`
- Sessions breakdown: Merged +1, Planned +1 (the link count)
- **Caveat**: the two original lecture plans stay as `scheduled` —
  see [Gap #6](#gap-6-merge-leaves-plans-dangling)

---

### Scenario 10 — Reschedule

> *Tuesday's lecture can't happen; move it to Wednesday.*

1. (Not currently exposed via a button — see [Gap #7](#gap-7-no-reschedule-button-in-ui))
2. Backend has `PATCH /lectures/{id}/reschedule` but no UI

**Insights effect**: `rescheduled` +1, will become `scheduled` again on the new date.

---

## 4. Gaps — what this system can't tell you today

The honest section. Some of these are tracked in DB but not surfaced; some
aren't tracked at all.

### Gap 1: Punctuality

We store `actual_start` (set on Start click) and `scheduled_start` (the
plan). The delta is the most obvious punctuality KPI — but **no UI surfaces
it**. A teacher who starts every class 15 minutes late looks identical in
the leaderboard to one who starts on time.

**Fix**: add `late_starts` and `avg_minutes_late` to the per-teacher
aggregation; surface as KPI.

### Gap 2: Effective teaching time

`actual_end - actual_start` is recorded for sessions and for completed
lectures (via the Complete-click timestamp). We don't surface "average
class duration" or "% of scheduled time actually used."

**Fix**: add a per-teacher "avg_duration vs scheduled_duration" KPI.

### Gap 3: Attendance is invisible in Insights

The attendance module exists and `lecture_attendance_mappings` is
populated. **But the Insights page doesn't read it.** A teacher with 100%
adherence and 30% student attendance is failing — currently invisible.

**Fix**: add an attendance-rate KPI; per-teacher and per-batch attendance
columns.

### Gap 4: Outcomes are not measured

There is no link from lectures to test scores, homework completion,
student feedback, or pass rates. Productivity in coaching is ultimately
*"do students learn?"* — and the system has no signal on that side of the
equation.

**Fix**: cross-link `lectures.subject_id` ↔ `tests.subject_id` so a
teacher's lecture cohort can be matched to their students' test
performance. Adds a "test result correlation" KPI.

### Gap 5: No-show reason breakdown

The `no_show_reason` column captures TEACHER / STUDENT / EXTERNAL / OTHER,
but the Insights KPI just shows "no_show rate". A 20% no-show rate that's
80% external isn't a teacher problem; one that's 80% TEACHER_NO_SHOW is.

**Fix**: break no_show into stacked counts by reason; consider showing
"teacher-attributable no-show rate" as a separate KPI.

### Gap 6: Merge leaves plans dangling

When two plans are merged into one session, the plans themselves stay
`scheduled` forever. They count as "planned but not completed" in
adherence — falsely deflating the rate.

**Fix**: on merge, auto-transition linked plans to `completed` (with a
"covered_by_session" marker) or add a new `merged_into` status.

### Gap 7: No reschedule button in UI

`PATCH /lectures/{id}/reschedule` exists on the backend with full conflict
checking. The lecture table has no button for it. Admins currently work
around this by Cancel + Schedule-fresh, which loses the link to the
original plan.

**Fix**: add a Reschedule action to scheduled / paused rows.

### Gap 8: Per-teacher syllabus

Syllabus coverage is per-batch only. A teacher across 3 batches has 3
different coverage numbers, none of which roll up. "Has Rahul covered
Mechanics across all his batches?" can't be answered.

**Fix**: add a per-teacher syllabus view alongside per-batch.

### Gap 9: Pace / expected coverage

Coverage shows "8 / 45 topics delivered." It does **not** show "should be
at 20 by now" — the expected progress based on the academic-year calendar.
A batch at 17.8% coverage might be on track (year just started) or 3
months behind.

**Fix**: introduce a planned-topics-per-week target on the batch (or
derive from `academic_years.start_year` + curriculum pacing) and show
delivered vs expected.

### Gap 10: Sub-topic granularity

`lectures.topic_id` is a single FK. Real lectures cover multiple
sub-topics. `LectureTopicMapping` exists in the model but **is unused** —
nothing writes to it. So "depth per hour" is unmeasurable.

**Fix**: populate `LectureTopicMapping` on lecture completion (admin
multi-selects what was covered); count distinct sub-topics in coverage.

### Gap 11: Substitute chains

Priya covered Rahul's lecture. Then she covers Asha's lecture next week.
She effectively shoulders other teachers' loads. The leaderboard's "Sub
in" column shows this raw count but doesn't flag that Priya's *own*
adherence might be 100% while she's quietly carrying 30% extra work.

**Fix**: surface "extra hours teaching as substitute" as a separate KPI;
flag teachers with high Sub in + high own adherence as overloaded.

### Gap 12: Workload distribution

Hours scheduled per teacher per week isn't summarised anywhere. Some
teachers may be overworked (60h/week) while others are underused (10h).

**Fix**: per-teacher "weekly scheduled hours" KPI; flag outliers.

### Gap 13: No-show pattern detection

Day-of-week or time-of-day patterns are invisible. A teacher who only
no-shows on Friday late slots signals something specific — currently lost
in the rate.

**Fix**: heatmap of no-show density by day × hour.

### Gap 14: Cost / value side

If teachers are paid per lecture, "productivity = value / cost." The
system has the activity side but no rate / cost data.

**Fix**: optional `teacher.hourly_rate` field; cost-per-adherence-point KPI.

---

## 5. Can admins decide teacher productivity from this today?

**Partially. Here's the honest answer:**

### What you CAN say today

- **"Rahul has a 41.7% substitute rate."** ✅ — solid signal of reliability
- **"NEET-A is 2x further behind on syllabus than NEET-B."** ✅ — actionable
- **"Priya covered for Rahul twice last month."** ✅ — leaderboard captures it
- **"We had 5 no-shows last week."** ✅ — distinct from cancellations now
- **"Tuesday 10am NEET-A is the most disrupted slot."** ❌ — drill-down missing

### What you CANNOT say today

- **"Rahul's lectures lead to higher test scores than Priya's."** ❌
- **"Asha is 12 minutes late on average."** ❌ (data exists, not surfaced)
- **"Students attend Priya's lectures more than Rahul's."** ❌ (attendance not in insights)
- **"NEET-A is behind schedule by 4 lectures (vs expected pace)."** ❌
- **"Rahul is overworked — 55 hours scheduled this week."** ❌
- **"Priya is effectively doing 20% of Rahul's job as a substitute."** ❌ (raw count
  yes, framed-as-overload no)

### The structural issue

What this system measures very well is **execution reliability** — did the
plan happen the way we said it would? That's important but it's only one
axis of productivity.

The two axes that matter for "who is a great teacher" are:

```
                Outcomes / Quality
                       ▲
                       │
         Good but      │     Star teacher
         flaky         │
              ────────┼────────▶  Reliability / Execution
                       │
         Underperformer│     Reliable but
                       │     low impact
                       │
```

Right now we measure the **horizontal axis** (Reliability) thoroughly. We
measure **nothing on the vertical axis** (Outcomes). An admin using only
this dashboard could fire a "good but flaky" star teacher and keep a
"reliable but low-impact" one — a real risk worth understanding before
using these numbers for evaluation.

### Practical recommendation for admins right now

Use Insights as a **diagnostic for reliability** — "who do I need to talk
to about absences and substitutes" — not as a **productivity score**. Pair
it with:

1. Student attendance % (from the attendance page — not in Insights yet)
2. Test pass rates (from the tests module — not linked to teachers yet)
3. Student / parent feedback (no module yet)

The system is a strong foundation. It's not yet a complete productivity
measurement tool, and presenting it as one would lead to bad decisions.

---

## Appendix — Quick reference: data flow

```
Plan (lectures table)
    │
    ├── if cancelled deliberately → lecture_status = "cancelled"
    ├── if teacher/student didn't show → lecture_status = "no_show" + no_show_reason
    ├── if started but different teacher → lecture_status = "completed" + actual_teacher_id
    │
    └── if completed cleanly → lecture_status = "completed"

Session (lecture_sessions table) — represents what ACTUALLY happened
    │
    ├── linked to 0 plans → origin = "ad_hoc"
    ├── linked to 1 plan + filling a missed slot → origin = "makeup"
    ├── linked to 2+ plans (same time slot, different batches) → origin = "planned" + merged
    │
    └── all sessions also link to >=1 batches via lecture_session_batches
```
