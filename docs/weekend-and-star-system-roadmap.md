# Weekend Work & Teacher Self-Assessment Workflow — Roadmap

Source spec: *Matrix Science Academy — Weekend Work & Teacher Self-Assessment
Workflow SRD v1.0* (client doc `DOC-20261118`).

This turns the **view-only Weekend Report** into an interactive approval workflow
and adds a brand-new **Teacher Star System** daily self-assessment, both inside
the Teacher Portal (`/my-day/*`), with an approver inbox on the admin side.

## Decisions taken (locked for this build)

- **Reconcile into one.** The live senior-initiated `weekend_work` flow (PR
  #192/#195 — senior pre-approves a date → teacher writes content → attendance
  drives payroll credit) and the SRD's teacher-initiated Weekend Plan are merged
  into **one `weekend_work` table + lifecycle** that supports both origins. The
  table is evolved in place, not replaced. Safe because **payroll reads
  `staff_daily_attendance`, never the `weekend_work` rows** — `credit_days` is
  report/audit only.
- **SRD open questions → proposed defaults** (section 12 of the SRD), each flagged
  in its PR so the client can override later:
  1. Approver = mapped Senior per teacher, Admin as fallback.
  2. Star System applies on working days + approved weekend days.
  3. Deductions shown separately, **penalty weight 0** until the client confirms.
  4. Mark-as-Absent recorded only; no payroll link in v1.
  5. Approved weekend plan does **not** feed payroll extra-day credit in v1.
  6. Approver can only decide + comment; cannot edit star ratings.
  7. Submit within 2 days; approver reminder after 24h (reminder deferred to the
     notifications slice).
  8. **In-app notifications only** for v1 (email/SMS optional, out of scope).

## Keying note

The Teacher Portal is **staff-keyed** (`staff_id` from the login session, strong
IDOR protection in `teacher_portal/api/routes.py`). The SRD says "Teacher"; we key
everything on `staff_id` and surface it as the teacher, consistent with the
existing portal, leave, and weekend-work features. Approvers are `User`s
(`super_admin` / `branch_admin` / `academic_head`, matching
`admin_weekend_routes.py`).

## Reconciled data model

### `weekend_work` (evolved in place — migration adds columns)
Existing columns kept. New columns:
| Column | Purpose |
|---|---|
| `origin` | `SENIOR_PREAPPROVED` \| `TEACHER_PLAN`. Existing rows backfill to `SENIOR_PREAPPROVED`. |
| `day_type` | `SATURDAY` \| `SUNDAY` \| `HOLIDAY` (SRD supports holidays, not only Sat/Sun). |
| `holiday_name` | Shown when `day_type = HOLIDAY`. |
| `approver_id` | Assigned approver (mapped/chosen) — distinct from `approved_by` (who actually decided). |
| `total_planned_minutes` | Auto sum of plan items (WP04). |
| `remarks` | Optional plan-level note. |
`approval_status` widened to the SRD lifecycle: `DRAFT → PENDING →
APPROVED|REJECTED|ABSENT`. `marked_absent` (bool) stays as the senior-flow
management override; `ABSENT` status is the unified terminal state for the
teacher-plan flow.

### `weekend_plan_items` (new) — WP03 work-breakdown lines
`weekend_work_id` FK, `work_type`, `batch_id` (nullable FK), `task_description`,
`start_time`, `end_time`, `sort_order`.

### Star System (new)
- `assessment_categories` — the 5 categories (4 rated + Discipline Deductions),
  `name`, `sort_order`, `is_deduction`, `active`.
- `assessment_item_master` — items per category, `input_type`
  (`COUNT`\|`STATUS`\|`DEDUCTION`), `options` (JSON), `sort_order`, `active`
  (admin-configurable).
- `self_assessments` — one per teacher per date (SA-06): `staff_id`,
  `assess_date`, `miscellaneous_text`, `final_total_star`, `status`,
  `approver_id`, `submitted_on`, `latest_approver_comment`.
- `self_assessment_items` — `self_assessment_id`, `item_master_id`,
  `selected_value`.
- `self_assessment_stars` — `self_assessment_id`, `category_id`, `stars` (1–5).

### Shared
- `approver_mappings` — `staff_id` (teacher) → `approver_user_id`, `is_default`.
- `approver_logs` — permanent decision log for BOTH record types:
  `record_type` (`WEEKEND_PLAN`\|`SELF_ASSESSMENT`), `record_id`,
  `approver_user_id`, `action` (`SUBMIT`\|`WITHDRAW`\|`RESUBMIT`\|`APPROVE`\|
  `REJECT`\|`MARK_ABSENT`), `comment`, timestamp. Teacher-visible history
  (BR-06, never deleted).
- `portal_notifications` — lean in-app inbox: `user_id`, `record_type`,
  `record_id`, `message`, `is_read`, `created_at` (AP07, open-Q 8).

## Slice plan (one PR each, off fresh master)

| Slice | Scope | SRD IDs |
|---|---|---|
| **1. Foundations** (this PR) | All models + migration `0075` + seed default Star categories/items/options + this doc | §8 tables, BR-05/06 fields |
| **2. Weekend Plan — teacher** | Draft/items/total-hours/submit/withdraw/resubmit, approver mapping resolve, day-type validation, ApproverLog + notify | WP01–10, BR-02/04/05 |
| **3. Approver inbox + decisions** | Inbox (plans + assessments), approve/reject/mark-absent, mandatory comment ≥10, log, notify, own-submission guard, final/reject-only-resubmit | AP01–09, BR-01/07 |
| **4. Star System — teacher** | Form definition, save draft, one-per-date, final-total calc, submit, status+comment, admin config of items | SA-01–08, BR-03 |
| **5. Frontend — teacher portal** | `/my-day/weekend-plan`, `/my-day/self-assessment` (wireframe §7), status cards, badges, edit/resubmit | §7.1/7.2/7.4 |
| **6. Frontend — approver** | Approvals inbox, read-only view, action panel (§7.3), history tab, approver-mapping admin | §7.3 |
| **7. Notifications + audit + tests** | In-app bell (teacher+approver), retention, acceptance tests AC-01–08 incl. IDOR, branch-isolation | §10, §11 |

## Acceptance criteria → verified in Slice 7
AC-01 draft+submit→Pending · AC-02 all categories/items, Misc only text · AC-03
final-total math · AC-04 no action without comment · AC-05 teacher sees
status+exact comment · AC-06 reject→edit→resubmit, history kept · AC-07
mark-absent + reason visible · AC-08 teacher cannot open another's record by URL.
