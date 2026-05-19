# Academy Platform — MCP Server

A standalone MCP server that wraps the Academy Platform FastAPI backend so
MCP clients (Claude Desktop, etc.) can drive it via natural language.

This is a thin client: no business logic lives here. Every tool maps to one
existing backend endpoint.

## Tools

| Tool | Backend endpoint |
|---|---|
| `get_risk_students` | `GET /api/v1/analytics/batches/{batch_id}/risk-students` |
| `get_batch_analytics` | `GET /api/v1/analytics/batches/{batch_id}` |
| `get_teacher_productivity` | `GET /api/v1/analytics/teachers/{teacher_id}` |
| `get_student_attendance` | `GET /api/v1/attendance/student/{student_id}` |
| `create_lecture` | `POST /api/v1/lectures` |
| `import_syllabus` | `POST /api/v1/syllabus/import` |

Risk-student and analytics endpoints only return UUIDs, not display names. If
you want names in the output you'd need to add a follow-up call to the
student endpoint per row — out of scope for v1.

## Setup

```powershell
cd mcp-server
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
# edit .env with real values
```

## Getting an `ACADEMY_API_TOKEN`

The backend issues an `access_token` cookie (HTTP-only JWT). Log in once and
copy the cookie value:

```powershell
$body = '{"email":"you@example.com","password":"yourpassword"}'
$resp = Invoke-WebRequest -Uri http://localhost:8000/api/v1/auth/login `
    -Method POST -ContentType application/json -Body $body `
    -SessionVariable s
($s.Cookies.GetCookies("http://localhost:8000") | Where-Object Name -eq access_token).Value
```

That JWT is what goes into `ACADEMY_API_TOKEN`.

> For production use, mint a long-lived token tied to a dedicated service
> account rather than reusing a human login cookie.

## Getting `ACADEMY_BRANCH_ID`

One MCP install = one branch. Grab the branch UUID from the platform UI or
from the user payload in the JWT (`branch_id` claim).

## Run standalone (smoke test)

```powershell
$env:ACADEMY_API_URL = "http://localhost:8000"
$env:ACADEMY_API_TOKEN = "<jwt>"
$env:ACADEMY_BRANCH_ID = "<branch-uuid>"
python server.py
```

The server speaks MCP over stdio, so without a client connected it will
just sit idle. Use it via an MCP client (below).

## Claude Desktop config

Edit `%APPDATA%\Claude\claude_desktop_config.json` (create if missing):

```json
{
  "mcpServers": {
    "academy": {
      "command": "C:\\Users\\Admin\\Documents\\academy-platform\\mcp-server\\.venv\\Scripts\\python.exe",
      "args": ["C:\\Users\\Admin\\Documents\\academy-platform\\mcp-server\\server.py"],
      "env": {
        "ACADEMY_API_URL": "http://localhost:8000",
        "ACADEMY_API_TOKEN": "your_jwt_here",
        "ACADEMY_BRANCH_ID": "your_branch_uuid_here"
      }
    }
  }
}
```

Restart Claude Desktop. The tools should appear under the connectors icon.

## Example prompts

- "Show me at-risk students in batch `<uuid>` with threshold 0.6."
- "Schedule a Physics lecture for batch `<uuid>` with teacher `<uuid>` and subject `<uuid>` tomorrow at 9:00."
- "What's the productivity of teacher `<uuid>`?"
- "Pull attendance for student `<uuid>`."

For `import_syllabus`, the file must be passed as base64 — Claude Desktop
can handle that when you attach a file in chat and ask "import this syllabus
into course `<uuid>`."

## Adding tools

Each tool is ~15 lines: one entry in `list_tools()`, one branch in
`_dispatch()`. Follow the existing examples and keep the formatter terse.
