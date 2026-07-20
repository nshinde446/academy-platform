# Platform Hardening Roadmap

Production-readiness work on the platform itself — resilience, type safety, CI
gating, and the repo's own developer tooling. Distinct from the feature
roadmaps (`coaching-test-loop-roadmap.md`,
`question-bank-and-dpp-roadmap.md`) and from `UI_ROADMAP.md`, which is product
UX.

Opened 2026-07-20 from a full-repo review. Ordered by payoff; each item is
independently shippable.

---

## H1 — Project guidance + CI gates ✅ done 2026-07-20

- Root `CLAUDE.md`: module anatomy, commands, conventions, landmines, and an
  index into the `docs/` references. Previously there was no root-level
  guidance for 404 source files.
- `npm run typecheck` (`tsc --noEmit`) added to CI as a **gating** step. It
  already passed at zero, so a type error could previously merge clean.
- `npm run lint:ci` added to CI as a **gating** step, at a documented
  `--max-warnings` baseline that only moves down.
- eslint config fixed to ignore `coverage/**` and hand-run `*.cjs` scripts.

## H2 — Frontend error and loading boundaries ✅ done 2026-07-20

19 routes previously had zero `error.tsx` / `loading.tsx` / `not-found.tsx`, so
any unhandled throw unwound to a blank white screen.

- `app/global-error.tsx` — root-layout failures; self-contained, no imports.
- `app/error.tsx` — `/login` and `(dashboard)/layout.tsx` crashes.
- `app/(dashboard)/error.tsx` — all dashboard routes, sidebar stays mounted.
- `app/(dashboard)/loading.tsx`, `app/not-found.tsx`.
- Shared `components/ui/error-state.tsx` + tests.

## H3 — Error reporting

**The boundaries from H2 currently fail silently from our side.** The user gets
a styled panel; we never learn the crash happened. The `digest` shown to the
user is only useful if something on our end recorded the matching stack trace —
today nothing does. Right now the only signal is a `console.error` under a
`[boundary:*]` prefix, visible solely if someone is looking at their own
devtools.

This is the highest-value item remaining, because it is what turns H2 from
"crashes look nicer" into "we find out about crashes".

Scope:

- Pick a reporter. Two credible options:
  - **Sentry** — fastest path, gives release tracking and source-mapped client
    stacks out of the box; external SaaS.
  - **OpenTelemetry → the existing `infra/monitoring/` stack** — no new vendor,
    keeps data on the VPS, but client-side error capture needs more wiring.
- Report from all three boundaries, replacing the `console.error` stopgap, and
  include the `digest` so the user-facing reference resolves to the trace.
- Capture backend exceptions too — pair with a `correlation_id` so a frontend
  report and its backend request can be joined.
- Upload frontend source maps at build time, otherwise production stacks are
  unreadable minified frames.
- Scrub PII before send: student names, phone numbers, and emails flow through
  most of these pages.
- Set a real alert (not just a dashboard) so a spike surfaces without anyone
  checking.

## H4 — Typed API client

`frontend/services/` is a 30-line axios wrapper; `modules/` and `utils/` are
empty. There is no typed layer over the API, which is why 68 `any`s exist.

- Generate types from the backend's `openapi.json` into the build.
- Replace ad-hoc `axios` calls and untyped payloads; backend contract changes
  then fail at compile time instead of at runtime in front of a client.
- Lower the `lint:ci` `--max-warnings` cap as the `any` count drops — most of
  the baseline debt disappears with this item.

## H5 — Slash commands for repeated scaffolding

`.claude/commands/`, cheapest tooling win:

- `/new-module <name>` — the five-directory backend module + a test file.
- `/new-page <route>` — page + route-level boundaries + a test.
- `/ship` — run the full gate, then branch → commit → PR.

## H6 — E2E coverage of the MVP flows

One spec (`login.spec.ts`) covers 19 routes, and it does not gate: both the
Playwright install and run are `continue-on-error`.

- Smoke specs for the four MVP flows: student import, lecture schedule,
  attendance marking, per-student test dashboard.
- Make them blocking once stable, or delete the decorative steps. The same
  applies to `npm audit` and `bandit`, both currently `|| true`.

## H7 — Split the oversized route components

`lectures/page.tsx` is 1170 lines with six sibling dialogs of 350–530 lines.
Not urgent, but it is where the next bug will land.

## H8 — Write-time feedback hooks

A `PostToolUse` hook on `Edit`/`Write` of `frontend/**/*.tsx` running
`tsc --noEmit` + eslint on the touched file — catches type errors at write time
rather than in CI.

## H9 — Review subagents

Only worth building once the above is stable, and only for genuinely parallel,
self-contained work:

- `migration-reviewer` — checks each Alembic revision for down-revision
  correctness, branch-isolation filters, and index coverage.
- `route-hardener` — walks one route at a time adding boundaries and tests.

Deliberately **not** an "architect agent" — architecture decisions should stay
in the loop with a human.
