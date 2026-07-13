# SmartOffice attendance agent

A tiny agent that runs on the institute's **SmartOffice PC** and forwards
biometric punches to the Academy backend in near-real-time.

```
 device → SmartOffice (IIS + MSSQL)  ── agent reads new rows (localhost, read-only)
                                     ── HTTPS POST (outbound only) → Academy backend
                                        → ingest → DailyAttendance → the /attendance
                                          screen live-refreshes
```

**Why an agent:** it makes *outbound* HTTPS calls only, so it works behind the
institute router/NAT with **no port-forwarding and without exposing SQL Server
to the internet**. It keeps a local watermark, so a dropped connection just
means the next cycle re-sends (the server dedups, so re-sends are harmless).

## Prerequisites (on the SmartOffice PC)

1. **Python 3.9+** (or use the packaged `.exe` once we build one).
2. **Microsoft ODBC Driver 17/18 for SQL Server** — usually already present
   where MSSQL runs. (`ODBC Driver 17 for SQL Server` is the default in the ini.)
3. From the provider: a **read-only SQL login**, and the **table/view name +
   column names** that hold the punches. Prefer a monotonic `IDENTITY`/`rowversion`
   column for exact incremental reads.
4. From the backend admin: the **base URL** and the **ingest token**
   (`SMARTOFFICE_INGEST_TOKEN`).

## Setup

```bat
cd agent\smartoffice
pip install -r requirements.txt
copy agent.example.ini agent.ini
notepad agent.ini            REM fill in [sql], [source], [backend]
```

Then test one cycle:

```bat
python smartoffice_agent.py --config agent.ini --once
```

You should see JSON like `{"read": 12, "pushed": 12, "server": {"inserted": 12, ...}}`.
If `skipped_no_student` is high, the students' `rfid_number` doesn't match their
SmartOffice `EmployeeCode` yet — fix the roster mapping.

## Run continuously (auto-start, survives reboot)

**Option A — Task Scheduler (simplest):** create a task that runs at system
startup:

```bat
schtasks /Create /TN "SmartOfficeAgent" /SC ONSTART /RL HIGHEST /RU SYSTEM ^
  /TR "python \"C:\path\to\agent\smartoffice\smartoffice_agent.py\" --config \"C:\path\to\agent\smartoffice\agent.ini\""
```

**Option B — Windows service via [NSSM](https://nssm.cc)** (auto-restarts on crash):

```bat
nssm install SmartOfficeAgent python "C:\path\to\smartoffice_agent.py" --config "C:\path\to\agent.ini"
nssm start SmartOfficeAgent
```

The agent loops every `poll_interval_seconds` (default 20s) and never dies on a
bad cycle — it logs and retries.

## Server side (once)

- Set `SMARTOFFICE_INGEST_TOKEN` (a long random string) in the backend env — the
  `/api/v1/attendance/smartoffice/ingest` endpoint returns **503** until it's set
  (fail-safe). Set the same value as `token` in `agent.ini`.
- Set `SMARTOFFICE_BRANCH_ID` (or put `branch_id` in `agent.ini`).
- Ensure each student's `rfid_number` equals their SmartOffice `EmployeeCode`.

## Security

- Use a **read-only** SQL login scoped to the punch table/view — never `SA`.
- Keep `agent.ini`, `watermark.json`, and the token off version control
  (`.gitignore`d here).
- The agent needs only outbound 443 to the backend; no inbound rules.
