"""BioMax AIData — LOCAL capture proxy (run on the coaching-center laptop).

Purpose
-------
Learn the *server -> device command vocabulary* (the ``cmd_code`` + payload the
BioMax R6 obeys when a user is created / edited / deleted) by watching BioMax's
own SmartOffice do it. This is the "oracle" method that cracked the ingest ack;
see docs/biomax-provisioning-implementation.md §0.

The VPS proxy (``aidata_proxy.py`` in this folder) can already relay to the
*remote* institute SmartOffice, but that path is roundabout and logs only to
Docker. Now that SmartOffice + MSSQL run on the coaching laptop, capture is a
same-LAN, no-cloud, ~20-minute job — this is that standalone tool.

How it works
------------
The device is pointed at THIS laptop instead of the VPS. Every request the
device sends is forwarded verbatim to local SmartOffice, and SmartOffice's
response is echoed back to the device byte-for-byte (original header casing
preserved — the firmware is case-sensitive about ``response_code`` etc.). Both
legs are written to a capture file. When an admin adds/edits/deletes a user in
SmartOffice's UI, SmartOffice answers the device's next poll with a command in
the response headers/body — and we capture it.

This proxy NEVER synthesises its own ack in capture mode: the whole point is to
observe SmartOffice's real response, command and all.

Run it (Windows, from this folder)
-----------------------------------
    python local_capture.py

Then on the R6 device's server/push setting, set the server IP to THIS laptop's
LAN IP and the port to this proxy's port (printed on startup); keep the path as
/AIData.aspx. Allow the port through Windows Firewall when prompted (or add an
inbound rule). Watch the console, add a user in SmartOffice, and read the
``*** COMMAND ***`` line. When done, point the device back at the VPS.

Biometric discipline (unchanged, non-negotiable)
------------------------------------------------
``face`` / ``photo`` / ``logPhoto`` / ``fps`` / ``template`` / ``image`` blobs
are PII and are NEVER written to the capture file — only the key name and byte
length are recorded. Capturing a command is not an excuse to log a face.

This is a temporary, on-site diagnostic tool. It is not part of the deployed
stack and must never run on a server.
"""

from __future__ import annotations

import datetime
import json
import os
import socket
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# --- config (override via env if needed) ------------------------------------
# Where local SmartOffice listens. It receives the device's POST at /AIData.aspx.
SMARTOFFICE = os.environ.get("SMARTOFFICE_URL", "http://127.0.0.1:8080/AIData.aspx")
# The port the DEVICE pushes to on this laptop (set this on the device).
PORT = int(os.environ.get("CAPTURE_PORT", "8090"))
TIMEOUT = float(os.environ.get("CAPTURE_TIMEOUT", "10"))
# Persistent capture file, written next to this script.
CAPTURE_FILE = os.environ.get(
    "CAPTURE_FILE", os.path.join(os.path.dirname(os.path.abspath(__file__)), "aidata_capture.log")
)
PATH = "/AIData.aspx"

# Framing headers we recompute rather than echo (urllib de-chunks the body).
_SKIP_ECHO = {"content-length", "transfer-encoding", "connection", "keep-alive"}
# Never written to the capture file — biometric PII. Key + byte length only.
_BIOMETRIC_KEYS = ("face", "photo", "logPhoto", "fps", "template", "image")


def _redact(body: bytes) -> object:
    """JSON-safe view of a body with biometric blobs stripped to a length
    marker. Non-JSON bodies collapse to a length marker too, so the capture
    file is always safe to read and never holds a face template."""
    if not body:
        return ""
    try:
        data = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        return f"<non-json {len(body)} bytes>"

    def scrub(obj: object) -> object:
        if isinstance(obj, dict):
            return {
                k: (f"<redacted {len(v)} bytes>" if k in _BIOMETRIC_KEYS and isinstance(v, str)
                    else scrub(v))
                for k, v in obj.items()
            }
        if isinstance(obj, list):
            return [scrub(v) for v in obj]
        return obj

    return scrub(data)


def _write_capture(entry: dict) -> None:
    """Append one JSON line to the capture file (biometric-redacted upstream)."""
    entry["ts"] = datetime.datetime.now().isoformat(timespec="seconds")
    line = json.dumps(entry, ensure_ascii=False)
    with open(CAPTURE_FILE, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def _hdr(headers: list[tuple[str, str]], name: str) -> str:
    """Case-insensitive header lookup over an original-case header list."""
    for k, v in headers:
        if k.lower() == name.lower():
            return v
    return ""


def _lan_ip() -> str:
    """Best-effort LAN IP of this laptop, for the on-screen instructions."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))  # no packet sent; just picks the outbound iface
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "<this-laptop-LAN-IP>"


class Handler(BaseHTTPRequestHandler):
    # The device speaks HTTP/1.0 and opens a fresh connection per record.
    protocol_version = "HTTP/1.1"
    server_version = "aidata-local-capture"

    def _refuse(self, status: int = 502) -> None:
        """No ack headers -> the device keeps the record and retries. Used when
        SmartOffice is unreachable, so a capture-session hiccup never makes the
        device discard a real punch."""
        self.send_response(status)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _handle(self, method: str) -> None:
        if self.path.split("?", 1)[0] != PATH:
            self._refuse(404)
            return

        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else b""
        req_headers = list(self.headers.items())  # original case, as received

        # Forward verbatim to local SmartOffice, minus Host (urllib sets it).
        fwd = {k: v for k, v in req_headers if k.lower() != "host"}
        try:
            req = urllib.request.Request(SMARTOFFICE, data=body, method=method, headers=fwd)
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                status = resp.status
                resp_headers = list(resp.headers.items())  # SmartOffice's exact casing
                resp_body = resp.read()
        except urllib.error.HTTPError as exc:
            status = exc.code
            resp_headers = list(exc.headers.items()) if exc.headers else []
            resp_body = exc.read() or b""
        except Exception as exc:  # SmartOffice down / refused / timeout
            print(f"  !! SmartOffice unreachable ({type(exc).__name__}) — refusing this poll")
            self._refuse()
            return

        # --- record + surface the exchange -----------------------------------
        req_code = _hdr(req_headers, "request_code") or "?"
        cmd_code = _hdr(resp_headers, "cmd_code")
        trans_id = _hdr(resp_headers, "trans_id")
        resp_code = _hdr(resp_headers, "response_code")
        stamp = datetime.datetime.now().strftime("%H:%M:%S")

        _write_capture({
            "leg": "device->smartoffice",
            "method": method, "path": self.path,
            "request_code": req_code,
            "headers": req_headers, "body": _redact(body),
        })
        _write_capture({
            "leg": "smartoffice->device",
            "status": status,
            "response_code": resp_code, "cmd_code": cmd_code, "trans_id": trans_id,
            "headers": resp_headers, "body": _redact(resp_body),
        })

        if cmd_code or trans_id:
            # This is the gold: SmartOffice is handing the device a command.
            print(f"[{stamp}] {req_code:<20} -> *** COMMAND *** "
                  f"cmd_code={cmd_code!r} trans_id={trans_id!r}  "
                  f"(full payload in {os.path.basename(CAPTURE_FILE)})")
        else:
            print(f"[{stamp}] {req_code:<20} -> ok (response_code={resp_code!r}, no command)")

        # --- echo SmartOffice's response to the device byte-for-byte ---------
        self.send_response(status)
        for k, v in resp_headers:
            if k.lower() in _SKIP_ECHO:
                continue
            self.send_header(k, v)  # preserves SmartOffice's exact header casing
        self.send_header("Content-Length", str(len(resp_body)))
        self.end_headers()
        if resp_body:
            self.wfile.write(resp_body)

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        self._handle("POST")

    def do_GET(self) -> None:  # noqa: N802 - some firmwares probe with GET
        self._handle("GET")

    def log_message(self, *args) -> None:
        """Silence the default per-request line; we print our own summary."""


def main() -> None:
    ip = _lan_ip()
    print("=" * 68)
    print(" BioMax AIData — LOCAL capture proxy")
    print("=" * 68)
    print(f" Relaying to SmartOffice : {SMARTOFFICE}")
    print(f" Capture file            : {CAPTURE_FILE}")
    print()
    print(" On the R6 device server/push setting, point it at THIS laptop:")
    print(f"     Server IP  : {ip}")
    print(f"     Port       : {PORT}")
    print(f"     Path       : {PATH}")
    print(" (Allow the port through Windows Firewall if prompted.)")
    print()
    print(" Then add a user in SmartOffice's UI and watch for a")
    print(" '*** COMMAND ***' line below. Ctrl-C to stop.")
    print("=" * 68)
    try:
        ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
    except KeyboardInterrupt:
        print("\nstopped.")


if __name__ == "__main__":
    main()
