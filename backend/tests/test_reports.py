import json
import uuid
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.reports.models.report_models import ReportJob, ReportTemplate
from app.modules.reports.services import report_service

BRANCH_A_ID = "00000000-0000-0000-0000-000000000001"
BRANCH_B_ID = "00000000-0000-0000-0000-000000000002"


async def _login_admin(client: AsyncClient):
    resp = await client.post("/api/v1/auth/login", json={
        "email": "admin@test.com",
        "password": "Admin123!",
    })
    assert resp.status_code == 200


async def _login_teacher(client: AsyncClient):
    resp = await client.post("/api/v1/auth/login", json={
        "email": "teacher@test.com",
        "password": "Teacher123!",
    })
    assert resp.status_code == 200


def _template_payload(**overrides):
    base = {
        "name": "Student Report Card",
        "report_type": "REPORT_CARD",
        "template_file": "report_card.html",
        "config": {"tables": ["analytics_student_summary"]},
        "is_active": True,
        "branch_id": BRANCH_A_ID,
    }
    base.update(overrides)
    return base


# ─── Test 1: Create report template ──────────────────────────────────────────

async def test_create_template(client: AsyncClient, seed_data):
    await _login_admin(client)
    resp = await client.post(
        "/api/v1/reports/templates",
        json=_template_payload(),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Student Report Card"
    assert data["report_type"] == "REPORT_CARD"
    assert data["template_file"] == "report_card.html"
    assert data["is_active"] is True
    assert data["config"] == {"tables": ["analytics_student_summary"]}


# ─── Test 2: List report templates ───────────────────────────────────────────

async def test_list_templates(client: AsyncClient, seed_data):
    await _login_admin(client)
    await client.post("/api/v1/reports/templates", json=_template_payload())
    await client.post("/api/v1/reports/templates", json=_template_payload(
        name="Attendance Report",
        report_type="ATTENDANCE_REPORT",
        template_file="attendance_report.html",
    ))
    resp = await client.get("/api/v1/reports/templates")
    assert resp.status_code == 200
    assert len(resp.json()) >= 2


# ─── Test 3: Invalid report_type rejected ────────────────────────────────────

async def test_invalid_report_type(client: AsyncClient, seed_data):
    await _login_admin(client)
    resp = await client.post(
        "/api/v1/reports/templates",
        json=_template_payload(report_type="INVALID_TYPE"),
    )
    assert resp.status_code == 400


# ─── Test 4: Create report job and check status ─────────────────────────────

async def test_create_job_and_status(client: AsyncClient, seed_data):
    await _login_admin(client)
    resp = await client.post("/api/v1/reports/templates", json=_template_payload())
    template_id = resp.json()["id"]

    resp = await client.post("/api/v1/reports/generate", json={
        "template_id": template_id,
        "parameters": {"student_id": "00000000-0000-0000-0000-000000000090"},
        "output_format": "PDF",
        "branch_id": BRANCH_A_ID,
    })
    assert resp.status_code == 201
    job = resp.json()
    assert job["job_status"] in ("COMPLETED", "PROCESSING", "PENDING")
    assert job["template_id"] == template_id
    assert job["output_format"] == "PDF"

    resp = await client.get(f"/api/v1/reports/jobs/{job['id']}")
    assert resp.status_code == 200


# ─── Test 5: Generate PDF report ────────────────────────────────────────────

async def test_generate_pdf_report(client: AsyncClient, seed_data):
    await _login_admin(client)
    resp = await client.post("/api/v1/reports/templates", json=_template_payload())
    template_id = resp.json()["id"]

    resp = await client.post("/api/v1/reports/generate", json={
        "template_id": template_id,
        "parameters": {"student_id": "00000000-0000-0000-0000-000000000090"},
        "output_format": "PDF",
        "branch_id": BRANCH_A_ID,
    })
    assert resp.status_code == 201
    job = resp.json()
    assert job["job_status"] == "COMPLETED"
    assert job["output_url"] is not None


# ─── Test 6: Generate Excel report ──────────────────────────────────────────

async def test_generate_excel_report(client: AsyncClient, seed_data):
    await _login_admin(client)
    resp = await client.post("/api/v1/reports/templates", json=_template_payload(
        name="Analytics Export",
        report_type="ANALYTICS_EXPORT",
        template_file="attendance_report.html",
    ))
    template_id = resp.json()["id"]

    resp = await client.post("/api/v1/reports/generate", json={
        "template_id": template_id,
        "parameters": {},
        "output_format": "EXCEL",
        "branch_id": BRANCH_A_ID,
    })
    assert resp.status_code == 201
    job = resp.json()
    assert job["job_status"] == "COMPLETED"
    assert job["output_format"] == "EXCEL"


# ─── Test 7: Download endpoint ──────────────────────────────────────────────

async def test_download_completed_report(client: AsyncClient, seed_data):
    await _login_admin(client)
    resp = await client.post("/api/v1/reports/templates", json=_template_payload())
    template_id = resp.json()["id"]

    resp = await client.post("/api/v1/reports/generate", json={
        "template_id": template_id,
        "parameters": {},
        "output_format": "PDF",
        "branch_id": BRANCH_A_ID,
    })
    job_id = resp.json()["id"]

    resp = await client.get(f"/api/v1/reports/jobs/{job_id}/download")
    assert resp.status_code == 200
    data = resp.json()
    assert "download_url" in data
    assert data["output_format"] == "PDF"


# ─── Test 8: Download not ready ─────────────────────────────────────────────

async def test_download_not_ready(client: AsyncClient, seed_data, db_session: AsyncSession):
    await _login_admin(client)
    resp = await client.post("/api/v1/reports/templates", json=_template_payload())
    template_id = uuid.UUID(resp.json()["id"])

    job = ReportJob(
        template_id=template_id,
        parameters_json=json.dumps({}),
        job_status="PENDING",
        output_format="PDF",
        requested_by=uuid.UUID("00000000-0000-0000-0000-000000000100"),
        requested_at=datetime.now(timezone.utc),
        branch_id=uuid.UUID(BRANCH_A_ID),
        status="active",
        is_deleted=False,
    )
    db_session.add(job)
    await db_session.commit()

    resp = await client.get(f"/api/v1/reports/jobs/{job.id}/download")
    assert resp.status_code == 400


# ─── Test 9: Branch isolation ────────────────────────────────────────────────

async def test_branch_isolation(client: AsyncClient, seed_data):
    await _login_admin(client)
    await client.post("/api/v1/reports/templates", json=_template_payload(
        name="branch_a_report",
        branch_id=BRANCH_A_ID,
    ))
    resp = await client.get(
        "/api/v1/reports/templates",
        params={"branch_id": BRANCH_B_ID},
    )
    assert resp.status_code == 200
    names = [t["name"] for t in resp.json()]
    assert "branch_a_report" not in names


# ─── Test 10: Global template visible to all branches ───────────────────────

async def test_global_template(client: AsyncClient, seed_data):
    await _login_admin(client)
    await client.post("/api/v1/reports/templates", json=_template_payload(
        name="global_report",
        branch_id=None,
    ))
    resp = await client.get(
        "/api/v1/reports/templates",
        params={"branch_id": BRANCH_B_ID},
    )
    names = [t["name"] for t in resp.json()]
    assert "global_report" in names


# ─── Test 11: Audit logging on template creation ────────────────────────────

async def test_audit_log_on_create(client: AsyncClient, seed_data):
    await _login_admin(client)
    await client.post("/api/v1/reports/templates", json=_template_payload(
        name="audit_test_report",
    ))
    resp = await client.get(
        "/api/v1/audit/logs",
        params={"table_name": "report_templates", "action": "CREATE"},
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert any(
        log["table_name"] == "report_templates" and log["action"] == "CREATE"
        for log in items
    )


# ─── Test 12: Audit logging on job creation ──────────────────────────────────

async def test_audit_log_on_job_create(client: AsyncClient, seed_data):
    await _login_admin(client)
    resp = await client.post("/api/v1/reports/templates", json=_template_payload())
    template_id = resp.json()["id"]

    await client.post("/api/v1/reports/generate", json={
        "template_id": template_id,
        "parameters": {},
        "output_format": "PDF",
        "branch_id": BRANCH_A_ID,
    })
    resp = await client.get(
        "/api/v1/audit/logs",
        params={"table_name": "report_jobs", "action": "CREATE"},
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert any(
        log["table_name"] == "report_jobs" and log["action"] == "CREATE"
        for log in items
    )


# ─── Test 13: RBAC – teacher cannot create template ─────────────────────────

async def test_teacher_cannot_create_template(client: AsyncClient, seed_data):
    await _login_teacher(client)
    resp = await client.post(
        "/api/v1/reports/templates",
        json=_template_payload(),
    )
    assert resp.status_code == 403


# ─── Test 14: Teacher can generate report ────────────────────────────────────

async def test_teacher_can_generate_report(client: AsyncClient, seed_data):
    await _login_admin(client)
    resp = await client.post("/api/v1/reports/templates", json=_template_payload())
    template_id = resp.json()["id"]

    await _login_teacher(client)
    resp = await client.post("/api/v1/reports/generate", json={
        "template_id": template_id,
        "parameters": {},
        "output_format": "PDF",
        "branch_id": BRANCH_A_ID,
    })
    assert resp.status_code == 201


# ─── Test 15: List jobs returns user's own jobs ─────────────────────────────

async def test_list_jobs(client: AsyncClient, seed_data):
    await _login_admin(client)
    resp = await client.post("/api/v1/reports/templates", json=_template_payload())
    template_id = resp.json()["id"]

    await client.post("/api/v1/reports/generate", json={
        "template_id": template_id,
        "parameters": {},
        "output_format": "PDF",
        "branch_id": BRANCH_A_ID,
    })

    resp = await client.get("/api/v1/reports/jobs")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


# ─── Test 16: Invalid output format rejected ────────────────────────────────

async def test_invalid_output_format(client: AsyncClient, seed_data):
    await _login_admin(client)
    resp = await client.post("/api/v1/reports/templates", json=_template_payload())
    template_id = resp.json()["id"]

    resp = await client.post("/api/v1/reports/generate", json={
        "template_id": template_id,
        "parameters": {},
        "output_format": "DOCX",
        "branch_id": BRANCH_A_ID,
    })
    assert resp.status_code == 400


# ─── Test 17: Nonexistent template for job creation ─────────────────────────

async def test_nonexistent_template(client: AsyncClient, seed_data):
    await _login_admin(client)
    resp = await client.post("/api/v1/reports/generate", json={
        "template_id": str(uuid.uuid4()),
        "parameters": {},
        "output_format": "PDF",
    })
    assert resp.status_code == 404


# ─── Test 18: Jinja2 template rendering ─────────────────────────────────────

def test_render_jinja_template():
    result = report_service.render_jinja_template("report_card.html", {
        "student_name": "Alice",
        "batch_name": "Batch A",
        "academic_year": "2025-2026",
        "attendance_percentage": 92.5,
        "average_score": 85.0,
        "subjects": [
            {"name": "Physics", "marks": 90, "grade": "A"},
            {"name": "Math", "marks": 80, "grade": "B"},
        ],
    })
    assert "Alice" in result
    assert "Physics" in result
    assert "90" in result


# ─── Test 19: Excel export ──────────────────────────────────────────────────

def test_export_to_excel():
    data = {
        "headers": ["Name", "Score"],
        "rows": [["Alice", 90], ["Bob", 85]],
    }
    result = report_service.export_to_excel(data)
    assert len(result) > 0


# ─── Test 20: PDF export placeholder ────────────────────────────────────────

def test_export_to_pdf():
    result = report_service.export_to_pdf("<h1>Test Report</h1>")
    assert b"PDF" in result
    assert b"Test Report" in result
