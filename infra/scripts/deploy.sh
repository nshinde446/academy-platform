#!/usr/bin/env bash
# Deploy entrypoint — executed on the VPS by the GitHub Actions workflow over SSH.
#
# Usage:
#   deploy.sh <env> <backend-image> <frontend-image>
#     env             — "prod" or "staging"
#     backend-image   — e.g. "ghcr.io/nshinde446/academy-platform-backend:abc1234"
#     frontend-image  — e.g. "ghcr.io/nshinde446/academy-platform-frontend:abc1234"
#
# Idempotent. Pulls the new images, runs migrations as a one-shot, restarts
# backend + worker + frontend. The compose stack already has health checks;
# if migration fails the new backend won't start (depends_on / condition).

set -euo pipefail

ENV="${1:?env required (prod|staging)}"
BACKEND_IMAGE="${2:?backend image tag required}"
FRONTEND_IMAGE="${3:?frontend image tag required}"

case "$ENV" in
    prod)
        COMPOSE_FILE="docker-compose.prod.yml"
        ENV_FILE=".env.prod"
        PROJECT="academy-prod"
        ;;
    staging)
        COMPOSE_FILE="docker-compose.staging.yml"
        ENV_FILE=".env.staging"
        PROJECT="academy-staging"
        ;;
    *)
        echo "Unknown env: $ENV (want prod|staging)" >&2
        exit 2
        ;;
esac

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT/infra/compose"

if [[ ! -f "$ENV_FILE" ]]; then
    echo "Missing $REPO_ROOT/infra/compose/$ENV_FILE — create it from ${ENV_FILE}.example" >&2
    exit 3
fi

# Inject the new image tags into the env file used by compose for image
# substitution. Re-writes the BACKEND_IMAGE / FRONTEND_IMAGE lines atomically.
tmp=$(mktemp)
grep -vE '^(BACKEND_IMAGE|FRONTEND_IMAGE)=' "$ENV_FILE" > "$tmp" || true
{
    echo "BACKEND_IMAGE=$BACKEND_IMAGE"
    echo "FRONTEND_IMAGE=$FRONTEND_IMAGE"
} >> "$tmp"
mv "$tmp" "$ENV_FILE"
chmod 600 "$ENV_FILE"

echo "==> Logging into GHCR (token comes from CI env)"
if [[ -n "${GHCR_TOKEN:-}" ]]; then
    echo "$GHCR_TOKEN" | docker login ghcr.io -u "${GHCR_USER:-token}" --password-stdin
fi

echo "==> docker compose pull (backend: $BACKEND_IMAGE, frontend: $FRONTEND_IMAGE)"
docker compose -p "$PROJECT" -f "$COMPOSE_FILE" --env-file "$ENV_FILE" pull

echo "==> docker compose up -d (migrations run as one-shot, then backend/worker restart)"
docker compose -p "$PROJECT" -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d --remove-orphans

echo "==> wait for backend healthcheck (max 60s)"
deadline=$(( $(date +%s) + 60 ))
PORT=$([[ "$ENV" == "prod" ]] && echo 8000 || echo 8001)
until curl -fsS "http://127.0.0.1:$PORT/health" >/dev/null 2>&1; do
    if (( $(date +%s) >= deadline )); then
        echo "FAIL: $ENV backend did not become healthy in 60s" >&2
        docker compose -p "$PROJECT" -f "$COMPOSE_FILE" logs --tail=80 backend
        exit 4
    fi
    sleep 2
done

echo "==> docker image prune"
docker image prune -f >/dev/null

echo "==> $ENV deploy OK (backend: $BACKEND_IMAGE, frontend: $FRONTEND_IMAGE)"
