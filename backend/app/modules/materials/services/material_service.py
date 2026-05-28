"""Materials service — orchestrates storage backend + DB repo.

Upload flow:
1. Compute sha256 of incoming bytes.
2. Check for an existing non-deleted material with the same sha256 +
   branch — if found, return it instead of creating a duplicate.
3. Build the canonical storage_key from material metadata.
4. Write bytes to storage. Insert the DB row. Link batches.
5. Audit-log + return the freshly fetched row.

Other operations (list, get, update, delete, ingest) are thin wrappers
around the repo with audit logging where state changes.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.storage import (
    StorageBackend,
    build_storage_key,
    compute_sha256,
)
from app.modules.academic.models.academic_models import AcademicYear, Subject
from app.modules.audit.services import audit_service
from app.modules.materials.models.material_models import Material
from app.modules.materials.repositories import material_repository
from app.modules.materials.schemas.material_schemas import (
    ALLOWED_CLASS_LABELS,
    MaterialUpdate,
    MaterialUploadMetadata,
)


def _slugify_subject(subject: Subject) -> str:
    """Storage-key segment for a subject. Stable and human-readable."""
    return subject.code.lower().strip().replace(" ", "-")


def _academic_year_code(ay: AcademicYear) -> str:
    """Storage-key segment for an academic year. ``2026-27`` from
    start_year=2026/end_year=2027."""
    return f"{ay.start_year}-{ay.end_year % 100:02d}"


async def upload_material(
    session: AsyncSession,
    *,
    file_bytes: bytes,
    filename: str,
    mime_type: str,
    meta: MaterialUploadMetadata,
    branch_id: uuid.UUID,
    current_user_id: uuid.UUID,
    storage: StorageBackend,
    ip_address: str | None = None,
) -> Material:
    if meta.class_label not in ALLOWED_CLASS_LABELS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"class_label must be one of {sorted(ALLOWED_CLASS_LABELS)}; "
                f"got {meta.class_label!r}"
            ),
        )
    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Empty upload."
        )

    sha = compute_sha256(file_bytes)

    existing = await material_repository.get_by_sha256(session, sha, branch_id)
    if existing is not None:
        # Idempotent on content. Update batch links if the caller asked
        # for any (lets re-upload-as-link work cleanly), but don't
        # rewrite metadata.
        if meta.batch_ids:
            await material_repository.set_batch_links(
                session, existing.id, meta.batch_ids, current_user_id
            )
        return existing

    # Resolve subject + academic year for the storage path.
    subject = (
        await session.execute(
            select(Subject).where(
                Subject.id == meta.subject_id,
                Subject.is_deleted == False,
            )
        )
    ).scalar_one_or_none()
    if subject is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Subject {meta.subject_id} not found",
        )
    ay = (
        await session.execute(
            select(AcademicYear).where(
                AcademicYear.id == meta.academic_year_id,
                AcademicYear.is_deleted == False,
            )
        )
    ).scalar_one_or_none()
    if ay is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Academic year {meta.academic_year_id} not found",
        )

    material_id = uuid.uuid4()
    storage_key = build_storage_key(
        material_id=str(material_id),
        academic_year_code=_academic_year_code(ay),
        class_label=meta.class_label,
        subject_slug=_slugify_subject(subject),
        category=meta.category.value,
        filename=filename,
    )

    storage.write(storage_key, file_bytes)

    material = await material_repository.create(
        session,
        id=material_id,
        filename=filename,
        storage_key=storage_key,
        mime_type=mime_type,
        size_bytes=len(file_bytes),
        sha256=sha,
        academic_year_id=meta.academic_year_id,
        class_label=meta.class_label,
        subject_id=meta.subject_id,
        topic=meta.topic,
        category=meta.category.value,
        exam_types=[et.value for et in meta.exam_types],
        description=meta.description,
        ingest_status="uploaded",
        question_count=0,
        branch_id=branch_id,
        created_by=current_user_id,
    )

    if meta.batch_ids:
        await material_repository.set_batch_links(
            session, material.id, meta.batch_ids, current_user_id
        )

    await audit_service.log_action(
        session,
        user_id=current_user_id,
        action="CREATE",
        table_name="materials",
        record_id=material.id,
        new_values={
            "filename": filename,
            "category": meta.category.value,
            "class_label": meta.class_label,
            "sha256": sha,
            "size_bytes": len(file_bytes),
        },
        ip_address=ip_address,
        branch_id=branch_id,
    )
    return material


async def get_material(
    session: AsyncSession, material_id: uuid.UUID, branch_id: uuid.UUID
) -> Material:
    m = await material_repository.get_by_id(session, material_id, branch_id)
    if m is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Material not found"
        )
    return m


async def list_materials(
    session: AsyncSession,
    *,
    branch_id: uuid.UUID,
    academic_year_id: uuid.UUID | None = None,
    class_label: str | None = None,
    subject_id: uuid.UUID | None = None,
    category: str | None = None,
    exam_type: str | None = None,
    batch_id: uuid.UUID | None = None,
    search: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[Material], int]:
    return await material_repository.list_filtered(
        session,
        branch_id=branch_id,
        academic_year_id=academic_year_id,
        class_label=class_label,
        subject_id=subject_id,
        category=category,
        exam_type=exam_type,
        batch_id=batch_id,
        search=search,
        offset=offset,
        limit=limit,
    )


async def update_material(
    session: AsyncSession,
    material_id: uuid.UUID,
    body: MaterialUpdate,
    branch_id: uuid.UUID,
    current_user_id: uuid.UUID,
    ip_address: str | None = None,
) -> Material:
    m = await get_material(session, material_id, branch_id)

    if body.class_label is not None and body.class_label not in ALLOWED_CLASS_LABELS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid class_label {body.class_label!r}",
        )

    updates: dict[str, Any] = {}
    if body.class_label is not None:
        updates["class_label"] = body.class_label
    if body.subject_id is not None:
        updates["subject_id"] = body.subject_id
    if body.category is not None:
        updates["category"] = body.category.value
    if body.exam_types is not None:
        updates["exam_types"] = [et.value for et in body.exam_types]
    if body.topic is not None:
        updates["topic"] = body.topic
    if body.description is not None:
        updates["description"] = body.description
    if updates:
        updates["updated_by"] = current_user_id
        await material_repository.update(session, m, **updates)

    if body.batch_ids is not None:
        await material_repository.set_batch_links(
            session, m.id, body.batch_ids, current_user_id
        )

    await audit_service.log_action(
        session,
        user_id=current_user_id,
        action="UPDATE",
        table_name="materials",
        record_id=m.id,
        new_values=updates,
        ip_address=ip_address,
        branch_id=branch_id,
    )
    return m


async def delete_material(
    session: AsyncSession,
    material_id: uuid.UUID,
    branch_id: uuid.UUID,
    current_user_id: uuid.UUID,
    storage: StorageBackend,
    ip_address: str | None = None,
) -> None:
    m = await get_material(session, material_id, branch_id)
    storage_key = m.storage_key
    await material_repository.soft_delete(session, m)
    # File stays on disk in M1; admin can purge via a future cleanup
    # job. Soft-delete first means audit + recoverability.
    await audit_service.log_action(
        session,
        user_id=current_user_id,
        action="DELETE",
        table_name="materials",
        record_id=m.id,
        old_values={"filename": m.filename, "storage_key": storage_key},
        ip_address=ip_address,
        branch_id=branch_id,
    )


async def start_ingest(
    session: AsyncSession,
    material_id: uuid.UUID,
    branch_id: uuid.UUID,
    current_user_id: uuid.UUID,
    ip_address: str | None = None,
) -> Material:
    """Mark the material as ingesting and return it. The actual PDF →
    questions extraction runs as a BackgroundTask (see ingest_service)
    because it makes many Gemini Vision calls and can take minutes.

    Guards against double-runs: if an ingest is already in flight, 409.
    """
    m = await get_material(session, material_id, branch_id)

    if m.ingest_status == "ingesting":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ingest already in progress for this material.",
        )

    await material_repository.update(
        session,
        m,
        ingest_status="ingesting",
        ingest_error=None,
        updated_by=current_user_id,
    )

    await audit_service.log_action(
        session,
        user_id=current_user_id,
        action="UPDATE",
        table_name="materials",
        record_id=m.id,
        new_values={"ingest_status": "ingesting"},
        ip_address=ip_address,
        branch_id=branch_id,
    )
    # The UPDATE above fires server-side onupdate=now() on updated_at,
    # which SQLAlchemy expires after flush. Refresh in-context so
    # FastAPI's response serialization reads loaded attributes instead
    # of triggering a lazy load outside the async greenlet (which raises
    # MissingGreenlet during serialization).
    await session.refresh(m)
    return m
