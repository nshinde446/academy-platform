"""Ops/monitoring models. BackupRun records each DB backup run so the
developer dashboard can show freshness + off-box status. Written by the on-box
backup script (infra/scripts/db-backup.sh), read by the /dev endpoint."""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database.base import Base


class BackupRun(Base):
    __tablename__ = "backup_runs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # ok | failed
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    # off-box copy outcome: ok | failed | skipped
    offbox: Mapped[str] = mapped_column(String(20), nullable=False, default="skipped")
    filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
