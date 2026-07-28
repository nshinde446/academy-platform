"""BioMax AIData protocol proxy.

The R6 terminal acks on HTTP *response headers* (``response_code: OK`` with
empty ``cmd_code``/``trans_id`` — see docs/biomax-attendance.md) and is
**case-sensitive** about them. Caddy is Go-based and canonicalises response
header keys (``response_code`` -> ``Response_code``), which the device rejects:
it then re-uploads the same record every few seconds forever and never reports
live scans. Go gives us no way to emit a non-canonical key, so the device cannot
be served through Caddy.

This tiny stdlib-only proxy sits on its own port, speaks the device's dialect
byte-for-byte, and forwards the record to the app for real ingest. The device
points straight at it, so nothing rewrites the headers.

Why a separate process instead of exposing the backend port directly: this
serves **only** ``/AIData.aspx``, so the rest of the API is never reachable over
plain HTTP.

Ack discipline (this is the part that loses data if you get it wrong): we ack
**only** once the app confirms it stored the punch. The device deletes its only
copy the moment it is acked, so acking a punch we could not store — e.g. during
a deploy — loses it permanently. On any upstream failure we return 500 and no
ack headers, and the device retains the record and retries.

RELAY / CAPTURE MODE (Phase 2 provisioning groundwork — normally OFF)
--------------------------------------------------------------------
Set ``AIDATA_RELAY_UPSTREAM`` to BioMax's own SmartOffice receiver
(e.g. ``http://103.171.50.109:8080/AIData.aspx``) to turn this into a transparent
relay: the device's POST is forwarded verbatim to SmartOffice and SmartOffice's
response — status, headers (original casing preserved), and body — is returned to
the device **unchanged**. Both directions are logged so we can capture the
server->device command vocabulary (the ``cmd_code`` values SmartOffice emits when
an admin adds/edits/deletes a user in its UI). This is the "oracle" method that
cracked the ack; see docs/biomax-provisioning-implementation.md §0.

Relay mode NEVER synthesises our own ack — the whole point is to observe
SmartOffice's real response, including any command it issues. It is a temporary,
explicitly-flagged mode: leave ``AIDATA_RELAY_UPSTREAM`` unset in production.

Biometric discipline is unchanged in every mode: ``face`` / ``photo`` /
``logPhoto`` / ``fps`` blobs are PII and are **never** written to the capture log
— only their key name and byte length are recorded.
"""

from __future__ import annotations

import json
import logging
import os
import ssl
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

UPSTREAM = os.environ.get("AIDATA_UPSTREAM", "http://backend:8000/AIData.aspx")
# When set, the proxy relays to this URL (SmartOffice) and echoes its response
# verbatim instead of ingesting + synthesising our own ack. Off by default.
RELAY_UPSTREAM = os.environ.get("AIDATA_RELAY_UPSTREAM") or None
PORT = int(os.environ.get("AIDATA_PORT", "8099"))
TIMEOUT = float(os.environ.get("AIDATA_TIMEOUT", "10"))
PATH = "/AIData.aspx"

# --- HTTPS (Domain Name mode) -----------------------------------------------
# When the device is configured with a hostname + HTTPS, it connects here over
# TLS. We terminate TLS in THIS process (not Caddy) because Caddy canonicalises
# the case-sensitive ack headers and breaks the device (the whole reason this
# proxy exists). Caddy still *issues/renews* the Let's Encrypt cert for the
# hostname; we just read its files. Unset -> no TLS listener (plain HTTP only).
TLS_PORT = int(os.environ.get("AIDATA_TLS_PORT", "0") or "0")
TLS_CERT = os.environ.get("AIDATA_TLS_CERT") or None  # fullchain .crt (PEM)
TLS_KEY = os.environ.get("AIDATA_TLS_KEY") or None     # private .key (PEM)

# --- Liveness heartbeat ------------------------------------------------------
# The device polls every ~20s even when nobody punches, so "no contact" is a far
# better outage signal than "no punches". On every device request we bump the
# mtime of this file; the watchdog (attendance_watchdog.py) alerts when it goes
# stale. Unset -> no heartbeat written.
HEARTBEAT_FILE = os.environ.get("AIDATA_HEARTBEAT_FILE") or None

# Headers the device sends that the app needs to identify + classify the record.
# Everything else (including any base64 face/photo payload) is passed through in
# the body untouched but never logged.
FORWARD_HEADERS = ("dev_id", "dev_model", "request_code", "trans_id", "Content-Type")

# Hop-by-hop / length headers we must not blindly echo back from the relayed
# response: urllib de-chunks and gives us the decoded body, so we recompute
# Content-Length and drop framing headers. Everything else is echoed as-is.
_SKIP_ECHO = {"content-length", "transfer-encoding", "connection", "keep-alive"}

# Never log these payload fields — biometric PII. We record the key + byte size
# only, so a capture never contains a face template or photo.
_BIOMETRIC_KEYS = ("face", "photo", "logPhoto", "fps", "template", "image")

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s aidata-proxy %(message)s"
)
log = logging.getLogger("aidata-proxy")


def _redact(body: bytes) -> object:
    """Return a JSON-safe view of a body with biometric blobs stripped to
    ``"<redacted N bytes>"``. Non-JSON bodies collapse to a length marker so a
    capture is always safe to read and never holds a face template."""
    if not body:
        return ""
    try:
        data = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        return f"<non-json {len(body)} bytes>"

    def scrub(obj: object) -> object:
        if isinstance(obj, dict):
            out = {}
            for k, v in obj.items():
                if k in _BIOMETRIC_KEYS and isinstance(v, str):
                    out[k] = f"<redacted {len(v)} bytes>"
                else:
                    out[k] = scrub(v)
            return out
        if isinstance(obj, list):
            return [scrub(v) for v in obj]
        return obj

    return scrub(data)


def _capture(direction: str, status: object, headers: object, body: bytes) -> None:
    """Log one leg of a relayed exchange as a single JSON line, biometric-safe.
    ``direction`` is e.g. ``device->smartoffice`` or ``smartoffice->device``."""
    entry = {
        "capture": direction,
        "status": status,
        "headers": headers,          # original-case list of [key, value]
        "body": _redact(body),
    }
    log.info("CAPTURE %s", json.dumps(entry, ensure_ascii=False))


def _touch_heartbeat() -> None:
    """Bump the heartbeat file's mtime to mark 'the device just contacted us'.
    Best-effort: a heartbeat failure must never affect acking a punch."""
    if not HEARTBEAT_FILE:
        return
    try:
        now = time.time()
        with open(HEARTBEAT_FILE, "a"):
            pass
        os.utime(HEARTBEAT_FILE, (now, now))
    except OSError as exc:
        log.warning("heartbeat write failed: %s", exc)


class _CertReloader:
    """Holds an SSLContext and reloads the cert when its file changes on disk,
    so Caddy's automatic renewals are picked up without restarting the proxy.
    Wired in as the context's ``sni_callback`` — checked once per TLS handshake,
    which is cheap and needs no timer thread."""

    def __init__(self, certfile: str, keyfile: str) -> None:
        self._certfile = certfile
        self._keyfile = keyfile
        self._lock = threading.Lock()
        self._mtime = 0.0
        self._ctx = self._build()

    def _build(self) -> ssl.SSLContext:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(self._certfile, self._keyfile)
        # Some BioMax firmwares only negotiate older TLS; allow down to 1.2
        # (still refuse SSLv3/TLS1.0/1.1). Raise if you confirm the device does
        # 1.3 cleanly.
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        self._mtime = os.path.getmtime(self._certfile)
        return ctx

    def _maybe_reload(self) -> None:
        try:
            if os.path.getmtime(self._certfile) != self._mtime:
                with self._lock:
                    if os.path.getmtime(self._certfile) != self._mtime:
                        self._ctx = self._build()
                        log.info("TLS cert reloaded from %s", self._certfile)
        except OSError as exc:
            log.warning("TLS cert reload check failed: %s", exc)

    def sni_callback(self, sslsock: ssl.SSLObject, server_name: str | None,
                     ctx: ssl.SSLContext) -> None:
        self._maybe_reload()
        sslsock.context = self._ctx

    @property
    def context(self) -> ssl.SSLContext:
        ctx = self._ctx
        ctx.sni_callback = self.sni_callback
        return ctx


class Handler(BaseHTTPRequestHandler):
    # The device speaks HTTP/1.0 and opens a fresh connection per record.
    protocol_version = "HTTP/1.1"
    server_version = "aidata-proxy"

    def _ack(self) -> None:
        """The exact response the R6 accepts. Keys must stay lowercase, and
        cmd_code/trans_id must stay EMPTY — a non-empty value means "server has
        a command for you" and the device re-syncs instead of clearing its log.
        """
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("response_code", "OK")
        self.send_header("cmd_code", "")
        self.send_header("trans_id", "")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _refuse(self, status: int = 500) -> None:
        """No ack headers -> the device keeps the record and retries later."""
        self.send_response(status)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _relay(self, method: str, body: bytes) -> None:
        """Transparent relay to SmartOffice: forward the device's request as-is
        and echo SmartOffice's response verbatim (status + headers + body),
        capturing both legs. Used only in relay/capture mode to learn the
        server->device command vocabulary; never synthesises our own ack.

        On any failure to reach SmartOffice we ``_refuse()`` — same fail-safe as
        ingest, so the device keeps the record rather than treating a proxy error
        as a delivery.
        """
        # Forward every header the device sent, verbatim, except Host (urllib
        # sets it from the relay URL). Faithful forwarding matters — SmartOffice
        # keys off User-Agent, request_code, dev_id, etc.
        fwd = {k: v for k, v in self.headers.items() if k.lower() != "host"}
        _capture("device->smartoffice", f"{method} {self.path}",
                 list(self.headers.items()), body)
        try:
            req = urllib.request.Request(
                RELAY_UPSTREAM, data=body, method=method, headers=fwd
            )
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                status = resp.status
                # resp.headers preserves SmartOffice's ORIGINAL header casing,
                # which is exactly what the case-sensitive firmware needs.
                resp_headers = list(resp.headers.items())
                resp_body = resp.read()
        except urllib.error.HTTPError as exc:
            # A 4xx/5xx from SmartOffice is still a real, capturable response —
            # echo it so we see what the device would have received.
            status = exc.code
            resp_headers = list(exc.headers.items()) if exc.headers else []
            resp_body = exc.read() or b""
        except Exception as exc:  # network refused, timeout, host down...
            log.warning("relay upstream unreachable (%s) — refusing", type(exc).__name__)
            self._refuse()
            return

        _capture("smartoffice->device", status, resp_headers, resp_body)

        # Echo SmartOffice's response to the device byte-for-byte (minus framing
        # headers we must recompute). send_header preserves whatever case we
        # pass, so the device sees SmartOffice's exact header casing.
        self.send_response(status)
        for k, v in resp_headers:
            if k.lower() in _SKIP_ECHO:
                continue
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(resp_body)))
        self.end_headers()
        if resp_body:
            self.wfile.write(resp_body)

    def _handle(self, method: str) -> None:
        if self.path.split("?", 1)[0] != PATH:
            self._refuse(404)
            return

        # A request on the real path is the device (or its probe) reaching us —
        # record liveness before anything else can fail.
        _touch_heartbeat()

        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else b""

        # Relay/capture mode: hand the whole exchange to SmartOffice verbatim.
        if RELAY_UPSTREAM:
            self._relay(method, body)
            return

        request_code = self.headers.get("request_code") or "?"
        headers = {
            h: self.headers.get(h) for h in FORWARD_HEADERS if self.headers.get(h)
        }
        headers.setdefault("Content-Type", "application/json")

        try:
            req = urllib.request.Request(
                UPSTREAM, data=body, method=method, headers=headers
            )
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                ok = 200 <= resp.status < 300
                resp.read()
        except urllib.error.HTTPError as exc:
            # The app deliberately 500s when it could not store the punch.
            ok = False
            log.warning("upstream %s for %s — not acking", exc.code, request_code)
        except Exception as exc:  # network refused, timeout, app restarting...
            ok = False
            log.warning("upstream unreachable (%s) — not acking", type(exc).__name__)

        if ok:
            self._ack()
        else:
            self._refuse()

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        self._handle("POST")

    def do_GET(self) -> None:  # noqa: N802 - some firmwares probe with GET
        self._handle("GET")

    def log_message(self, *args) -> None:
        """Silence the default per-request line; it would echo the request path
        and add nothing. Real events are logged explicitly above."""


def _serve(server: ThreadingHTTPServer, label: str) -> None:
    log.info("listening on %s (%s) -> %s", server.server_address, label,
             RELAY_UPSTREAM or UPSTREAM)
    server.serve_forever()


def main() -> None:
    if RELAY_UPSTREAM:
        log.warning(
            "RELAY/CAPTURE MODE — forwarding to %s and echoing its response "
            "verbatim (biometric blobs redacted in the capture log). This must "
            "NOT run in production.", RELAY_UPSTREAM
        )
    if HEARTBEAT_FILE:
        _touch_heartbeat()  # seed it so the watchdog doesn't false-alarm on boot
        log.info("heartbeat -> %s", HEARTBEAT_FILE)

    servers: list[tuple[ThreadingHTTPServer, str]] = [
        (ThreadingHTTPServer(("0.0.0.0", PORT), Handler), "plain HTTP")
    ]

    # Optional TLS listener for the device in Domain Name + HTTPS mode.
    if TLS_PORT and TLS_CERT and TLS_KEY:
        try:
            reloader = _CertReloader(TLS_CERT, TLS_KEY)
            tls_server = ThreadingHTTPServer(("0.0.0.0", TLS_PORT), Handler)
            tls_server.socket = reloader.context.wrap_socket(
                tls_server.socket, server_side=True
            )
            servers.append((tls_server, "HTTPS/TLS"))
            log.info("TLS enabled on :%d using %s", TLS_PORT, TLS_CERT)
        except (OSError, ssl.SSLError) as exc:
            # Never let a cert problem take down plain-HTTP ingest — that path is
            # the proven fallback. Log loudly and carry on HTTP-only.
            log.error("TLS listener NOT started (%s) — continuing HTTP-only", exc)
    elif TLS_PORT:
        log.warning("AIDATA_TLS_PORT set but cert/key missing — TLS disabled")

    # Run every listener but the last in its own daemon thread; serve the last
    # on the main thread so the process blocks here.
    for server, label in servers[:-1]:
        threading.Thread(target=_serve, args=(server, label), daemon=True).start()
    _serve(*servers[-1])


if __name__ == "__main__":
    main()
