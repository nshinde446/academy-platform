# Payroll rollout runbook (§14)

The Payroll module ships **dormant**: migration `0069` seeds `payroll_enabled =
false`, so the Payroll nav section is hidden and no one reaches the screens in
normal use. The endpoints exist and are RBAC-gated (§9), but until the switch is
flipped the module is invisible. This runbook turns it on safely.

Prerequisites: Slices 1–7 merged and deployed; migration `0069` applied on prod
(verify `alembic current` shows `0069`). Payroll adds only new tables and never
writes attendance/late-fine data, so it cannot corrupt existing reports.

## 1. Back up and prove a restore (do this first)

- Confirm the nightly DB backup ran (`/root/db-backup.sh`, cron 02:00 UTC) and
  the off-box copy reached the Hetzner Storage Box. See
  `project_backups_monitoring` / `docs` for the drill.
- On **staging**, restore the latest prod backup and bring the app up against it.
  This is the rollback target; do not proceed until a restore is proven.

## 2. Parallel month on staging

Pick the most recently completed month and reproduce it on staging:

1. **Month Setup** → set the required days (e.g. 26) and declare that month's
   paid holidays/leaves.
2. Open the **Report** (preview) and compare a handful of staff against the
   manual payroll sheet: present days, net, late fine.
3. **Close** the month. Re-check the report (now the frozen snapshot) and a
   couple of **Ledgers** (extra_added / compensation_used as expected).
4. Exercise one **extra-day request** end to end (raise → approve), and confirm
   the source month flips to *deferred* and next month's required days rise.
5. Export the report and a ledger to **PDF and Excel**; confirm the numbers
   match the screen.

Sign-off: the staging figures equal the manual sheet for every spot-checked
staff member. Investigate any mismatch before touching prod (the §3 worked
examples are the automated tests — a mismatch is either a setup difference or a
genuine bug).

## 3. Flip the switch on prod — Super Admin first

The switch is `payroll_config.payroll_enabled`. Flip it as a Super Admin:

- **Preferred (UI):** the Payroll **Settings** page → *Enable payroll module*.
  While the nav is still hidden, reach it directly at `/payroll/settings`.
- **API:** `PUT /api/v1/payroll/config` with `{"payroll_enabled": true}` (Super
  Admin cookie). The change is audited.

Once enabled, the Payroll nav appears for admins (`super_admin` / `branch_admin`).
Run the same parallel-month check for the latest real month on prod **without
closing it** (preview only) and compare to the manual sheet.

## 4. Widen access — Accounts and HR

Payroll screens already respect §9 roles (report: accounts/branch_admin/manager;
ledger: super_admin/accounts; all setup + settings: super_admin). No further
flag is needed — once the module is on, those roles see what their role allows.
Brief Accounts/HR, then let them use the Report and (where permitted) raise
extra-day requests.

## 5. First real close

Close the first live month only after the preview has been reconciled with the
manual sheet. Closing writes the ledger and freezes the snapshot; a mistake is
recoverable by **Reopen** (Super Admin + reason, later months recompute), but
reconcile first to avoid churn.

## Rollback

- **Fastest:** flip `payroll_enabled` back to `false` — the module disappears
  from the UI immediately. Data stays intact (dormant), so you can re-enable
  after a fix.
- **Schema:** `alembic downgrade 0068` drops the payroll tables and the
  append-only trigger (reversible migration). Only needed to remove the module
  entirely.
- **Full:** restore the backup proven in step 1.

## Notes / guardrails

- The carry-forward ledger is append-only (Postgres trigger blocks UPDATE/DELETE);
  corrections are reversal rows. Never edit ledger rows by hand.
- A manual `backend` container recreate skips migrations — re-run the `migrate`
  service, don't shortcut it (see root `CLAUDE.md`).
- Cookie/session note does not apply here; enabling payroll takes effect on the
  next page load (the nav reads the flag live).
