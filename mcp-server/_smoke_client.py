"""Smoke-test client for the Academy MCP server.

Spawns server.py over stdio, sends `initialize` + `list_tools`, then attempts
one tool call (`get_risk_students` with a dummy batch). Prints a summary.

Run:  python _smoke_client.py
"""

import asyncio
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

HERE = Path(__file__).parent
PY = HERE / ".venv" / "Scripts" / "python.exe"
SERVER = HERE / "server.py"

EXPECTED_TOOLS = {
    "get_risk_students",
    "get_batch_analytics",
    "get_teacher_productivity",
    "get_student_attendance",
    "create_lecture",
    "import_syllabus",
}


async def main() -> int:
    params = StdioServerParameters(
        command=str(PY),
        args=[str(SERVER)],
        env={
            **os.environ,
            "ACADEMY_API_URL": os.environ.get("ACADEMY_API_URL", "http://localhost:8000"),
            "ACADEMY_API_TOKEN": os.environ.get("ACADEMY_API_TOKEN", "dummy-jwt"),
            "ACADEMY_BRANCH_ID": os.environ.get(
                "ACADEMY_BRANCH_ID", "00000000-0000-0000-0000-000000000000"
            ),
        },
    )

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            print(f"server: {init.serverInfo.name} v{init.serverInfo.version}")
            print(f"protocol: {init.protocolVersion}")

            listed = await session.list_tools()
            names = {t.name for t in listed.tools}
            print(f"\ntools advertised ({len(names)}): {sorted(names)}")

            missing = EXPECTED_TOOLS - names
            extra = names - EXPECTED_TOOLS
            if missing:
                print(f"FAIL: missing tools: {sorted(missing)}", file=sys.stderr)
                return 2
            if extra:
                print(f"WARN: unexpected tools: {sorted(extra)}", file=sys.stderr)

            print("\nschema spot-check: create_lecture.required")
            create = next(t for t in listed.tools if t.name == "create_lecture")
            required = create.inputSchema.get("required", [])
            print(f"  required={required}")
            for need in ("batch_id", "teacher_id", "subject_id", "scheduled_start"):
                if need not in required:
                    print(f"FAIL: create_lecture missing required field {need!r}", file=sys.stderr)
                    return 2

            print("\nlive backend probe: get_risk_students with dummy batch_id...")
            try:
                result = await session.call_tool(
                    "get_risk_students",
                    {"batch_id": "00000000-0000-0000-0000-000000000000", "threshold": 0.5},
                )
                text = result.content[0].text if result.content else "(no content)"
                print(f"  result: {text[:300]}")
            except Exception as exc:
                print(f"  call_tool raised: {exc}")

            return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
