import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.base import BaseModel


class ReportTemplate(BaseModel):
    __tablename__ = "report_templates"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    report_type: Mapped[str] = mapped_column(String(50), nullable=False)
    template_file: Mapped[str] = mapped_column(String(255), nullable=False)
    config_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    branch_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("branch.id"), nullable=True
    )


class ReportJob(BaseModel):
    __tablename__ = "report_jobs"

    template_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("report_templates.id"), nullable=False
    )
    parameters_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    job_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="PENDING"
    )
    output_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    output_format: Mapped[str] = mapped_column(String(10), nullable=False, default="PDF")
    requested_by: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=False
    )
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    branch_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("branch.id"), nullable=True
    )
