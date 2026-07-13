#!/usr/bin/env python3
"""SmartOffice -> Academy attendance on-prem agent.

Runs on the institute's Windows PC *next to* the SmartOffice install. It reads
new biometric punch rows from SmartOffice's SQL Server table (over localhost,
with a read-only login) and pushes them to the Academy backend's authenticated
ingest endpoint (``POST /api/v1/attendance/smartoffice/ingest``).

Why an agent instead of the cloud connecting to SQL directly:
- It only makes OUTBOUND HTTPS calls, so it works behind the institute's
  router/NAT with no port-forwarding and no exposing SQL Server to the internet.
- It keeps a local watermark, so a dropped internet connection just means the
  next cycle re-sends; nothing is lost. The server dedups, so re-sends are safe.

The exact SQL table/view name and column names are all config values
(``agent.ini``) — fill them in once the provider hands over the schema. Prefer a
monotonic ``id_column`` (IDENTITY / rowversion) for exact incremental reads; if
there isn't one, set ``timestamp_column`` and the agent watermarks on time
(with the server's 5s dedup covering the small overlap).
"""

from __future__ import annotations

import argparse
import configparser
import json
import logging
import os
import sys
import time
from datetime import datetime

try:
    import pyodbc
except ImportError:  # surfaced with a clear message at runtime
    pyodbc = None

import requests

log = logging.getLogger("smartoffice-agent")

# Field names the backend expects in each pushed row (SmartOffice's own casing).
F_EMP = "EmployeeCode"
F_LOG = "LogDate"
F_SERIAL = "SerialNumber"
F_DIR = "PunchDirection"
LOG_DATE_FMT = "%Y-%m-%d %H:%M:%S"


# ── config + watermark ───────────────────────────────────────────────────────


def load_config(path: str) -> configparser.ConfigParser:
    if not os.path.exists(path):
        raise SystemExit(f"Config file not found: {path} (copy agent.example.ini)")
    cfg = configparser.ConfigParser()
    cfg.read(path)
    return cfg


def build_conn_str(cfg: configparser.ConfigParser) -> str:
    """A full ODBC connection string wins; otherwise assemble one from parts."""
    sql = cfg["sql"]
    raw = sql.get("odbc_connection_string", "").strip()
    if raw:
        return raw
    driver = sql.get("driver", "ODBC Driver 17 for SQL Server")
    parts = [
        f"DRIVER={{{driver}}}",
        f"SERVER={sql.get('server', 'localhost')}",
        f"DATABASE={sql.get('database', '')}",
        f"UID={sql.get('username', '')}",
        f"PWD={sql.get('password', '')}",
    ]
    if sql.getboolean("trust_server_certificate", fallback=True):
        parts.append("TrustServerCertificate=yes")
    if sql.getboolean("encrypt", fallback=False):
        parts.append("Encrypt=yes")
    return ";".join(parts) + ";"


def read_watermark(path: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (FileNotFoundError, ValueError):
        return {}


def write_watermark(path: str, wm: dict) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(wm, fh)
    os.replace(tmp, path)  # atomic so a crash never leaves a half-written file


# ── SQL read ────────────────────────────────────────────────────────────────


def _q(name: str) -> str:
    """Bracket-quote a SQL identifier (column). Table/view is passed as-is so it
    can carry a schema prefix like dbo.DeviceLogs."""
    return "[" + name.replace("]", "]]") + "]"


def fetch_new_rows(conn, cfg, wm: dict) -> tuple[list[dict], dict]:
    """Read punches newer than the watermark. Returns (rows, new_watermark).

    ``rows`` use the backend's field names; the new watermark is only what we
    *read* — the caller advances the persisted watermark only after a successful
    push, so a failed push is retried, not skipped."""
    src = cfg["source"]
    table = src["table"].strip()
    emp_col = src["employee_code_column"].strip()
    id_col = src.get("id_column", "").strip()
    ts_col = src.get("timestamp_column", "").strip()
    serial_col = src.get("serial_column", "").strip()
    dir_col = src.get("direction_column", "").strip()
    batch = src.getint("batch_size", fallback=500)

    if not id_col and not ts_col:
        raise SystemExit("Configure [source] id_column or timestamp_column.")

    order_col = id_col or ts_col
    select = [f"{_q(emp_col)} AS {F_EMP}"]
    if ts_col:
        select.append(f"{_q(ts_col)} AS {F_LOG}")
    if serial_col:
        select.append(f"{_q(serial_col)} AS {F_SERIAL}")
    if dir_col:
        select.append(f"{_q(dir_col)} AS {F_DIR}")
    select.append(f"{_q(order_col)} AS _cursor")

    where_val = wm.get("cursor")
    if where_val is None:
        where_val = 0 if id_col else "1900-01-01 00:00:00"
    sql = (
        f"SELECT TOP (?) {', '.join(select)} FROM {table} "
        f"WHERE {_q(order_col)} > ? ORDER BY {_q(order_col)} ASC"
    )

    cur = conn.cursor()
    cur.execute(sql, batch, where_val)
    columns = [c[0] for c in cur.description]

    rows: list[dict] = []
    last_cursor = wm.get("cursor")
    for record in cur.fetchall():
        row = dict(zip(columns, record))
        cursor_val = row.pop("_cursor")
        out = {F_EMP: _s(row.get(F_EMP))}
        log_dt = row.get(F_LOG)
        if isinstance(log_dt, datetime):
            out[F_LOG] = log_dt.strftime(LOG_DATE_FMT)
        elif log_dt is not None:
            out[F_LOG] = str(log_dt)
        elif isinstance(cursor_val, datetime):
            out[F_LOG] = cursor_val.strftime(LOG_DATE_FMT)  # ts is the cursor
        if serial_col:
            out[F_SERIAL] = _s(row.get(F_SERIAL))
        if dir_col:
            out[F_DIR] = _s(row.get(F_DIR))
        rows.append(out)
        last_cursor = (
            int(cursor_val)
            if id_col
            else cursor_val.strftime(LOG_DATE_FMT)
            if isinstance(cursor_val, datetime)
            else str(cursor_val)
        )

    return rows, {"cursor": last_cursor}


def _s(v) -> str:
    return "" if v is None else str(v).strip()


# ── push ────────────────────────────────────────────────────────────────────


def push_rows(cfg: configparser.ConfigParser, rows: list[dict]) -> dict:
    be = cfg["backend"]
    url = be["url"].rstrip("/") + "/api/v1/attendance/smartoffice/ingest"
    params = {}
    if be.get("branch_id", "").strip():
        params["branch_id"] = be["branch_id"].strip()
    resp = requests.post(
        url,
        params=params,
        json={"rows": rows},
        headers={"X-SmartOffice-Token": be["token"]},
        timeout=be.getfloat("timeout_seconds", fallback=30.0),
        verify=be.getboolean("verify_tls", fallback=True),
    )
    resp.raise_for_status()
    return resp.json()


# ── loop ────────────────────────────────────────────────────────────────────


def run_once(cfg: configparser.ConfigParser, wm_path: str) -> dict:
    if pyodbc is None:
        raise SystemExit("pyodbc is not installed. Run: pip install -r requirements.txt")
    wm = read_watermark(wm_path)
    conn = pyodbc.connect(build_conn_str(cfg), timeout=10)
    try:
        rows, new_wm = fetch_new_rows(conn, cfg, wm)
    finally:
        conn.close()

    if not rows:
        return {"read": 0, "pushed": 0}

    summary = push_rows(cfg, rows)
    # Advance the watermark ONLY after the push succeeded.
    write_watermark(wm_path, new_wm)
    log.info(
        "pushed %d rows -> inserted=%s skipped_no_student=%s duplicate=%s cursor=%s",
        len(rows), summary.get("inserted"), summary.get("skipped_no_student"),
        summary.get("skipped_duplicate"), new_wm.get("cursor"),
    )
    return {"read": len(rows), "pushed": len(rows), "server": summary, "cursor": new_wm["cursor"]}


def main() -> None:
    parser = argparse.ArgumentParser(description="SmartOffice attendance agent")
    parser.add_argument("--config", default="agent.ini", help="Path to agent.ini")
    parser.add_argument("--once", action="store_true", help="Run one cycle and exit")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    cfg = load_config(args.config)
    wm_path = cfg["agent"].get("watermark_file", "watermark.json")
    interval = cfg["agent"].getint("poll_interval_seconds", fallback=20)

    if args.once:
        result = run_once(cfg, wm_path)
        print(json.dumps(result, indent=2))
        return

    log.info("agent started; polling every %ds", interval)
    while True:
        try:
            run_once(cfg, wm_path)
        except Exception:  # never let one bad cycle kill the loop
            log.exception("cycle failed; will retry next tick")
        time.sleep(interval)


if __name__ == "__main__":
    sys.exit(main())
