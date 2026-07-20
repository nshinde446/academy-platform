#!/usr/bin/env bash
# Roll back to the images that were running before the most recent deploy.
#
# Usage:
#   rollback.sh <env>          # env: prod | staging
#
# Reads infra/compose/.prev-images.<env>, written by deploy.sh immediately
# before it overwrote the env file, and re-runs deploy.sh with those tags.
#
# Scope and limits — read before relying on this:
#   * This rolls back CODE ONLY. It does not reverse database migrations.
#     A deploy that migrated the schema is NOT safely undone by this script
#     unless the migration was written expand/contract style, i.e. the old
#     image can still read the new schema. That is exactly why
#     migration-bearing deploys are gated behind a human approval — see
#     docs/delivery-workflow-architecture.md.
#   * The rollback target is a single step back. Two consecutive bad deploys
#     leave .prev-images pointing at the first bad one; recover by passing an
#     explicit SHA to deploy.sh.

set -euo pipefail

ENV="${1:?env required (prod|staging)}"

case "$ENV" in
    prod|staging) ;;
    *) echo "Unknown env: $ENV (want prod|staging)" >&2; exit 2 ;;
esac

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PREV_FILE="$REPO_ROOT/infra/compose/.prev-images.$ENV"

if [[ ! -f "$PREV_FILE" ]]; then
    echo "FAIL: no rollback target recorded at $PREV_FILE" >&2
    echo "      Deploy an explicit known-good SHA instead:" >&2
    echo "      deploy.sh $ENV <backend-image>:<sha> <frontend-image>:<sha>" >&2
    exit 3
fi

# shellcheck disable=SC1090
BACKEND_IMAGE="$(grep -E '^BACKEND_IMAGE=' "$PREV_FILE" | cut -d= -f2-)"
FRONTEND_IMAGE="$(grep -E '^FRONTEND_IMAGE=' "$PREV_FILE" | cut -d= -f2-)"

if [[ -z "$BACKEND_IMAGE" || -z "$FRONTEND_IMAGE" ]]; then
    echo "FAIL: $PREV_FILE is malformed" >&2
    exit 3
fi

echo "==> ROLLING BACK $ENV to:"
echo "      backend:  $BACKEND_IMAGE"
echo "      frontend: $FRONTEND_IMAGE"

exec bash "$REPO_ROOT/infra/scripts/deploy.sh" "$ENV" "$BACKEND_IMAGE" "$FRONTEND_IMAGE"
