# Architecture

Tech stack and runtime topology for the coaching academy platform. Sourced from
`backend/requirements.txt`, `frontend/package.json`,
`infra/compose/docker-compose.prod.yml`, and `.github/workflows/`.

## At a glance

| Layer | Technology |
|---|---|
| Frontend | Next.js 16 (App Router) · React 19 · TypeScript 5 · Tailwind CSS 4 · Base UI / shadcn |
| Frontend state | TanStack Query 5 (server) · Zustand 5 (client) · axios |
| Backend | FastAPI (async) · Uvicorn · Python · Pydantic v2 |
| ORM / migrations | SQLAlchemy 2.0 async · asyncpg · Alembic |
| Background jobs | Celery 5 (worker + beat) |
| Database | PostgreSQL 16 |
| Cache / broker | Redis 7 |
| Containers | Docker + Docker Compose |
| Host edge | nginx (TLS termination + reverse proxy) |
| Hosting | Single Hetzner VPS (Ubuntu) |
| CI/CD | GitHub Actions · GHCR · SSH deploy |
| Domain | `app.eduworld-livekit.duckdns.org` (DuckDNS) |

## Frontend

- **Next.js 16.2.6** on the App Router, **React 19.2**, **TypeScript 5**. Runs as
  a standalone Node server (not a static export) so it can proxy `/api/*` and
  `/iclock/*` to the backend server-side.
- **Styling:** Tailwind CSS 4, **Base UI** (`@base-ui/react`) primitives, and
  **shadcn** components; **lucide-react** icons.
- **State / data:** **TanStack Query 5** for server state and caching; **Zustand
  5** for client state (auth / user store); **axios** API client.
- **Math rendering:** KaTeX / react-katex (question bank, paper previews).
- **Auth gate:** `frontend/proxy.ts` (this Next version's middleware) redirects to
  `/login` when no access/refresh cookie is present. It runs *before* the
  `next.config` rewrites, so `api` and `iclock` are excluded from the matcher —
  biometric devices pushing to `/iclock/*` authenticate at the backend, not via a
  web session.
- **Testing:** Vitest 4 + Testing Library (unit), Playwright (e2e).

## Backend

- **FastAPI** (fully async) served by **Uvicorn**; **Pydantic v2** /
  pydantic-settings for schemas and config.
- **Data:** **SQLAlchemy 2.0 async** ORM over the **asyncpg** driver; **Alembic**
  migrations run as a one-shot `migrate` service before the app boots, so new app
  code never sees an old schema.
- **Auth:** JWT (python-jose) with **passlib + bcrypt** password hashing; access
  and refresh tokens delivered as cookies.
- **Background work:** **Celery 5** worker + beat, brokered by **Redis** — e.g.
  the eTimeOffice attendance poll (~every 10 min) and the materials ingest
  pipeline.
- **Outbound HTTP:** httpx (eTimeOffice pull, Gemini calls).
- **Domain libraries:** PyMuPDF (`fitz`) and a **Playwright headless Chromium**
  for branded PDF generation (KaTeX rendered in-browser so output matches the
  question-bank preview); **google-genai** (Gemini Vision) for question
  extraction; openpyxl (Excel reports); Jinja2; matplotlib (legacy PDF fallback).
- **Testing:** pytest + pytest-asyncio (SQLite / aiosqlite in tests).

## Database & cache

- **PostgreSQL 16** (`postgres:16-alpine`) — primary datastore. Kept on the
  private Docker bridge network, never exposed to the public internet; persisted
  to the `pgdata` volume with a 60s healthcheck grace window for crash recovery.
- **Redis 7** (`redis:7-alpine`) — Celery broker/result backend and cache.
  Append-only persistence, 256 MB cap with `allkeys-lru` eviction.

## Runtime topology (production)

Everything runs in **Docker Compose** on one VPS as the `academy-prod` project:

```
                 Internet (HTTPS)
                       │
                 host nginx  (TLS termination, reverse proxy)
              ┌────────┴─────────┐
   :3000 (localhost)        :8000 (localhost)
      frontend  ───────────►  backend (FastAPI)
   (Next.js server)          │   │   │
                             db  redis  worker (Celery)
                             │     │
                          pgdata  redis_data        migrate (one-shot: alembic upgrade head)
```

- `frontend` and `backend` ports bind to **localhost only**; all public traffic
  enters through host **nginx**, which terminates TLS and reverse-proxies.
- The frontend talks to the backend over the internal Docker network
  (`API_BASE_URL=http://backend:8000`), skipping a public TLS round-trip.
- `worker` (Celery) shares the backend image and the study-material volume.
- **Uploaded study material** lives on a host-mounted directory
  (`/srv/academy/study_material`) so files survive container restarts and image
  swaps.

Compose services: `db`, `redis`, `migrate`, `backend`, `worker`, `frontend`
(a separate `infra/monitoring/` compose runs monitoring).

## CI/CD

Trunk-based on `master`, via **GitHub Actions**.

- **CI (on PR)** — `.github/workflows/ci.yml`: backend **pytest** + frontend
  **vitest** are the required status checks; coverage, e2e, and a security scan
  also run. `master` has **branch protection** with these checks required.
- **Deploy (push to `master`)** — `.github/workflows/deploy-prod.yml`:
  1. Build SHA-tagged `backend` and `frontend` images and push to **GHCR** (in
     parallel jobs).
  2. **Re-run** the unit suites as a gate (`fast: true` skips coverage/e2e/scan)
     so a direct-to-master push can't ship untested code.
  3. **SSH deploy** (`appleboy/ssh-action`) into the VPS: `git reset --hard
     origin/master`, then `infra/scripts/deploy.sh` pulls the SHA-tagged images
     and recreates the stack; superseded images are pruned.
  - The SSH deploy (the only prod mutation) is gated behind the `production`
    environment's **required-reviewer approval**; the image builds run ahead of
    approval since they're cheap and harmless.

## External integrations

- **Biometric attendance** (two vendor products, one funnel):
  - **eTimeOffice** — cloud REST **pull** (`DownloadInOutPunchData`), polled by a
    Celery beat job plus a manual admin "pull" button.
  - **BioMax / ZKTeco** — on-prem devices **push** via the ADMS `iclock` protocol
    (`/iclock/cdata`, `/iclock/getrequest`), authenticated by device-serial
    allowlist.
  - Both converge on one pipeline: `PunchEvent → ingest → DailyAttendance
    (Layer 1) → lecture projection (Layer 2)`.
- **AI:** Google **Gemini** (Vision) for question extraction from uploaded
  material; DeepSeek referenced for question generation.

## Repository layout

```
backend/    FastAPI app, SQLAlchemy models, Alembic migrations, Celery tasks
frontend/   Next.js App Router app, components, hooks, tests
infra/      compose files (prod / staging), deploy scripts, monitoring
docs/       design + workflow docs
.github/    CI and deploy workflows
```
