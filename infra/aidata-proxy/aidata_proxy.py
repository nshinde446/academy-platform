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
"""

from __future__ import annotations

import logging
import os
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

UPSTREAM = os.environ.get("AIDATA_UPSTREAM", "http://backend:8000/AIData.aspx")
PORT = int(os.environ.get("AIDATA_PORT", "8099"))
TIMEOUT = float(os.environ.get("AIDATA_TIMEOUT", "10"))
PATH = "/AIData.aspx"

# Headers the device sends that the app needs to identify + classify the record.
# Everything else (including any base64 face/photo payload) is passed through in
# the body untouched but never logged.
FORWARD_HEADERS = ("dev_id", "dev_model", "request_code", "trans_id", "Content-Type")

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s aidata-proxy %(message)s"
)
log = logging.getLogger("aidata-proxy")


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

    def _handle(self, method: str) -> None:
        if self.path.split("?", 1)[0] != PATH:
            self._refuse(404)
            return

        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else b""
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
    log.info("listening on 0.0.0.0:%d -> %s", PORT, UPSTREAM)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
