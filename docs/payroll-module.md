# Payroll module (days-based)

Source spec: `Payroll_Module_Explained.pdf`. This doc is the implementation
companion — what the code does, the decisions taken where the spec left a choice,
and the slice roadmap. **The module is dormant behind the `payroll_enabled`
config flag until rollout (§14).**

Days-based payroll only. Money/salary is an explicit later phase (§15) and is not
built.

## What it is

Payroll sits *on top of* the existing staff attendance. For each staff member and
month it reads `StaffDailyAttendance` (`PRESENT`/`LATE` = 1 day, `HALF_DAY` =
0.5) and the existing late fine, and **never writes either**. Super Admin sets
the month's required working days and any paid holidays; the engine computes
credited / net / extra / shortfall, threads a carry-forward balance through an
append-only ledger, and lets an uncovered shortfall be deferred via an approval
flow.

## Data model (migration 0069, new tables only)

| Table | Purpose |
|---|---|
| `payroll_month_settings` | required days + lifecycle per branch-month (§1/§6) |
| `payroll_month_holidays` | declared paid holidays / leaves per month (§1) |
| `payroll_staff_month` | computed per-staff monthly snapshot (§2/§7) |
| `carry_forward_ledger` | append-only balance ledger (§4) |
| `extra_day_requests` | make-up request flow (§5) |
| `extra_day_request_history` | append-only status timeline (§5) |
| `payroll_config` | key/value settings, seeded with §8 defaults |

Naming note: the month/staff-month "status" in the spec is stored as
**`lifecycle`** (OPEN/CLOSED/LOCKED) and the request "status" as
**`request_status`**, because `BaseModel.status` already exists as the generic
active/inactive record flag and must stay untouched.

The ledger is **append-only**: the service only ever INSERTs, and on Postgres a
`BEFORE UPDATE OR DELETE` trigger (`carry_forward_ledger_append_only`) raises. A
correction is a new `reversal` row. Each row carries a per-staff monotonic `seq`
so rows written in one transaction have a stable total order (Postgres `now()` is
constant across a transaction, so `created_at` cannot order them).

## Calculation (§2/§3)

```
credited          = present_days (full×1 + half×0.5) + paid_leave_days
effective_required = required_days + makeup_days        (makeup = approved request)
net               = credited − effective_required
```

- **net > 0 (extra):** add to the carry-forward balance up to the cap; the
  remainder is trimmed. Ledger: `extra_added` (+added) and, if anything was
  trimmed, a `cap_trim` row recording the discarded amount (no balance change).
- **net < 0 (shortfall):** the balance covers it first (never below zero unless
  `allow_negative_balance`); ledger `compensation_used` (−used). The uncovered
  remainder gets **no** ledger row — it is handled by the request flow.
- **net == 0:** nothing, no ledger entry (§3 Example 3).

Paid holidays/leaves credit is deduped by date and never double-counts a day the
staff actually worked ("counted once", §12).

### Decisions taken (where the spec/examples were ambiguous)

- **cap_trim** is a *separate, informational* ledger row (days = discarded
  amount, running balance unchanged), so "logged as cap_trim" (§3 More cases) is
  satisfied while the running-balance invariant stays clean. The §4 illustrative
  table folds it into the `extra_added` note instead; the behaviour is
  equivalent in balance terms.
- **Recompute after a correction** (§12) reverses a month to the balance it
  carried in with a single `reversal` row, then re-applies fresh entries, for the
  corrected month and every later CLOSED/LOCKED month in order. Superseded rows
  stay (append-only); the `seq`-latest running balance is always authoritative.
- **makeup_credit / manual_adjustment** entry types exist but are not emitted by
  the core engine yet — they belong to the request flow / admin actions (Slice 4+).

## Slice roadmap

| Slice | Scope | Status |
|---|---|---|
| 1 | module + migration 0069 + `payroll_config` + settings endpoint | ✅ done |
| 2 | calc engine + ledger + recompute; all §3 examples as tests | ✅ done |
| 3 | month setup + monthly report API + RBAC (§7/§9) | ✅ done |
| 4 | extra-day request flow (§5) | ✅ done |
| 5 | PDF/Excel exports + comparison tests | ✅ done |
| 6 | frontend: Month Setup + Monthly Report | ⬜ |
| 7 | frontend: Staff Ledger + Requests + Settings | ⬜ |
| 8 | rollout: flag flip, staging parallel month, backup/restore drill | ⬜ |

## Roles (§9) — enforced server-side in Slice 3+

| Action | super_admin | accounts / branch_admin | manager | teacher |
|---|---|---|---|---|
| Set required days / holidays | ✔ | view | view | — |
| Close / lock / reopen month | ✔ | — | — | — |
| View report + export | ✔ | ✔ | own depts | — |
| View staff ledger | ✔ | ✔ | — | — |
| Raise extra-day request | ✔ | ✔ | optional | — |
| Approve / reject request | ✔ | — | optional | — |
| Change payroll settings | ✔ | — | — | — |

Defaults for every §8 decision live in
`app/modules/payroll/services/config_service.py` (`DEFAULTS`) and the 0069 seed —
keep the two in sync.
