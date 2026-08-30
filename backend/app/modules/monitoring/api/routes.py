"""Developer monitoring endpoint. Email-gated (settings.DEVELOPER_EMAILS) — no
role qualifies, only the listed developer(s)."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.modules.auth.permissions.rbac import require_developer
from app.modules.monitoring.services import monitoring_service

router = APIRouter(prefix="/dev", tags=["dev-monitoring"])


@router.get("/monitoring")
async def dev_monitoring(
    _dev: dict = Depends(require_developer),
    session: AsyncSession = Depends(get_db),
):
    """Whole-institute health snapshot: system size, device connectivity,
    attendance freshness, backup status, command queue, and active alerts."""
    return await monitoring_service.dev_snapshot(session)
