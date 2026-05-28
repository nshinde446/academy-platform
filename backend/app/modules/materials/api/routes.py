import uuid

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.storage import StorageBackend, get_storage_backend
from app.modules.auth.permissions.rbac import get_current_user, require_roles
from app.modules.materials.repositories import material_repository
from app.modules.materials.schemas.material_schemas import (
    ExamType,
    FacetBucket,
    MaterialCategory,
    MaterialFacetCounts,
    MaterialListResponse,
    MaterialResponse,
    MaterialUpdate,
    MaterialUploadMetadata,
)
from app.modules.materials.services import ingest_service, material_service


router = APIRouter(prefix="/materials", tags=["materials"])


def _parse_csv_uuids(raw: str | None) -> list[uuid.UUID]:
    if not raw:
        return []
    out: list[uuid.UUID] = []
    for tok in raw.split(","):
        tok = tok.strip()
        if not tok:
            continue
        try:
            out.append(uuid.UUID(tok))
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Bad UUID in list: {tok!r}",
            ) from exc
    return out


def _parse_csv_enum(raw: str | None, enum_cls) -> list:
    if not raw:
        return []
    out = []
    for tok in raw.split(","):
        tok = tok.strip()
        if not tok:
            continue
        try:
            out.append(enum_cls(tok))
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Bad value {tok!r} (allowed: {[e.value for e in enum_cls]})",
            ) from exc
    return out


@router.post("", response_model=MaterialResponse, status_code=status.HTTP_201_CREATED)
async def upload_material(
    request: Request,
    file: UploadFile = File(...),
    academic_year_id: uuid.UUID = Form(...),
    class_label: str = Form(...),
    subject_id: uuid.UUID = Form(...),
    category: MaterialCategory = Form(...),
    # Comma-separated lists keep the multipart payload simple. Parsed
    # below into proper types before handing to the service.
    exam_types: str | None = Form(None),
    batch_ids: str | None = Form(None),
    topic: str | None = Form(None),
    description: str | None = Form(None),
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin"])),
    session: AsyncSession = Depends(get_db),
    storage: StorageBackend = Depends(get_storage_backend),
):
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty."
        )
    meta = MaterialUploadMetadata(
        academic_year_id=academic_year_id,
        class_label=class_label,
        subject_id=subject_id,
        category=category,
        exam_types=_parse_csv_enum(exam_types, ExamType),
        batch_ids=_parse_csv_uuids(batch_ids),
        topic=topic,
        description=description,
    )

    material = await material_service.upload_material(
        session,
        file_bytes=file_bytes,
        filename=file.filename or "unnamed",
        mime_type=file.content_type or "application/octet-stream",
        meta=meta,
        branch_id=branch_id,
        current_user_id=current_user["user_id"],
        storage=storage,
        ip_address=request.client.host if request.client else None,
    )
    return material


@router.get("", response_model=MaterialListResponse)
async def list_materials(
    branch_id: uuid.UUID = Query(...),
    academic_year_id: uuid.UUID | None = Query(None),
    class_label: str | None = Query(None),
    subject_id: uuid.UUID | None = Query(None),
    category: MaterialCategory | None = Query(None),
    exam_type: ExamType | None = Query(None),
    batch_id: uuid.UUID | None = Query(None),
    search: str | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    items, total = await material_service.list_materials(
        session,
        branch_id=branch_id,
        academic_year_id=academic_year_id,
        class_label=class_label,
        subject_id=subject_id,
        category=category.value if category else None,
        exam_type=exam_type.value if exam_type else None,
        batch_id=batch_id,
        search=search,
        offset=offset,
        limit=limit,
    )
    return MaterialListResponse(items=items, total=total)


@router.get("/facets", response_model=MaterialFacetCounts)
async def list_facets(
    branch_id: uuid.UUID = Query(...),
    academic_year_id: uuid.UUID | None = Query(None),
    class_label: str | None = Query(None),
    subject_id: uuid.UUID | None = Query(None),
    category: MaterialCategory | None = Query(None),
    exam_type: ExamType | None = Query(None),
    search: str | None = Query(None),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    facets = await material_repository.facet_counts(
        session,
        branch_id=branch_id,
        base_filters={
            "academic_year_id": academic_year_id,
            "class_label": class_label,
            "subject_id": subject_id,
            "category": category.value if category else None,
            "exam_type": exam_type.value if exam_type else None,
            "search": search,
        },
    )
    return MaterialFacetCounts(
        classes=[FacetBucket(value=v, count=c) for v, c in facets["classes"]],
        subjects=[FacetBucket(value=v, count=c) for v, c in facets["subjects"]],
        categories=[FacetBucket(value=v, count=c) for v, c in facets["categories"]],
        exam_types=[FacetBucket(value=v, count=c) for v, c in facets["exam_types"]],
        batches=[FacetBucket(value=v, count=c) for v, c in facets["batches"]],
    )


@router.get("/{material_id}", response_model=MaterialResponse)
async def get_material(
    material_id: uuid.UUID,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    return await material_service.get_material(session, material_id, branch_id)


@router.patch("/{material_id}", response_model=MaterialResponse)
async def update_material(
    material_id: uuid.UUID,
    body: MaterialUpdate,
    request: Request,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin"])),
    session: AsyncSession = Depends(get_db),
):
    return await material_service.update_material(
        session,
        material_id,
        body,
        branch_id,
        current_user["user_id"],
        request.client.host if request.client else None,
    )


@router.post("/{material_id}/ingest", response_model=MaterialResponse)
async def ingest_material(
    material_id: uuid.UUID,
    request: Request,
    background_tasks: BackgroundTasks,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin"])),
    session: AsyncSession = Depends(get_db),
):
    # Flip status to "ingesting" synchronously, then run the heavy
    # PDF → questions extraction after the response returns. The
    # background task opens its own DB session.
    material = await material_service.start_ingest(
        session,
        material_id,
        branch_id,
        current_user["user_id"],
        request.client.host if request.client else None,
    )
    background_tasks.add_task(
        ingest_service.extract_and_store, material_id, branch_id
    )
    return material


@router.delete("/{material_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_material(
    material_id: uuid.UUID,
    request: Request,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin"])),
    session: AsyncSession = Depends(get_db),
    storage: StorageBackend = Depends(get_storage_backend),
):
    await material_service.delete_material(
        session,
        material_id,
        branch_id,
        current_user["user_id"],
        storage,
        request.client.host if request.client else None,
    )
