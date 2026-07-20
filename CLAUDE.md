# CLAUDE.md

Coaching-academy academic intelligence platform. FastAPI + Postgres backend,
Next.js 16 App Router frontend, deployed by Docker Compose to a single Hetzner
VPS.

This file is the entry point. It carries the things you can't infer from the
code; the deep references live in `docs/` and are linked below.

## Read before you touch these areas

| Area | Doc |
|---|---|
| Stack, runtime topology, prod compose | `ARCHITECTURE.md` |
| Layering rules, auth/permission rules | `docs/coding_rules.md` |
| Endpoint shape, versioning, errors | `docs/api_conventions.md` |
| Table base fields, branch isolation, soft delete | `docs/db_conventions.md` |
| Test pyramid, what to test at each layer | `docs/testing_rules.md` |
| Branch → PR → deploy loop, deploy gotchas | `docs/git-and-deploy-workflow.md` |
| Resilience / CI / tooling backlog | `docs/platform-hardening-roadmap.md` |

## Commands

Backend (from `backend/`, venv at `backend/.venv`):

```bash
.venv/Scripts/python.exe -m pytest                 # full suite; SQLite in-memory
.venv/Scripts/python.exe -m pytest tests/test_x.py -q
.venv/Scripts/alembic.exe upgrade head             # apply migrations
.venv/Scripts/alembic.exe revision --autogenerate -m "..."
```

Tests default to in-memory SQLite for speed. **CI runs the same suite against
real Postgres 16** (`TEST_DATABASE_URL`), so PG-only behaviour — ARRAY columns,
native FK enforcement, partial unique indexes — is only exercised there. If you
touch any of those, run against Postgres locally before pushing or CI will be
the first thing to tell you.

Frontend (from `frontend/`):

```bash
npm run typecheck     # tsc --noEmit — gating in CI, keep at zero
npm run lint:ci       # gating in CI at a --max-warnings baseline
npm run test:unit     # vitest
npm run test:e2e      # playwright
npm run dev           # proxies /api/* to localhost:8000
```

## Backend module anatomy

`backend/app/modules/<domain>/` — 18 of them (student, lectures, attendance,
tests, materials, …). Every one has the same five directories:

```
api/           routes.py — HTTP only, no business logic, no DB
services/      business logic; the only place rules live
repositories/  data access; the only place queries live
models/        SQLAlchemy models
schemas/       Pydantic request/response
```

Route → Service → Repository → DB is enforced by convention, not tooling. A
route that opens a session or a service that writes raw SQL is a bug, even if it
works. `app/core/` holds cross-cutting config, database, logging, middleware,
security, storage; `app/jobs/` and `app/events/` hold Celery tasks and the
event bus.

Frontend mirrors this loosely: route pages in `app/(dashboard)/<route>/page.tsx`,
route-private components in a sibling `_components/`, shared primitives in
`components/ui/`.

## Landmines

These have each cost real debugging time. They are not obvious from the code.

- **Duplicate subject rows across courses.** The same subject name exists as
  separate rows per course, so any exact `subject_id` filter silently drops
  data. Match on subject *name* across sibling rows instead. Fixed so far in
  questions and schedule-teachers; when you fix another, fix the read *and*
  write path together or the data drifts.
- **Branch isolation is a data-correctness rule, not a feature.** Every core
  academic query must filter by `branch_id`. Missing it leaks another branch's
  students into a roster. `tests/test_branch_isolation.py` guards this — extend
  it when you add a module.
- **Soft delete is the default.** `DELETE` sets `is_deleted`; it does not remove
  rows. Queries must filter `is_deleted = false` or deleted records reappear.
- **Prod: a manual container recreate skips migrations.** The `migrate` service
  is one-shot and runs before the app. If you recreate `backend` by hand you get
  new code on an old schema. Re-run the migrate service, don't shortcut it.
- **Prod: pre-volume uploads are gone.** Study material now lives on a
  host-mounted volume; anything uploaded before that change did not survive.
- **Cookie/auth changes require a fresh login** to take effect — existing
  sessions carry the old cookie and will look like the change didn't deploy.
- **DPP coverage has no retroactive credit.** The lectures KPI counts only
  composer-created DPPs after 2026-06-28; older lectures read as uncovered by
  design, not by bug.
- **`gh pr merge --auto` only waits for CI when branch protection requires
  checks.** Without it, it merges immediately with checks pending. See the
  gotcha section in `docs/git-and-deploy-workflow.md`.

## Frontend conventions

- **Page headers**: every dashboard page uses the compact
  `<PageHeader title actions>`. Long descriptions go behind the ⓘ `InfoHint`,
  never inline. Detail pages keep the entity name as the heading.
- **Confirmations**: never `window.confirm/alert/prompt` — use
  `components/ui/confirm-dialog.tsx`. This is lint-enforced.
- **Bulk actions**: explicit row selection (checkboxes) via `use-row-selection`
  plus the shared selection bar. Never offer a blind "delete by date" style bulk
  action — the user picks the set and the target.
- **Every route needs its boundaries.** `app/(dashboard)/error.tsx` and
  `loading.tsx` cover the group; add a route-level one only when a section needs
  a different shape.
- **Polymorphic components** use Base UI's `render` prop:
  `<Button render={<Link href="/x" />}>Label</Button>`.

## Lint baseline

`frontend/eslint.config.mjs` demotes three rules (`no-explicit-any`,
`set-state-in-effect`, `static-components`) to warnings with a documented
pre-existing count, and `lint:ci` caps the total with `--max-warnings`. **The cap
only moves down.** Fixing violations means lowering the number in
`package.json` in the same PR. Do not raise it to make a build pass.

Most of the `any` count is untyped API payloads and will fall out naturally once
a typed client is generated from `openapi.json`.

## Working agreements

- Branch off fresh `master`, never commit to it directly. Squash-merge via PR.
- Stage explicit paths (`git add <paths>`), never `git add -A` — the repo
  carries untracked scratch directories (`misc/`, `study_material/`, `uploads/`)
  that must not be committed.
- Frontend work is expected to land type-safe, tested, and responsive per
  change — not as a cleanup pass afterwards.
- Prefer extending an existing module over adding a new one; 18 is already a
  lot of surface.
