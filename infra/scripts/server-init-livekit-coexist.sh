#!/usr/bin/env bash
# Bootstrap variant for a VPS that ALREADY runs another workload (in our
# case, LiveKit + Caddy + a native Redis). Designed to be safe to run on a
# live box: it does not apt-upgrade, does not install nginx, does not touch
# Caddy, does not reconfigure UFW.
#
# Usage (as a sudo-capable user on the target VPS):
#   bash infra/scripts/server-init-livekit-coexist.sh
#
# Idempotent — safe to re-run.

set -euo pipefail

if [[ $EUID -eq 0 ]]; then
    echo "WARN: running as root. Recommended: a sudo-capable non-root user."
fi

echo "==> sanity check: docker present"
if ! command -v docker >/dev/null 2>&1; then
    echo "Docker not found. On this server it should already be installed for"
    echo "the existing workload. Aborting to avoid surprising LiveKit."
    exit 1
fi
docker info >/dev/null 2>&1 || {
    echo "Docker daemon unreachable. Check 'sudo systemctl status docker'."
    exit 1
}

if ! id -nG "$USER" 2>/dev/null | grep -qw docker; then
    echo "==> adding $USER to docker group (re-login required after this script)"
    sudo usermod -aG docker "$USER"
fi

echo "==> sanity check: Caddy present (we'll proxy academy through it later)"
if command -v caddy >/dev/null 2>&1; then
    caddy version || true
else
    echo "WARN: caddy binary not in PATH. If LiveKit uses caddy via systemd"
    echo "      that's fine — we'll only edit its config later, not install."
fi

echo "==> sanity check: UFW already allows 80/443 (LiveKit needs them, so does academy)"
sudo ufw status verbose | grep -E '(^80/tcp|^443/tcp)' || {
    echo "UFW doesn't show 80/tcp or 443/tcp ALLOW. That's unexpected — the"
    echo "earlier diagnostic showed them open. Re-run 'sudo ufw status verbose'"
    echo "to confirm. Aborting."
    exit 1
}

echo "==> create /srv/academy directory tree"
sudo mkdir -p /srv/academy/{prod,staging,backups}
sudo chown -R "$USER":"$USER" /srv/academy

echo "==> clone repo (or update if already present)"
if [[ ! -d /srv/academy/repo/.git ]]; then
    git clone https://github.com/nshinde446/academy-platform.git /srv/academy/repo
else
    git -C /srv/academy/repo fetch --depth=1 origin master
    git -C /srv/academy/repo reset --hard origin/master
fi

echo
echo "==> done."
echo "Next steps:"
echo "  1. cp /srv/academy/repo/infra/compose/.env.prod.example     \\"
echo "        /srv/academy/repo/infra/compose/.env.prod"
echo "     cp /srv/academy/repo/infra/compose/.env.staging.example  \\"
echo "        /srv/academy/repo/infra/compose/.env.staging"
echo "     chmod 600 /srv/academy/repo/infra/compose/.env.*"
echo "  2. Generate secrets:  python3 -c 'import secrets; print(secrets.token_urlsafe(48))'"
echo "  3. Edit .env.prod and .env.staging to replace placeholders."
echo "  4. Set GitHub Actions secrets: VPS_HOST, VPS_USER, VPS_SSH_KEY (see DEPLOYMENT.md §3)."
echo "  5. Push to staging branch, watch the deploy."
echo
echo "Note: the backend containers will bind to 127.0.0.1:8000 (prod) and"
echo "127.0.0.1:8001 (staging) — NOT public. Until you have a domain and add"
echo "Caddy site blocks, reach them via SSH tunnel from your laptop:"
echo "  ssh -L 8000:127.0.0.1:8000 -L 8001:127.0.0.1:8001 root@116.203.116.141"
echo "Then open http://127.0.0.1:8000/health locally."
