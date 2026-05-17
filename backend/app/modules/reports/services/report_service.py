import json
import io
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.services import audit_service
from app.modules.reports.repositories import report_repository
from app.modules.reports.schemas.report_schemas import VALID_OUTPUT_FORMATS, VALID_REPORT_TYPES

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
REPORTS_OUTPUT_DIR = Path(__file__).parent.parent.parent.parent.parent / "generated_reports"


async def create_template(
    session: AsyncSession,
    data: dict,
    current_user_id: uuid.UUID,
    ip_address: str | None = None,
):
    if data.get("report_type") not in VALID_REPORT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid report_type. Must be one of: {', '.join(sorted(VALID_REPORT_TYPES))}",
        )

    config_json = None
    if data.get("config"):
        config_json = json.dumps(data["config"])

    template = await report_repository.create_template(
        session,
        name=data["name"],
        report_type=data["report_type"],
        template_file=data["template_file"],
        config_json=config_json,
        is_active=data.get("is_active", True),
        branch_id=data.get("branch_id"),
    )

    await audit_service.log_action(
        session,
        user_id=current_user_id,
        action="CREATE",
        table_name="report_templates",
        record_id=template.id,
        new_values={"name": data["name"], "report_type": data["report_type"]},
        ip_address=ip_address,
        branch_id=data.get("branch_id"),
    )

    return _format_template(template)


async def list_templates(
    session: AsyncSession,
    branch_id: uuid.UUID | None = None,
    report_type: str | None = None,
    offset: int = 0,
    limit: int = 50,
):
    templates = await report_repository.list_templates(
        session, branch_id=branch_id, report_type=report_type,
        offset=offset, limit=limit,
    )
    return [_format_template(t) for t in templates]


async def create_job(
    session: AsyncSession,
    data: dict,
    current_user_id: uuid.UUID,
    ip_address: str | None = None,
):
    template = await report_repository.get_template(session, data["template_id"])
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report template not found",
        )

    output_format = data.get("output_format", "PDF").upper()
    if output_format not in VALID_OUTPUT_FORMATS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid output_format. Must be one of: {', '.join(sorted(VALID_OUTPUT_FORMATS))}",
        )

    parameters_json = None
    if data.get("parameters"):
        parameters_json = json.dumps(data["parameters"])

    now = datetime.now(timezone.utc)
    branch_id = data.get("branch_id")

    job = await report_repository.create_job(
        session,
        template_id=data["template_id"],
        parameters_json=parameters_json,
        job_status="PENDING",
        output_format=output_format,
        requested_by=current_user_id,
        requested_at=now,
        branch_id=branch_id,
    )

    await audit_service.log_action(
        session,
        user_id=current_user_id,
        action="CREATE",
        table_name="report_jobs",
        record_id=job.id,
        new_values={
            "template_id": str(data["template_id"]),
            "output_format": output_format,
        },
        ip_address=ip_address,
        branch_id=branch_id,
    )

    return _format_job(job)


async def get_job_status(
    session: AsyncSession,
    job_id: uuid.UUID,
):
    job = await report_repository.get_job(session, job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report job not found",
        )
    return _format_job(job)


async def list_jobs(
    session: AsyncSession,
    requested_by: uuid.UUID | None = None,
    branch_id: uuid.UUID | None = None,
    job_status: str | None = None,
    offset: int = 0,
    limit: int = 50,
):
    jobs = await report_repository.list_jobs(
        session,
        requested_by=requested_by,
        branch_id=branch_id,
        job_status=job_status,
        offset=offset,
        limit=limit,
    )
    return [_format_job(j) for j in jobs]


async def generate_report(session: AsyncSession, job_id: uuid.UUID):
    job = await report_repository.get_job(session, job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report job not found",
        )

    job = await report_repository.update_job(session, job, job_status="PROCESSING")

    try:
        template = await report_repository.get_template(session, job.template_id)
        if not template:
            raise ValueError("Report template not found")

        parameters = {}
        if job.parameters_json:
            parameters = json.loads(job.parameters_json)

        data = await _fetch_report_data(session, template.report_type, parameters)

        html_content = render_jinja_template(template.template_file, data)

        if job.output_format == "PDF":
            file_bytes = export_to_pdf(html_content)
            ext = "pdf"
        else:
            file_bytes = export_to_excel(data)
            ext = "xlsx"

        filename = f"{template.report_type.lower()}_{job.id}.{ext}"
        output_url = upload_to_storage(file_bytes, filename)

        now = datetime.now(timezone.utc)
        job = await report_repository.update_job(
            session, job,
            job_status="COMPLETED",
            output_url=output_url,
            completed_at=now,
        )

        await audit_service.log_action(
            session,
            user_id=job.requested_by,
            action="GENERATE",
            table_name="report_jobs",
            record_id=job.id,
            new_values={"status": "COMPLETED", "output_url": output_url},
            branch_id=job.branch_id,
        )

        return _format_job(job)

    except Exception as e:
        logger.error("Report generation failed for job %s: %s", job_id, str(e))
        job = await report_repository.update_job(
            session, job,
            job_status="FAILED",
            error_message=str(e),
        )
        return _format_job(job)


async def get_download_url(session: AsyncSession, job_id: uuid.UUID):
    job = await report_repository.get_job(session, job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report job not found",
        )
    if job.job_status != "COMPLETED" or not job.output_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Report is not ready for download",
        )
    return {"download_url": job.output_url, "output_format": job.output_format}


def render_jinja_template(template_file: str, data: dict) -> str:
    from jinja2 import Environment, FileSystemLoader

    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), autoescape=True)
    tmpl = env.get_template(template_file)
    return tmpl.render(**data)


def export_to_pdf(html_content: str) -> bytes:
    header = "%PDF-1.4 placeholder\n"
    return (header + html_content).encode("utf-8")


def export_to_excel(data: dict) -> bytes:
    try:
        from openpyxl import Workbook

        wb = Workbook()
        ws = wb.active
        ws.title = "Report"

        if "headers" in data and "rows" in data:
            ws.append(data["headers"])
            for row in data["rows"]:
                ws.append(row)
        else:
            ws.append(["Key", "Value"])
            for key, value in data.items():
                if not isinstance(value, (list, dict)):
                    ws.append([str(key), str(value)])

        buf = io.BytesIO()
        wb.save(buf)
        return buf.getvalue()
    except ImportError:
        return json.dumps(data, default=str).encode("utf-8")


def upload_to_storage(file_bytes: bytes, filename: str) -> str:
    REPORTS_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    filepath = REPORTS_OUTPUT_DIR / filename
    filepath.write_bytes(file_bytes)
    return str(filepath)


async def _fetch_report_data(
    session: AsyncSession, report_type: str, parameters: dict
) -> dict:
    if report_type == "REPORT_CARD":
        return await _fetch_report_card_data(session, parameters)
    elif report_type == "ATTENDANCE_REPORT":
        return await _fetch_attendance_report_data(session, parameters)
    elif report_type == "PRODUCTIVITY_REPORT":
        return await _fetch_productivity_report_data(session, parameters)
    elif report_type == "ANALYTICS_EXPORT":
        return await _fetch_analytics_export_data(session, parameters)
    return {"report_type": report_type, "parameters": parameters}


async def _fetch_report_card_data(
    session: AsyncSession, parameters: dict
) -> dict:
    from app.modules.analytics.models.analytics_models import AnalyticsStudentSummary
    from sqlalchemy import select

    student_id = parameters.get("student_id")
    if not student_id:
        return {"student_name": "N/A", "subjects": [], "batch_name": "N/A", "academic_year": "N/A"}

    result = await session.execute(
        select(AnalyticsStudentSummary).where(
            AnalyticsStudentSummary.student_id == uuid.UUID(student_id)
            if isinstance(student_id, str) else
            AnalyticsStudentSummary.student_id == student_id
        )
    )
    summary = result.scalar_one_or_none()

    if not summary:
        return {"student_name": "Unknown", "subjects": [], "batch_name": "N/A", "academic_year": "N/A"}

    return {
        "student_name": f"Student {student_id}",
        "batch_name": "N/A",
        "academic_year": "N/A",
        "attendance_percentage": float(summary.attendance_pct) if summary.attendance_pct else 0,
        "average_score": float(summary.avg_score) if summary.avg_score else 0,
        "subjects": [],
    }


async def _fetch_attendance_report_data(
    session: AsyncSession, parameters: dict
) -> dict:
    return {
        "report_title": "Attendance Report",
        "headers": ["Student", "Total Classes", "Present", "Absent", "Percentage"],
        "rows": [],
        "parameters": parameters,
    }


async def _fetch_productivity_report_data(
    session: AsyncSession, parameters: dict
) -> dict:
    return {
        "report_title": "Productivity Report",
        "headers": ["Teacher", "Lectures Conducted", "Avg Rating"],
        "rows": [],
        "parameters": parameters,
    }


async def _fetch_analytics_export_data(
    session: AsyncSession, parameters: dict
) -> dict:
    return {
        "report_title": "Analytics Export",
        "headers": ["Metric", "Value"],
        "rows": [],
        "parameters": parameters,
    }


def _format_template(t):
    config = None
    if t.config_json:
        try:
            config = json.loads(t.config_json)
        except (json.JSONDecodeError, TypeError):
            pass
    return {
        "id": t.id,
        "name": t.name,
        "report_type": t.report_type,
        "template_file": t.template_file,
        "config": config,
        "is_active": t.is_active,
        "branch_id": t.branch_id,
        "created_at": t.created_at,
        "updated_at": t.updated_at,
    }


def _format_job(j):
    parameters = None
    if j.parameters_json:
        try:
            parameters = json.loads(j.parameters_json)
        except (json.JSONDecodeError, TypeError):
            pass
    return {
        "id": j.id,
        "template_id": j.template_id,
        "parameters": parameters,
        "job_status": j.job_status,
        "output_url": j.output_url,
        "output_format": j.output_format,
        "requested_by": j.requested_by,
        "requested_at": j.requested_at,
        "completed_at": j.completed_at,
        "error_message": j.error_message,
        "branch_id": j.branch_id,
        "created_at": j.created_at,
    }
