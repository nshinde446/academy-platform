# BioMax attendance — HTTPS ingest + liveness watchdog

Hardens the device→VPS direct-push path for the case where **the device lives
at the institute and the coaching laptop is unreliable (often off)**. Two
additions on top of the working plain-HTTP ingest (`docs/biomax-attendance.md`):

1. **HTTPS ingest** — the device connects over TLS using a stable **hostname**
   (`attend.eduworld-livekit.duckdns.org`), so attendance is encrypted over the
   public internet and the device never needs re-pointing if the VPS IP changes.
2. **Liveness watchdog** — alerts you (Telegram/webhook) within minutes when
   punches stop, so a dead device / dropped internet / crashed proxy is never a
   silent multi-day gap.

Neither touches the deliberately-off Celery beat or the stubbed notification
delivery — both are self-contained in the `aidata-proxy` infra.

---

## Why TLS terminates in the proxy, not Caddy

Caddy is Go-based and **canonicalises response header keys**
(`response_code` → `Response_code`). The R6 firmware is case-sensitive about the
ack headers and rejects the canonicalised form — it then re-uploads forever and
never goes live. So the device can never be served *through* Caddy.

Caddy still does what it's good at — **issuing and auto-renewing** the Let's
Encrypt cert for the hostname. The proxy simply **reads Caddy's cert files** and
terminates TLS itself (`_CertReloader` hot-reloads on renewal via the SNI
callback), preserving exact header casing. Device traffic never passes through
Caddy.

```
device --TLS :8443--> aidata-proxy (terminates TLS, exact headers) --> backend:8000
Caddy :443 attend.*  -> only issues/renews the cert; no device traffic
```

Ports: **8099** plain HTTP (proven fallback), **8443** HTTPS. The device dials
*outbound* to whichever is configured, so a non-443 port is fine (outbound is
not firewalled the way inbound is).

---

## One-time deploy (on the VPS)

```bash
# 1. Issue the cert: add a block to /etc/caddy/Caddyfile so Caddy obtains it.
#    It does nothing else — no device traffic goes through Caddy.
cat >> /etc/caddy/Caddyfile <<'EOF'

# Cert issuance only for the BioMax HTTPS ingest (served by aidata-proxy:8443).
attend.eduworld-livekit.duckdns.org {
    respond "aidata-proxy" 200
}
EOF
systemctl reload caddy
# Wait for issuance, then confirm the cert files exist:
ls /var/lib/caddy/.local/share/caddy/certificates/*/attend.eduworld-livekit.duckdns.org/

# 2. Heartbeat dir shared between the proxy container and the host watchdog.
mkdir -p /srv/academy/aidata

# 3. Pull the new proxy + compose, recreate ONLY aidata-proxy.
git -C /srv/academy/repo pull
docker compose -p academy-prod -f /srv/academy/repo/infra/compose/docker-compose.prod.yml \
  up -d --no-deps --force-recreate aidata-proxy
docker logs --tail 5 academy-prod-aidata-proxy-1   # expect "TLS enabled on :8443"

# 4. Install the watchdog cron (every 3 min). Alert channel via env (see below).
cat > /etc/cron.d/attendance-watchdog <<'EOF'
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
*/3 * * * * root /usr/bin/python3 /srv/academy/repo/infra/aidata-proxy/attendance_watchdog.py >> /var/log/attendance_watchdog.log 2>&1
EOF
```

Until `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID` (or `ALERT_WEBHOOK_URL`) are set,
the watchdog **logs only** — safe to run, just no phone alert yet.

### Verify

```bash
# TLS handshake + ack from outside (once the device isn't the only client):
curl -sv https://attend.eduworld-livekit.duckdns.org:8443/AIData.aspx \
  -H 'dev_id: AMDB26013800122' -X POST --data '{}' 2>&1 | grep -Ei 'SSL|response_code'
# Heartbeat bumps on every device contact:
stat -c '%y' /srv/academy/aidata/heartbeat
# Watchdog dry-run:
AIDATA_HEARTBEAT_FILE=/srv/academy/aidata/heartbeat \
  python3 /srv/academy/repo/infra/aidata-proxy/attendance_watchdog.py
```

---

## Device settings (at the institute)

**Primary — HTTPS + Domain Name:**

| Setting | Value |
|---|---|
| Comm/ADMS → Enable Domain Name | **On** |
| Push Server IP / Server address | `attend.eduworld-livekit.duckdns.org` |
| Push Server Port | `8443` |
| Https | **On** |
| Real Time Req | **On** |
| DNS (Ethernet/Wi-Fi) | `8.8.8.8` (so the hostname resolves) |

**Fallback — proven plain HTTP** (use if the firmware's TLS misbehaves):

| Setting | Value |
|---|---|
| Enable Domain Name | On (`attend.eduworld-livekit.duckdns.org`) or Off (IP `116.203.116.141`) |
| Push Server Port | `8099` |
| Https | **Off** |

Always confirm a real punch lands (`docker logs -f academy-prod-aidata-proxy-1`,
look for `inserted=1`) before leaving the site.

---

## Alert channel (pick one)

- **Telegram (recommended — free, instant to phone):** create a bot via
  @BotFather, get the token; message the bot once, then read your chat id from
  `https://api.telegram.org/bot<token>/getUpdates`. Put both in the cron file.
- **Webhook:** set `ALERT_WEBHOOK_URL` to any endpoint that accepts a JSON POST.

Tunables (env, all optional): `WATCHDOG_STALE_SECONDS` (default 300),
`WATCHDOG_WORK_START_HOUR`/`WATCHDOG_WORK_END_HOUR` (default 7–22 IST),
`WATCHDOG_REPEAT_SECONDS` (re-remind cadence, default 2h), `WATCHDOG_TZ`.

---

## Failure modes covered

| Failure | What happens |
|---|---|
| Internet blip at institute | Device buffers punches, re-sends on reconnect; watchdog may briefly flag DOWN then RECOVERED |
| Device unplugged / crashed | No heartbeat → DOWN alert within `STALE_SECONDS` (in working hours) |
| Proxy container down | No heartbeat → DOWN alert; plain-HTTP ingest and TLS both restart via `restart: unless-stopped` |
| Cert renewal | `_CertReloader` picks up Caddy's renewed cert on the next handshake — no restart |
| TLS cert missing/broken at boot | Proxy logs the error and **continues HTTP-only** — ingest never goes down over a cert problem |
| VPS IP changes | Update DuckDNS once; the device (on the hostname) needs no change |
