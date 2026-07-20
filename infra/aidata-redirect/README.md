# aidata-redirect — temporary port-80 shim for the BioMax terminal

> **This is a stopgap. Prefer fixing the device.** Set the terminal's push port
> to `8099` so it reaches `aidata-proxy` directly, then delete this unit
> entirely (see "Removing it" below).

## Why it exists

The BioMax R6 acks on a case-sensitive `response_code` response header. Caddy is
Go-based and canonicalises header keys (`response_code` → `Response_code`), which
the device rejects — it then re-uploads the same record every few seconds forever
and never reports live scans. So the terminal **cannot** be served through Caddy;
it has to reach `aidata-proxy` (port 8099), which speaks its dialect verbatim.
Background: `docs/biomax-attendance.md`.

Normally you'd just point the device at `8099`. On this unit the push-port
setting would not persist across a reboot, so as a fallback we redirect its
port-80 traffic to the proxy at the packet level.

## Known weakness

The rule matches on the device's **public IP**, so:

- **If the ISP changes that IP, attendance stops silently.** Nothing errors —
  the device just goes back to talking to Caddy and looping.
- It only covers this one source address; a second site needs another rule.

Reboots are handled (the unit re-applies on boot), but the IP fragility is
exactly why this should be replaced by the device-side port change.

## Install

```bash
sudo cp aidata-redirect.default /etc/default/aidata-redirect
sudo cp aidata-redirect.service /etc/systemd/system/
sudo nano /etc/default/aidata-redirect     # set DEVICE_IP
sudo systemctl daemon-reload
sudo systemctl enable --now aidata-redirect
```

Verify the rule is live:

```bash
sudo iptables -t nat -L PREROUTING -n | grep REDIRECT
```

`ExecStart` is idempotent (`-C` tests before adding), so restarts never stack
duplicate rules.

## When the public IP changes

```bash
# find the address the terminal is pushing from
sudo tcpdump -i eth0 -nn "tcp[tcpflags] & tcp-syn != 0 and dst port 80"

sudo nano /etc/default/aidata-redirect     # update DEVICE_IP
sudo systemctl restart aidata-redirect
```

Confirm punches resume:

```bash
docker logs --since 2m academy-prod-backend-1 2>&1 | grep -i "AIData punch"
```

Healthy output shows **distinct** timestamps. The *same* timestamp repeating
every few seconds means the device is still being served by Caddy — the
redirect is not matching, so re-check `DEVICE_IP`.

## Removing it (the goal)

Once the terminal's push port is set to `8099` and punches are confirmed
arriving:

```bash
sudo systemctl disable --now aidata-redirect
sudo rm /etc/systemd/system/aidata-redirect.service /etc/default/aidata-redirect
sudo systemctl daemon-reload
```

`ExecStop` drops the iptables rule, so nothing is left behind.
