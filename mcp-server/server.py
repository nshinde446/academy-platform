"""MCP server for the Academy Platform.

Exposes 6 tools that wrap existing FastAPI endpoints, so any MCP client
(Claude Desktop, etc.) can drive the platform via natural language.

Auth note: the backend authenticates via an HTTP-only `access_token` cookie
issued by POST /api/v1/auth/login — NOT a Bearer header. The MCP server
therefore sends the JWT as `Cookie: access_token=...` on every call.
"""

import asyncio
import base64
import os
from datetime import datetime, timedelta
from typing import Any

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

API_BASE_URL = os.getenv("ACADEMY_API_URL", "http://localhost:8000").rstrip("/")
API_TOKEN = os.getenv("ACADEMY_API_TOKEN")
BRANCH_ID = os.getenv("ACADEMY_BRANCH_ID")  # required for analytics/attendance

if not API_TOKEN:
    raise SystemExit("ACADEMY_API_TOKEN env var is required")
if not BRANCH_ID:
    raise SystemExit("ACADEMY_BRANCH_ID env var is required (single-tenant per server)")

app: Server = Server("academy-platform")


async def _request(method: str, path: str, **kwargs: Any) -> Any:
    """Make an authenticated call to the backend. Returns parsed JSON or None."""
    cookies = {"access_token": API_TOKEN}
    url = f"{API_BASE_URL}{path}"
    async with httpx.AsyncClient(timeout=30.0, cookies=cookies) as client:
        resp = await client.request(method, url, **kwargs)
    if resp.status_code >= 400:
        raise RuntimeError(f"{method} {path} -> {resp.status_code}: {resp.text}")
    if resp.status_code == 204 or not resp.content:
        return None
    return resp.json()


def _text(s: str) -> list[TextContent]:
    return [TextContent(type="text", text=s)]


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="get_risk_students",
            description=(
                "List at-risk students in a batch, ranked by risk score. "
                "Returns student UUIDs with risk/attendance/score metrics."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "batch_id": {"type": "string", "description": "UUID of the batch"},
                    "threshold": {
                        "type": "number",
                        "description": "Minimum risk score 0.0-1.0 (default 0.7)",
                        "default": 0.7,
                    },
                },
                "required": ["batch_id"],
            },
        ),
        Tool(
            name="get_batch_analytics",
            description="Overall metrics for a batch: attendance %, average score, top performers, weak subjects.",
            inputSchema={
                "type": "object",
                "properties": {
                    "batch_id": {"type": "string", "description": "UUID of the batch"},
                },
                "required": ["batch_id"],
            },
        ),
        Tool(
            name="get_teacher_productivity",
            description="Lecture-completion metrics for a teacher (completion rate, avg delay, student attendance).",
            inputSchema={
                "type": "object",
                "properties": {
                    "teacher_id": {"type": "string", "description": "UUID of the teacher"},
                },
                "required": ["teacher_id"],
            },
        ),
        Tool(
            name="get_student_attendance",
            description="Per-lecture attendance records for a student (most recent first).",
            inputSchema={
                "type": "object",
                "properties": {
                    "student_id": {"type": "string", "description": "UUID of the student"},
                    "limit": {
                        "type": "integer",
                        "description": "Max records to return 1-200 (default 50)",
                        "default": 50,
                    },
                },
                "required": ["student_id"],
            },
        ),
        Tool(
            name="create_lecture",
            description=(
                "Schedule a lecture for a batch + teacher. "
                "`scheduled_end` is computed from `duration_minutes` if omitted."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "batch_id": {"type": "string", "description": "UUID of the batch"},
                    "teacher_id": {"type": "string", "description": "UUID of the teacher"},
                    "subject_id": {"type": "string", "description": "UUID of the subject"},
                    "topic_id": {"type": "string", "description": "UUID of the topic (optional)"},
                    "classroom_id": {"type": "string", "description": "UUID of the classroom (optional)"},
                    "scheduled_start": {
                        "type": "string",
                        "description": "ISO datetime, e.g. 2026-05-20T09:00:00",
                    },
                    "scheduled_end": {
                        "type": "string",
                        "description": "ISO datetime (optional; defaults to start + duration_minutes)",
                    },
                    "duration_minutes": {
                        "type": "integer",
                        "description": "Used to compute scheduled_end if not given (default 60)",
                        "default": 60,
                    },
                    "delivery_mode": {
                        "type": "string",
                        "description": "offline | online | hybrid (default offline)",
                        "default": "offline",
                    },
                    "notes": {"type": "string"},
                },
                "required": ["batch_id", "teacher_id", "subject_id", "scheduled_start"],
            },
        ),
        Tool(
            name="import_syllabus",
            description="Import an Excel syllabus into a course. Provide the .xlsx as base64.",
            inputSchema={
                "type": "object",
                "properties": {
                    "course_id": {"type": "string", "description": "UUID of the course"},
                    "file_data_base64": {
                        "type": "string",
                        "description": "Base64-encoded .xlsx contents",
                    },
                    "filename": {"type": "string", "description": "Original filename (default upload.xlsx)"},
                },
                "required": ["course_id", "file_data_base64"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    try:
        return await _dispatch(name, arguments)
    except Exception as exc:
        return _text(f"Tool error ({name}): {exc}")


async def _dispatch(name: str, args: dict) -> list[TextContent]:
    if name == "get_risk_students":
        batch_id = args["batch_id"]
        threshold = args.get("threshold", 0.7)
        data = await _request(
            "GET",
            f"/api/v1/analytics/batches/{batch_id}/risk-students",
            params={"branch_id": BRANCH_ID, "threshold": threshold},
        )
        if not data:
            return _text(f"No at-risk students at threshold {threshold:.2f} for batch {batch_id}.")
        lines = [
            f"## At-risk students (threshold {threshold:.2f})",
            f"Batch: `{batch_id}`",
            f"{len(data)} student(s):",
            "",
        ]
        for s in data:
            lines.append(
                f"- `{s['student_id']}` — risk {s['risk_score']:.2f}, "
                f"attendance {s['attendance_percentage']:.1f}%, "
                f"avg score {s['average_score']:.1f}"
            )
        return _text("\n".join(lines))

    if name == "get_batch_analytics":
        batch_id = args["batch_id"]
        data = await _request(
            "GET",
            f"/api/v1/analytics/batches/{batch_id}",
            params={"branch_id": BRANCH_ID},
        )
        lines = [
            f"## Batch analytics — `{batch_id}`",
            f"- Total students: {data.get('total_students', 'n/a')}",
            f"- Avg attendance: {data.get('avg_attendance', 0):.1f}%",
            f"- Avg score: {data.get('avg_score', 0):.1f}",
        ]
        top = data.get("top_performers") or []
        weak = data.get("weak_subjects") or []
        if top:
            lines.append(f"- Top performers: {', '.join(top[:5])}")
        if weak:
            lines.append(f"- Weak subjects: {', '.join(weak[:5])}")
        return _text("\n".join(lines))

    if name == "get_teacher_productivity":
        teacher_id = args["teacher_id"]
        data = await _request(
            "GET",
            f"/api/v1/analytics/teachers/{teacher_id}",
            params={"branch_id": BRANCH_ID},
        )
        return _text(
            "\n".join(
                [
                    f"## Teacher productivity — `{teacher_id}`",
                    f"- Total lectures: {data.get('total_lectures', 'n/a')}",
                    f"- Completed: {data.get('completed_lectures', 'n/a')}",
                    f"- Completion rate: {data.get('completion_rate', 0):.1f}%",
                    f"- Avg delay: {data.get('avg_delay_minutes', 0):.1f} min",
                    f"- Avg student attendance: {data.get('avg_student_attendance', 0):.1f}%",
                ]
            )
        )

    if name == "get_student_attendance":
        student_id = args["student_id"]
        limit = args.get("limit", 50)
        data = await _request(
            "GET",
            f"/api/v1/attendance/student/{student_id}",
            params={"branch_id": BRANCH_ID, "limit": limit},
        ) or []
        if not data:
            return _text(f"No attendance records for student `{student_id}`.")
        total = len(data)
        present = sum(1 for r in data if r.get("attendance_status") == "PRESENT")
        absent = sum(1 for r in data if r.get("attendance_status") == "ABSENT")
        late = sum(1 for r in data if r.get("attendance_status") == "LATE")
        return _text(
            "\n".join(
                [
                    f"## Attendance — student `{student_id}`",
                    f"- Records returned: {total} (limit {limit})",
                    f"- Present: {present} ({present / total * 100:.1f}%)",
                    f"- Absent: {absent} ({absent / total * 100:.1f}%)",
                    f"- Late: {late} ({late / total * 100:.1f}%)",
                ]
            )
        )

    if name == "create_lecture":
        scheduled_start_str = args["scheduled_start"]
        scheduled_end_str = args.get("scheduled_end")
        if not scheduled_end_str:
            duration = int(args.get("duration_minutes", 60))
            start_dt = datetime.fromisoformat(scheduled_start_str)
            scheduled_end_str = (start_dt + timedelta(minutes=duration)).isoformat()
        payload = {
            "teacher_id": args["teacher_id"],
            "batch_id": args["batch_id"],
            "subject_id": args["subject_id"],
            "scheduled_start": scheduled_start_str,
            "scheduled_end": scheduled_end_str,
            "delivery_mode": args.get("delivery_mode", "offline"),
        }
        for opt in ("classroom_id", "topic_id", "notes"):
            if args.get(opt):
                payload[opt] = args[opt]
        result = await _request("POST", "/api/v1/lectures", json=payload)
        return _text(
            f"Lecture created.\n- id: `{result['id']}`\n"
            f"- scheduled: {result['scheduled_start']} → {result['scheduled_end']}\n"
            f"- status: {result.get('lecture_status', 'scheduled')}"
        )

    if name == "import_syllabus":
        course_id = args["course_id"]
        filename = args.get("filename", "upload.xlsx")
        try:
            file_bytes = base64.b64decode(args["file_data_base64"], validate=True)
        except Exception as exc:
            return _text(f"Invalid base64 payload: {exc}")
        files = {
            "file": (
                filename,
                file_bytes,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        }
        result = await _request(
            "POST",
            "/api/v1/syllabus/import",
            params={"course_id": course_id},
            files=files,
        )
        return _text(
            "\n".join(
                [
                    f"## Syllabus imported into course `{course_id}`",
                    f"- subjects created: {result.get('subjects_created', 0)}",
                    f"- chapters created: {result.get('chapters_created', 0)}",
                    f"- topics created: {result.get('topics_created', 0)}",
                    f"- subtopics created: {result.get('subtopics_created', 0)}",
                    f"- rows processed: {result.get('rows_processed', 0)}",
                    f"- errors: {len(result.get('errors') or [])}",
                ]
            )
        )

    raise ValueError(f"Unknown tool: {name}")


async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
