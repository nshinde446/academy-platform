# UFW (firewall) configuration

The VPS runs UFW (Uncomplicated Firewall) and allows only what the platform needs.

## Required ruleset

```
22/tcp   ALLOW   IN    Anywhere    # ssh
80/tcp   ALLOW   IN    Anywhere    # http (nginx, also for certbot http-01)
443/tcp  ALLOW   IN    Anywhere    # https (nginx)
8099/tcp ALLOW   IN    Anywhere    # aidata-proxy — BioMax terminals push here
```

`8099` is the **only** other public port. It is served by `aidata-proxy`, which
answers exactly one path (`/AIData.aspx`) and forwards to the backend; the rest
of the API is never reachable over plain HTTP. The terminals speak plain HTTP
only and ack on case-sensitive headers that Caddy would rewrite, so they cannot
be served on 80/443 — see `docs/biomax-attendance.md`. The payload is just an ID
and a timestamp, and the backend still enforces its `dev_id` allowlist. If you
can pin the institute's public IP, narrow it: `sudo ufw allow from <ip> to any port 8099 proto tcp`.

Everything else (Postgres 5432, Redis 6379, app port 8000/8001, monitoring 9090/9093/3001/5555) MUST stay closed to the public — they're reachable only via Docker's bridge network or `127.0.0.1`.

## Apply manually

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw --force enable
sudo ufw status verbose
```

These commands are also run by `infra/scripts/server-init.sh` when bootstrapping a fresh VPS.

## Optional: lock SSH to your IP

If your home/office IP is stable:

```bash
sudo ufw delete allow 22/tcp
sudo ufw allow from <your-ip> to any port 22 proto tcp
```

Far better than fail2ban for keeping the SSH log noise down.

## Optional: admin endpoints over SSH tunnel

The monitoring stack (Prometheus :9090, Grafana :3001, Alertmanager :9093, Flower :5555) MUST stay on the loopback only. Access them via SSH local-forward:

```bash
ssh -L 3001:127.0.0.1:3001 -L 9090:127.0.0.1:9090 user@<server-ip>
```

Then browse http://127.0.0.1:3001 on your laptop. Never open these ports in UFW.
