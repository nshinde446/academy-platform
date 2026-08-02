"""Orchestration for downloadable attendance reports.

Fetches the data (via daily_service + name lookups) and hands it to the pure
builders in attendance_export_service, returning (filename, bytes, media_type)
ready for a streaming Response. Three scopes × two formats.
"""

from __future__ import annotations

import re
import uuid
from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config.settings import get_settings
from app.modules.attendance.services import daily_service
from app.modules.attendance.services import attendance_export_service as ex
from app.modules.batch.models.batch_models import Batch
from app.modules.student.models.student_models import Student

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
PDF_MIME = "application/pdf"


def _slug(s: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower() or "report"


def _check_fmt(fmt: str) -> str:
    if fmt not in ("xlsx", "pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="format must be xlsx or pdf",
        )
    return fmt


async def student_report(
    session: AsyncSession, *, student_id: uuid.UUID, branch_id: uuid.UUID,
    start: date, end: date, fmt: str,
) -> tuple[str, bytes, str]:
    _check_fmt(fmt)
    student = (await session.execute(
        select(Student).where(Student.id == student_id, Student.branch_id == branch_id)
    )).scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    name = f"{student.first_name} {student.last_name}".strip()
    tz = await daily_service.branch_timezone(session, branch_id)
    summary = await daily_service.monthly_summary(
        session, student_id=student_id, branch_id=branch_id, start=start, end=end, tz_name=tz,
    )
    timeline = await daily_service.student_timeline(
        session, student_id=student_id, branch_id=branch_id, start=start, end=end,
    )
    brand = get_settings().ACADEMY_BRAND_NAME
    base = f"attendance-{_slug(name)}-{start}-{end}"

    if fmt == "xlsx":
        data = ex.student_xlsx(
            brand=brand, student_name=name, start=start, end=end,
            summary=summary, timeline=timeline, tz_name=tz,
        )
        return f"{base}.xlsx", data, XLSX_MIME
    html = ex.student_html(
        brand=brand, student_name=name, start=start, end=end,
        summary=summary, timeline=timeline, tz_name=tz,
    )
    return f"{base}.pdf", await ex.render_html_to_pdf(html), PDF_MIME


async def batch_report(
    session: AsyncSession, *, batch_id: uuid.UUID, branch_id: uuid.UUID,
    start: date, end: date, fmt: str,
) -> tuple[str, bytes, str]:
    _check_fmt(fmt)
    batch = (await session.execute(
        select(Batch).where(Batch.id == batch_id, Batch.branch_id == branch_id)
    )).scalar_one_or_none()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    tz = await daily_service.branch_timezone(session, branch_id)
    matrix = await daily_service.batch_matrix(
        session, branch_id=branch_id, batch_id=batch_id, start=start, end=end, tz_name=tz,
    )
    brand = get_settings().ACADEMY_BRAND_NAME
    base = f"attendance-{_slug(batch.name)}-{start}-{end}"

    if fmt == "xlsx":
        data = ex.batch_xlsx(
            brand=brand, batch_name=batch.name, start=start, end=end, matrix=matrix,
        )
        return f"{base}.xlsx", data, XLSX_MIME
    html = ex.batch_html(
        brand=brand, batch_name=batch.name, start=start, end=end, matrix=matrix,
    )
    return f"{base}.pdf", await ex.render_html_to_pdf(html, landscape=True), PDF_MIME


async def daily_ledger_report(
    session: AsyncSession, *, branch_id: uuid.UUID, start: date, end: date, fmt: str,
) -> tuple[str, bytes, str]:
    """The immutable all-students daily ledger — every student's per-day record
    over the range, batch-independent (survives batch/subject/profile changes)."""
    _check_fmt(fmt)
    tz = await daily_service.branch_timezone(session, branch_id)
    ledger = await daily_service.daily_ledger(
        session, branch_id=branch_id, start=start, end=end,
    )
    brand = get_settings().ACADEMY_BRAND_NAME
    base = f"attendance-daily-ledger-{start}-{end}"

    if fmt == "xlsx":
        data = ex.daily_ledger_xlsx(
            brand=brand, start=start, end=end, ledger=ledger, tz_name=tz,
        )
        return f"{base}.xlsx", data, XLSX_MIME
    html = ex.daily_ledger_html(
        brand=brand, start=start, end=end, ledger=ledger, tz_name=tz,
    )
    return f"{base}.pdf", await ex.render_html_to_pdf(html, landscape=True), PDF_MIME


async def all_batches_report(
    session: AsyncSession, *, branch_id: uuid.UUID, start: date, end: date, fmt: str,
) -> tuple[str, bytes, str]:
    _check_fmt(fmt)
    tz = await daily_service.branch_timezone(session, branch_id)
    batches = (await session.execute(
        select(Batch).where(Batch.branch_id == branch_id, Batch.is_deleted == False)
        .order_by(Batch.name)
    )).scalars().all()

    summaries: list[dict] = []
    matrices: dict[str, dict] = {}
    batch_names: dict[str, str] = {}
    for b in batches:
        m = await daily_service.batch_matrix(
            session, branch_id=branch_id, batch_id=b.id, start=start, end=end, tz_name=tz,
        )
        key = str(b.id)
        matrices[key] = m
        batch_names[key] = b.name
        total = m["student_count"] * len(m["dates"])
        present = sum(r["present"] for r in m["students"])
        summaries.append({
            "batch_name": b.name,
            "batch_code": b.code,
            "student_count": m["student_count"],
            "working_days": len(m["dates"]),
            "present": present,
            "total_slots": total,
            "avg_pct": round(present / total * 100, 1) if total else 0.0,
        })

    brand = get_settings().ACADEMY_BRAND_NAME
    base = f"attendance-all-batches-{start}-{end}"

    if fmt == "xlsx":
        data = ex.all_batches_xlsx(
            brand=brand, start=start, end=end,
            summaries=summaries, matrices=matrices, batch_names=batch_names,
        )
        return f"{base}.xlsx", data, XLSX_MIME
    html = ex.all_batches_html(brand=brand, start=start, end=end, summaries=summaries)
    return f"{base}.pdf", await ex.render_html_to_pdf(html), PDF_MIME
