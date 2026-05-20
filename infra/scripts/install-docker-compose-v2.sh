#!/usr/bin/env bash
# Install the standalone docker compose v2 plugin on a host that has Docker
# installed via Ubuntu's docker.io package (which doesn't ship the v2 plugin).
#
# Run as root:
#   bash infra/scripts/install-docker-compose-v2.sh
#
# Idempotent. Verifies install with `docker compose version` at the end.

set -euo pipefail

VERSION="v2.29.7"

ARCH_RAW=$(uname -m)
case "$ARCH_RAW" in
    x86_64)  ARCH=linux-x86_64 ;;
    aarch64) ARCH=linux-aarch64 ;;
    *) echo "Unsupported arch: $ARCH_RAW"; exit 1 ;;
esac

if [[ -d /usr/libexec/docker ]]; then
    PLUGIN_DIR="/usr/libexec/docker/cli-plugins"
else
    PLUGIN_DIR="/usr/local/lib/docker/cli-plugins"
fi

mkdir -p "$PLUGIN_DIR"

URL="https://github.com/docker/compose/releases/download/${VERSION}/docker-compose-${ARCH}"
echo "==> Downloading docker compose ${VERSION}"
echo "    from: $URL"
echo "    to:   $PLUGIN_DIR/docker-compose"
curl -fL --retry 3 -o "$PLUGIN_DIR/docker-compose" "$URL"
chmod +x "$PLUGIN_DIR/docker-compose"

echo
echo "==> Verifying"
docker compose version
