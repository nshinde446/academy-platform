#!/usr/bin/env bash
# One-time bootstrap for a fresh Hetzner / Ubuntu VPS.
#
# Usage (as a sudo-capable user on the target VPS):
#   curl -fsSL https://raw.githubusercontent.com/nshinde446/academy-platform/master/infra/scripts/server-init.sh | bash
# or, if you have the repo cloned:
#   bash infra/scripts/server-init.sh
#
# Idempotent — safe to re-run.

set -euo pipefail

if [[ $EUID -eq 0 ]]; then
    echo "Run this as a regular user with sudo, not as root." >&2
    exit 1
fi

echo "==> apt update + upgrade"
sudo apt-get update -y
sudo DEBIAN_FRONTEND=noninteractive apt-get upgrade -y

echo "==> base packages"
sudo apt-get install -y --no-install-recommends \
    ca-certificates curl gnupg lsb-release \
    nginx certbot python3-certbot-nginx \
    ufw fail2ban unattended-upgrades \
    postgresql-client

echo "==> docker (skipped if already installed)"
if ! command -v docker >/dev/null 2>&1; then
    curl -fsSL https://get.docker.com | sudo sh
fi
sudo usermod -aG docker "$USER" || true

echo "==> 2GB swap (if missing)"
if ! sudo swapon --show | grep -q '/swapfile'; then
    sudo fallocate -l 2G /swapfile
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile
    if ! grep -q '/swapfile' /etc/fstab; then
        echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
    fi
fi

echo "==> firewall (UFW)"
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw --force enable

echo "==> unattended security updates"
echo 'APT::Periodic::Update-Package-Lists "1";'             | sudo tee /etc/apt/apt.conf.d/20auto-upgrades >/dev/null
echo 'APT::Periodic::Unattended-Upgrade "1";'              | sudo tee -a /etc/apt/apt.conf.d/20auto-upgrades >/dev/null
echo 'APT::Periodic::AutocleanInterval "7";'               | sudo tee -a /etc/apt/apt.conf.d/20auto-upgrades >/dev/null

echo "==> create /srv/academy directory tree"
sudo mkdir -p /srv/academy/{prod,staging,backups,nginx-snippets}
sudo chown -R "$USER":"$USER" /srv/academy

echo "==> install shared nginx snippets"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
sudo install -m 644 "$REPO_ROOT/infra/nginx/security-headers.conf"  /etc/nginx/snippets/security-headers.conf
sudo install -m 644 "$REPO_ROOT/infra/nginx/proxy-common.conf"      /etc/nginx/snippets/proxy-common.conf
sudo install -m 644 "$REPO_ROOT/infra/nginx/rate-limit.conf"        /etc/nginx/conf.d/rate-limit.conf
sudo install -m 644 "$REPO_ROOT/infra/nginx/logrotate.conf"         /etc/logrotate.d/nginx-academy

echo "==> install per-env nginx site configs (disabled until you set the real domain)"
sudo install -m 644 "$REPO_ROOT/infra/nginx/api-prod.conf"    /etc/nginx/sites-available/api-prod.conf
sudo install -m 644 "$REPO_ROOT/infra/nginx/api-staging.conf" /etc/nginx/sites-available/api-staging.conf
echo "   Edit /etc/nginx/sites-available/api-*.conf to set server_name, then symlink to sites-enabled/."

echo "==> done. Log out + back in once so the docker group takes effect."
echo "    Next: place .env.prod and .env.staging under /srv/academy/{prod,staging}/, then deploy."
