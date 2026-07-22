# Delivery Workflow Architecture

How code gets from a local edit to production, and the controls that make that
safe. Companion to `docs/git-and-deploy-workflow.md`, which is the *procedure*;
this is the *design and its rationale*.

Written 2026-07-20.

---

## Governing principle

**Every safety claim must be executable and self-verifying, not written down.**

This document exists because of a concrete failure. `ARCHITECTURE.md` and
`docs/git-and-deploy-workflow.md` both described a required-reviewer approval
gate on production deploys. The `production` GitHub environment had
`protection_rules: []`. There was no gate, there had not been one for as long as
the config had existed, and nothing detected the gap — it surfaced by accident
during an unrelated PR.

The lesson is not "add the gate". It is that prose describing a control is
indistinguishable from a control that does not exist. Wherever this pipeline
claims a guarantee, something must assert it.

A second principle follows from the first, and from this being a
single-maintainer project:

**Optimise for fast detection and cheap reversal, not for more approvals.**

Blanket approval gates on a solo project train reflexive clicking, which is
worse than no gate — it manufactures a feeling of safety with none of the
substance. Gates are reserved for the small number of changes that are genuinely
hard to undo.

---

## The pipeline

```
local commit ──▶  PR  ──▶ master ──▶ staging ──▶  prod  ──▶ post-deploy verify
   hook           fast     full       smoke       deploy      auto-rollback
   ~10s          ~4 min   ~14 min      e2e                    on failure
```

### 1. Local — pre-commit hook

`typecheck` + `lint` + tests for changed files only. Seconds, not minutes.
Catches trivia before it costs a full CI cycle.

### 2. PR — a *fast* required gate

The required checks must stay under about five minutes. This is not comfort, it
is a control: **slow gates are the ones people work around**, and a bypassed
gate protects nothing. The backend suite currently takes ~14 minutes, which
makes it the single largest structural threat to this workflow.

Split it:

| Lane | Contents | Runs on | Target |
|---|---|---|---|
| Fast | typecheck, lint, unit, affected integration | every PR (required) | < 4 min |
| Full | entire pytest suite, coverage, e2e, security scans | merge to master, nightly | unbounded |

`ci.yml` already has a `fast:` input for the deploy path. The same split should
apply to the backend suite itself.

### 3. Merge to master → staging, automatically

`deploy-staging.yml` exists and is not in the path. It should be: master deploys
to staging first, and the Playwright suite runs **against a real deployed
stack** rather than in CI. This is where e2e earns its cost — exercising the
four MVP flows (student import, lecture schedule, attendance marking,
per-student test dashboard) against real containers, a real database, and the
real nginx proxy.

### 4. Staging green → production

Automatic for ordinary changes. Gated for exactly one case: **deploys that carry
a database migration**. See "Migration safety" below.

### 5. Post-deploy verification is a job, not a person

`infra/scripts/deploy.sh` already waits on the backend healthcheck, which
catches a container that fails to start. It does not catch an application that
starts and then serves wrongly — the auth proxy misrouting, the frontend
rendering a 500, a rewrite rule that breaks `/api`.

Verification runs from outside the box, against the public hostname, and its
failure fails the deploy:

- `GET /login` → 200 (frontend renders, nginx and TLS terminate correctly)
- `GET /api/v1/<authed>` without a cookie → 401 (backend reachable through the
  proxy; auth is enforced, not merely present)
- backend healthcheck → 200 on the internal port
- no container in the compose project is `restarting` or `dead`, and backend
  and frontend are both `running`

That last check exists because HTTP probes only exercise the services that
answer HTTP. The Celery worker crash-looped on a bad `-A` module path through
roughly thirty deploys, and every one of them verified green: `deploy.sh` waits
only on the backend healthcheck, and both probes hit backend/frontend. A
service that never starts is invisible to a check that only asks whether the
site responds.

### 6. Rollback is a first-class path

Images are already SHA-tagged, which is the hard part. What was missing is a
recorded previous-good tag and a one-command path back to it. On verification
failure the pipeline redeploys the last known-good images automatically; the
same path is available manually via `workflow_dispatch`.

**Rollback must not depend on the registry.** The first hand-run drill
(2026-07-21) failed: `rollback.sh` execs `deploy.sh`, which pulled before
restarting, and the hand-run path has no `GHCR_TOKEN`, so the pull was denied
and the rollback aborted with exit 18. The pull was never necessary — a
rollback target was running minutes earlier and is by definition already on the
host. `deploy.sh` now continues past a pull failure when it can prove both
images are present locally, and fails loudly when it cannot.

That drill also exposed the failure mode to check for: `deploy.sh` rewrites
`.env.<env>` and `.prev-images.<env>` *before* restarting anything, so an abort
between those two points leaves the env file naming images that are not
running, and a later `docker compose up` would silently switch releases.
Reconcile both files against `docker ps` after any failed rollback.

**Code rollback is trivial. Schema rollback is not.** That asymmetry is why
migrations get their own rules.

---

## Migration safety

The realistic worst outcome for this platform is not downtime — it is corrupting
student, attendance, or test data. Alembic down-revisions are written but almost
never executed, so a bad migration is effectively irreversible under pressure.

Three rules:

**Expand / contract.** Never add a column and start writing to it in the same
deploy that drops the old one. Old code must always work against the new schema.
This is what makes rollback possible at all — without it, reverting the image
puts old code in front of a schema it cannot read.

**Destructive operations are gated.** A PR that adds an Alembic revision routes
the deploy through an environment with a required reviewer. This is rare enough
that the approval stays meaningful. Everything else ships unattended.

**Snapshot before migrating, and prove the snapshot restores.** `infra/backup/`
exists; it belongs in the deploy path immediately before any migration-bearing
release. An unverified backup is not a backup — a scheduled restore rehearsal is
the only thing that turns it into one.

---

## Observability

Until error reporting exists, every other control in this document is guessing.

The error boundaries added in H2 render a styled panel to the user and, by
themselves, tell the operator nothing. The `digest` shown to the user resolves
to a stack trace only if something recorded it.

- **Sentry** for frontend and backend exceptions, with source maps uploaded at
  build time so production stacks are readable rather than minified frames.
- **PII scrubbing before send is mandatory.** Student names, phone numbers,
  emails, and parent contact details flow through most pages in this app. The
  reporter is an external processor; it must never receive them.
- **A `correlation_id` shared between frontend report and backend request**, so
  a user-visible reference resolves to both sides of the failure.
- **One real alert**, not a dashboard nobody opens.

---

## Config drift detection

The control that would have caught the missing approval gate: a CI job that
asserts live repository configuration matches a committed spec — branch
protection, required status checks, environment protection rules.

Any divergence between what this repo *claims* and what GitHub *enforces*
fails a build, rather than waiting to be discovered.

Implemented as:
- **`.github/config-spec.json`** — the committed source of truth. To change the
  real config, change it on GitHub *and* update this file in the same PR.
- **`.github/scripts/check_config_drift.py`** — reads live config via `gh api`
  and fails on any mismatch. Asserts only keys the spec declares, so
  integration-managed environments (Vercel's Preview/Production) never trip it.
  Inability to *read* the config is itself a failure — a check that can't see
  the config is the blind spot this job removes.
- **`.github/workflows/config-drift.yml`** — daily, plus on any change to the
  spec/checker/deploy pipeline, plus manual. Environment gates are asserted with
  the built-in token — this is the half that catches the incident that motivated
  the job, and it needs zero configuration.

Branch protection is **left as a warning by design**, not for want of a token.
The *classic* branch-protection REST API is unreadable by the Actions token
*and* by fine-grained PATs (those reach only the newer rulesets API, even with
`administration: read` — confirmed the hard way on 2026-07-22). The only token
that can read it is a classic `repo`-scope PAT, which grants broad, long-lived
read/write access to the whole repo — a strictly worse security posture than
the narrow, low-probability gap it would close on a solo repo. If collaborators
are ever added, migrate `master` from classic branch protection to a
**repository ruleset** and point the checker at `repos/<repo>/rulesets`; a
fine-grained *read-only* PAT (`CONFIG_AUDIT_TOKEN`, already an optional override)
reads that API cleanly.

The spec deliberately records that `production` must stay *unprotected* and
`production-migrations` must keep its reviewer, so re-introducing a blanket gate
(or dropping the migration gate) both count as drift.

---

## Open decisions

**Deploy target.** Vercel builds this repository in parallel with the Hetzner
pipeline; three Vercel deployments ran during a single PR on 2026-07-20. Two
live targets with independent configuration is drift waiting to happen. One
should be authoritative and the other disabled or formally scoped to previews.

**Test suite runtime.** The 14-minute backend suite is tolerable today because
merges are infrequent. It stops being tolerable the moment it is on the critical
path of an incident fix.

---

## Implementation status

| # | Item | Status |
|---|---|---|
| 1 | Error reporting (Sentry, both tiers, PII-scrubbed) | see `docs/platform-hardening-roadmap.md` H3 |
| 2 | Post-deploy verification + auto-rollback | this change |
| 3 | Migration-gated prod approval + corrected docs | this change |
| 4 | Config-drift assertion job | done — `.github/config-spec.json` + checker + workflow |
| 5 | Fast/full test split | planned |
| 6 | Staging in the path + e2e smoke | planned |
| 7 | Migration rules + verified backup restores | partially — rules documented, backup wiring planned |
| 8 | One-command rollback | this change |
