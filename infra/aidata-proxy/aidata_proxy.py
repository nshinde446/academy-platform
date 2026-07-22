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


def main() -> None:
    if RELAY_UPSTREAM:
        log.warning(
            "RELAY/CAPTURE MODE — forwarding to %s and echoing its response "
            "verbatim (biometric blobs redacted in the capture log). This must "
            "NOT run in production.", RELAY_UPSTREAM
        )
    log.info("listening on 0.0.0.0:%d -> %s", PORT, RELAY_UPSTREAM or UPSTREAM)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
