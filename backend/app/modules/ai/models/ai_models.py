import uuid

from sqlalchemy import Boolean, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.base import BaseModel


VALID_REQUEST_TYPES = {"QUESTION_GENERATION", "RECOMMENDATION", "TUTOR", "DPP_GENERATION"}
VALID_REQUEST_STATUSES = {"PENDING", "PROCESSING", "COMPLETED", "FAILED"}


class AIRequest(BaseModel):
    __tablename__ = "ai_requests"

    request_type: Mapped[str] = mapped_column(String(30), nullable=False)
    request_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="PENDING"
    )
    payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    requested_by: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=False
    )
    branch_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("branch.id"), nullable=True
    )


class AIServiceConfig(BaseModel):
    __tablename__ = "ai_service_config"

    service_name: Mapped[str] = mapped_column(String(50), nullable=False)
    config_key: Mapped[str] = mapped_column(String(100), nullable=False)
    config_value: Mapped[str] = mapped_column(Text, nullable=False)
    is_secret: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    branch_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("branch.id"), nullable=True
    )
