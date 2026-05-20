# Deployment runbook

Production setup for a self-hosted Hetzner VPS (backend + DB + Redis + Celery)
plus Vercel for the Next.js frontend, with a separate staging environment on
the same VPS. CI/CD via GitHub Actions; container images on GHCR; nginx on
the host for TLS + rate limiting + security headers.

```
                ┌──────────────────────────────────────────────┐
                │            Hetzner CX33 (Ubuntu)             │
                │                                              │
   Internet ──▶ │  nginx :80/:443                              │
                │   │                                          │
                │   ├─ api.<domain>          → 127.0.0.1:8000  │  ◀ academy-prod
                │   │                          (compose stack) │
                │   └─ staging-api.<domain>  → 127.0.0.1:8001  │  ◀ academy-staging
                │                              (compose stack) │
                │                                              │
                │  Each stack: backend + worker + db + redis   │
                │  + one-shot migrate (compose service)        │
                │                                              │
                │  ufw: only 22 / 80 / 443 open                │
                │  monitoring (Prom/Grafana/Flower): 127.0.0.1 │
                └──────────────────────────────────────────────┘

   Internet ──▶  Vercel  →  Next.js frontend  (auto-deploys from GitHub)
```

This file is the single source of truth. Read top-to-bottom for first-time
setup; jump to **Day-to-day workflow** once you're live.

## 0. What you need

* A Hetzner CX33 (4 vCPU, 8 GB RAM, 80 GB SSD) running Ubuntu 22.04 or 24.04
  — you have one. Other VPSes work too as long as Docker is supported.
* Root or sudo-capable SSH user on the VPS.
* GitHub repo with admin access (already done).
* (Optional, register later) A domain you control. Until then, the API is
  reachable by IP and Vercel hands you a `*.vercel.app` URL.

## 1. One-time server bootstrap

On the VPS, as a regular sudo user:

```bash
# Clone the repo to a known location.
sudo mkdir -p /srv/academy
sudo chown "$USER":"$USER" /srv/academy
git clone https://github.com/nshinde446/academy-platform.git /srv/academy/repo
cd /srv/academy/repo

# Run the bootstrap script. Installs Docker, nginx, certbot, UFW, sets up a
# 2GB swap file, enables unattended security upgrades, lays down shared nginx
# snippets, and creates /srv/academy/{prod,staging,backups}/ dirs.
bash infra/scripts/server-init.sh

# Re-login so the docker group takes effect (or run `newgrp docker`).
exit
ssh user@<vps-ip>
docker info >/dev/null && echo OK
```

What that script did, for the curious:

* `apt update && upgrade` + base packages (nginx, certbot, ufw, fail2ban,
  unattended-upgrades, postgresql-client).
* `get-docker.sh` if Docker isn't present; adds your user to `docker` group.
* 2 GB swap file at `/swapfile` + `/etc/fstab` entry.
* UFW: deny incoming, allow 22/80/443.
* Auto security updates via `unattended-upgrades`.
* Installs the shared nginx snippets into `/etc/nginx/snippets/` and
  `/etc/nginx/conf.d/rate-limit.conf`.
* Stages the per-env nginx site configs in `/etc/nginx/sites-available/` but
  does NOT symlink them into `sites-enabled/` yet — they reference a
  placeholder `server_name`.

## 2. Create env files on the VPS

```bash
cp /srv/academy/repo/infra/compose/.env.prod.example     /srv/academy/repo/infra/compose/.env.prod
cp /srv/academy/repo/infra/compose/.env.staging.example  /srv/academy/repo/infra/compose/.env.staging
chmod 600 /srv/academy/repo/infra/compose/.env.*

# Generate strong secrets:
python3 -c "import secrets; print(secrets.token_urlsafe(48))"   # SECRET_KEY for .env.prod
python3 -c "import secrets; print(secrets.token_urlsafe(48))"   # different SECRET_KEY for .env.staging
python3 -c "import secrets; print(secrets.token_urlsafe(24))"   # POSTGRES_PASSWORD (one per env)
```

Edit each file and replace the placeholders. **Use different secrets in
staging vs. prod**. The DB password only needs to be strong, not memorable.

Both files are gitignored (`*.env*` is not — but `.env` is, and these are
`.env.prod` / `.env.staging`. Add explicit ignores if you prefer; see step 12
for the gitignore note).

## 3. GitHub Actions secrets

Settings → Secrets and variables → Actions → New repository secret:

| Secret           | Value                                                          |
|------------------|----------------------------------------------------------------|
| `VPS_HOST`       | VPS public IP or hostname                                      |
| `VPS_USER`       | sudo-capable user (e.g. `deploy`)                              |
| `VPS_SSH_KEY`    | Private SSH key (whole contents, including `-----BEGIN ...`)   |
| `VPS_SSH_PORT`   | (Optional) custom SSH port — defaults to 22                    |

Generate a dedicated deploy key on your laptop:

```bash
ssh-keygen -t ed25519 -f ~/.ssh/academy-deploy -C "academy ci deploy" -N ""
# Add the .pub key to /home/<user>/.ssh/authorized_keys on the VPS.
# Paste the private key into VPS_SSH_KEY.
```

Don't reuse your personal SSH key — when it leaks, you rotate one secret, not
all of them.

Settings → Environments → create two:

* `staging` — no protection rules
* `production` — **add "Required reviewers" → yourself**. This means every
  prod deploy needs a manual click in the Actions UI before SSH runs. Solo
  devs sometimes skip this, but it has saved me from a few "I didn't mean
  to merge that PR yet" moments.

## 4. First manual deploy (before CI is wired)

On the VPS:

```bash
cd /srv/academy/repo

# Log into GHCR so docker can pull (use a Personal Access Token with `read:packages`).
echo "<ghcr-token>" | docker login ghcr.io -u nshinde446 --password-stdin

# Pull and bring up prod
docker compose -p academy-prod \
    -f infra/compose/docker-compose.prod.yml \
    --env-file infra/compose/.env.prod \
    up -d --pull=always

# Same for staging
docker compose -p academy-staging \
    -f infra/compose/docker-compose.staging.yml \
    --env-file infra/compose/.env.staging \
    up -d --pull=always

# Verify
curl -fsS http://127.0.0.1:8000/health   # prod
curl -fsS http://127.0.0.1:8001/health   # staging
```

If the prod image hasn't been pushed yet, push it once from your laptop:

```bash
# from the repo root, locally
docker buildx build \
    --platform linux/amd64 \
    --push \
    -t ghcr.io/nshinde446/academy-platform-backend:latest \
    ./backend
```

After this, GitHub Actions takes over (step 6).

## 5. Wire up nginx

On the VPS, edit the staged site configs and put a real `server_name` in:

```bash
sudo nano /etc/nginx/sites-available/api-prod.conf       # set server_name
sudo nano /etc/nginx/sites-available/api-staging.conf    # set server_name
sudo ln -s /etc/nginx/sites-available/api-prod.conf     /etc/nginx/sites-enabled/
sudo ln -s /etc/nginx/sites-available/api-staging.conf  /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

**No domain yet?** Set `server_name _;` in `api-prod.conf` only, leave
staging disabled, and use the bare IP to reach the API (`http://<ip>/health`).
This is a temporary state — skip to step 8 once you have a domain.

## 6. CI/CD flow (the steady-state)

Two GitHub Actions workflows handle deploys:

* `.github/workflows/deploy-staging.yml` — fires on push to `staging`
* `.github/workflows/deploy-prod.yml` — fires on push to `master`,
  *gates on CI green*, requires manual reviewer approval

Both build the backend image, push to GHCR, then SSH into the VPS and run
`infra/scripts/deploy.sh <env> <image-tag>`. That script:

1. Writes the new image tag into the env file (atomically).
2. `docker compose pull` the new image.
3. `docker compose up -d` — Compose v2 sees the migrate service is `restart:
   "no"`, runs it once, waits for `service_completed_successfully`, then
   starts the new backend and worker.
4. Polls `/health` for up to 60s — fails the workflow if not green.
5. Prunes dangling images.

Branch model:

```
feature/* ──PR──▶ master ──auto-deploy──▶ prod
                  ▲
                  └── merge staging when tested
staging   ────────auto-deploy──▶ staging env
```

To promote: open a PR `staging` → `master`. CI runs full suite; merging
triggers prod deploy after your manual approval.

## 7. Frontend on Vercel

Vercel deploys the Next.js frontend separately. One-time:

1. New Vercel project → import this GitHub repo.
2. **Root directory**: `frontend`
3. **Framework preset**: Next.js
4. Environment variables (both Production and Preview):
   * `NEXT_PUBLIC_API_URL` → `https://api.<yourdomain>` (or `http://<vps-ip>`
     until you have a domain)
5. `Production branch`: `master`. Preview deploys auto-fire for every PR and
   for pushes to `staging`.

Vercel rebuilds + auto-deploys on every push to `master`. No GitHub Actions
needed for the frontend.

## 8. Domain & TLS (when you have one)

1. Register a domain (Cloudflare ~$10/year, Namecheap, Porkbun).
2. Cloudflare DNS (free) — point:
   * `app.<domain>`         → Vercel (CNAME `cname.vercel-dns.com`)
   * `api.<domain>`         → VPS IP   (A record)
   * `staging-api.<domain>` → VPS IP   (A record)
3. On the VPS: replace the placeholder `server_name` in
   `/etc/nginx/sites-available/api-{prod,staging}.conf` and reload.
4. Run certbot:

   ```bash
   sudo certbot --nginx -d api.<domain> -d staging-api.<domain>
   ```

   It edits the nginx configs in place, adds the `listen 443 ssl` block,
   redirects 80→443, and installs a cron job for renewal.

5. Uncomment the HSTS header in
   `/etc/nginx/snippets/security-headers.conf` and reload nginx.
6. Update `CORS_ORIGINS` in `.env.prod` and `.env.staging` to your real
   domains, then redeploy.
7. Update Vercel's `NEXT_PUBLIC_API_URL` to the https URL.

## 9. Migrations

Migrations run as a one-shot compose service (`migrate`) before each deploy.
The new `backend` container only starts after the migration succeeds. This
means:

* You can never roll out new code against an old schema.
* If a migration fails, backend doesn't restart — old version keeps serving.

For manual control (rare):

```bash
docker compose -p academy-prod \
    -f infra/compose/docker-compose.prod.yml --env-file infra/compose/.env.prod \
    run --rm migrate alembic upgrade head

# Roll back one revision (only if you know it's safe):
docker compose -p academy-prod \
    -f infra/compose/docker-compose.prod.yml --env-file infra/compose/.env.prod \
    run --rm migrate alembic downgrade -1
```

**Rule**: every migration should be backwards-compatible with the previous
deploy. Add columns nullable, deprecate by ignoring before dropping, etc.

## 10. Backups

The existing `infra/backup/backup.sh` does `pg_dump` + optional S3 upload + 7-day
retention. Wire it up via cron on the VPS:

```bash
# Edit the existing infra/backup/cron/backup_crontab to point at /srv/academy
# and the prod container, then install:
sudo cp /srv/academy/repo/infra/backup/cron/backup_crontab /etc/cron.d/academy-backup
sudo chmod 644 /etc/cron.d/academy-backup
```

Backup the *staging* DB only if you'd be sad to lose its test data — usually
no, since you can re-seed it.

**Test restore once before you need it**:

```bash
# On the VPS:
bash /srv/academy/repo/infra/backup/restore_test.sh
```

If you go even semi-serious, ship dumps off-box: Hetzner Storage Box (€3/mo,
50 GB) or Cloudflare R2 (free up to 10 GB, no egress fees). The backup script
already supports `aws s3 cp` — R2 is S3-compatible.

## 11. Monitoring

Existing stack lives in `infra/monitoring/` — Prometheus, Grafana,
Alertmanager, Flower (Celery), plus postgres-exporter and redis-exporter.

**Don't expose those ports.** The compose currently uses `ports: 9090:9090`
etc. — that's wrong for prod. Either:

1. Change those bindings to `127.0.0.1:9090:9090`, OR
2. Tunnel via SSH when you need to look:

   ```bash
   ssh -L 3001:127.0.0.1:3001 -L 9090:127.0.0.1:9090 user@<vps-ip>
   ```

   Then browse http://127.0.0.1:3001 (Grafana). The default password is
   `admin:admin` — **rotate it immediately**.

Tier-2 follow-up: add Sentry (free tier, two SDKs) for unhandled exception
reporting. 10 minutes of setup, catches what Grafana doesn't.

## 12. Gitignore additions

Add to `.gitignore`:

```
infra/compose/.env.prod
infra/compose/.env.staging
```

The `.example` files are committed; the real values never are.

## 13. Day-to-day workflow

```
# 1. work on a feature branch
git checkout -b feature/whatever
# ... edits ...
git push -u origin feature/whatever

# 2. open PR to master — CI runs, you review
# 3. merge to master — prod deploy workflow fires, waits for your approval
# 4. approve in Actions UI — backend image builds, ships to VPS, /health gates the rollout

# To validate first:
git checkout master && git pull
git checkout -b staging-promote && git merge --ff-only staging
git push                                # if staging branch is ahead
# OR push directly to staging to test:
git push origin master:staging          # forces staging to mirror master
```

## 14. Rollback

The deploy script tags each image with the commit SHA. To roll back:

```bash
# on VPS
cd /srv/academy/repo
bash infra/scripts/deploy.sh prod ghcr.io/nshinde446/academy-platform-backend:<previous-sha>
```

If the rollback also needs to reverse a migration, run `alembic downgrade`
manually (step 9). The script does **not** auto-downgrade — migrations are
one-way unless you say otherwise.

## 15. Cost estimate

| Item                                  | Monthly       |
|---------------------------------------|---------------|
| Hetzner CX33 (you already pay this)   | ~€6           |
| Vercel (Hobby, fine until ~100K req)  | $0            |
| Cloudflare DNS                        | $0            |
| Domain registration (annualised)      | ~$1           |
| Hetzner Storage Box for off-box backup| ~€3 (optional)|
| Sentry (Hobby tier)                   | $0 (optional) |
| **Total**                             | **~€7-10**    |

GHCR is free for public images and 500MB free for private (you only need
~50MB).

## 16. What's *not* in this doc on purpose

* **Kubernetes** — overkill for a single VPS.
* **Terraform** — you have one VPS. Click in the Hetzner UI.
* **Managed Postgres** — adds €15+/month for benefits you don't need yet.
  Revisit at the 5-institute mark.
* **Multi-region** — you have users in one country. Don't.
* **gRPC, service mesh, message queues beyond Redis** — premature.
* **Blue/green deploy** — a 5-second restart with healthcheck-gated rollout
  is good enough until you have paying customers complaining about downtime.

## 17. When something breaks

Diagnostic order, from cheapest to most expensive:

1. `curl -fsS http://127.0.0.1:8000/health` on the VPS — is the backend
   itself up?
2. `docker compose -p academy-prod -f ... logs --tail=200 backend` —
   exception in the app?
3. `docker compose -p academy-prod -f ... logs migrate` — schema problem?
4. `docker compose -p academy-prod -f ... ps` — are services in a restart
   loop?
5. `sudo systemctl status nginx` + `sudo nginx -t` — proxy itself broken?
6. `df -h` and `free -h` — disk or memory pressure?
7. Postgres logs (`docker compose -p academy-prod -f ... logs db`) — DB out
   of connections, OOM, etc.?

For anything not obvious from logs, screenshot or paste output into a
conversation with Claude — most prod incidents look like one of the above
five categories.
