"""BioMax webhook + manual import endpoints.

POST /api/v1/attendance/biomax/webhook
    Receives push events from BioMax cloud. PLACEHOLDER signature
    verification — fill in once vendor docs land. Today it just
    validates a shared secret header.

POST /api/v1/attendance/biomax/import
    Manual punch import — accepts a JSON list of normalized
    ``PunchEvent`` and writes them through the same service. Useful
    for backfilling historical data exported as CSV from the BioMax
    device, or for testing the rest of the attendance pipeline
    without the live integration wired up.
"""

import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, Header, Query, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.modules.attendance.integrations.biomax.schemas import (
    IngestResult,
    PunchEvent,
    parse_biomax_webhook_payload,
)
from app.modules.attendance.integrations.biomax.service import ingest_punches
from app.modules.auth.permissions.rbac import require_roles


router = APIRouter(prefix="/attendance/biomax", tags=["attendance"])


class ManualImportBody(BaseModel):
    events: list[PunchEvent]


def _verify_webhook_secret(provided: str | None) -> None:
    """PLACEHOLDER — proper auth depends on what BioMax sends.

    Common patterns:
    - Static shared secret in a custom header (what this does).
    - HMAC of the body signed with a shared key (more secure; switch
      once we know the vendor uses it).
    - Source-IP allowlist (less reliable; their cloud may relay).

    Today: compare against env BIOMAX_WEBHOOK_SECRET. If unset, reject
    everything (fail-safe — we'd rather drop events than accept spoofed
    ones).
    """
    expected = os.environ.get("BIOMAX_WEBHOOK_SECRET", "")
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Webhook secret not configured. Set BIOMAX_WEBHOOK_SECRET.",
        )
    if not provided or provided != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing webhook secret",
        )


@router.post("/webhook", response_model=IngestResult)
async def biomax_webhook(
    request: Request,
    branch_id: uuid.UUID = Query(...),
    x_biomax_secret: str | None = Header(None),
    session: AsyncSession = Depends(get_db),
):
    """Receive push events from BioMax cloud. Vendor-specific payload
    parsing lives in ``parse_biomax_webhook_payload``."""
    _verify_webhook_secret(x_biomax_secret)

    body = await request.json()
    events = parse_biomax_webhook_payload(body)
    return await ingest_punches(session, events, branch_id)


@router.post("/import", response_model=IngestResult)
async def manual_import(
    body: ManualImportBody,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin"])),
    session: AsyncSession = Depends(get_db),
):
    """Admin-only manual import. Accepts a JSON list of normalized
    ``PunchEvent`` objects. Useful for CSV backfills (parse CSV
    client-side, POST as JSON) and for testing the ingestion + dedup
    paths without a live device."""
    return await ingest_punches(session, body.events, branch_id)
