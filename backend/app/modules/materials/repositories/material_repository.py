import uuid
from collections import defaultdict
from typing import Any

from sqlalchemy import and_, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.batch.models.batch_models import Batch
from app.modules.materials.models.material_models import Material, MaterialBatch


async def create(session: AsyncSession, **kwargs: Any) -> Material:
    m = Material(**kwargs)
    session.add(m)
    await session.flush()
    return m


async def get_by_id(
    session: AsyncSession, material_id: uuid.UUID, branch_id: uuid.UUID
) -> Material | None:
    result = await session.execute(
        select(Material).where(
            Material.id == material_id,
            Material.branch_id == branch_id,
            Material.is_deleted == False,
        )
    )
    return result.scalar_one_or_none()


async def get_by_sha256(
    session: AsyncSession, sha256: str, branch_id: uuid.UUID
) -> Material | None:
    """Dedup lookup. Soft-deleted matches are excluded so a re-upload
    after delete creates a fresh row (intentional)."""
    result = await session.execute(
        select(Material).where(
            Material.sha256 == sha256,
            Material.branch_id == branch_id,
            Material.is_deleted == False,
        )
    )
    return result.scalar_one_or_none()


def _list_filters(
    *,
    branch_id: uuid.UUID,
    academic_year_id: uuid.UUID | None,
    class_label: str | None,
    subject_id: uuid.UUID | None,
    category: str | None,
    exam_type: str | None,
    search: str | None,
):
    clauses = [Material.branch_id == branch_id, Material.is_deleted == False]
    if academic_year_id is not None:
        clauses.append(Material.academic_year_id == academic_year_id)
    if class_label:
        clauses.append(Material.class_label == class_label)
    if subject_id is not None:
        clauses.append(Material.subject_id == subject_id)
    if category:
        clauses.append(Material.category == category)
    if exam_type:
        # Postgres ARRAY contains operator
        clauses.append(Material.exam_types.any(exam_type))
    if search:
        ilike = f"%{search}%"
        clauses.append(
            (Material.filename.ilike(ilike)) | (Material.topic.ilike(ilike))
        )
    return and_(*clauses)


async def list_filtered(
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
    where = _list_filters(
        branch_id=branch_id,
        academic_year_id=academic_year_id,
        class_label=class_label,
        subject_id=subject_id,
        category=category,
        exam_type=exam_type,
        search=search,
    )
    stmt = select(Material).where(where)
    if batch_id is not None:
        stmt = stmt.join(
            MaterialBatch, MaterialBatch.material_id == Material.id
        ).where(MaterialBatch.batch_id == batch_id)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await session.execute(count_stmt)).scalar_one()

    stmt = stmt.order_by(Material.created_at.desc()).offset(offset).limit(limit)
    rows = (await session.execute(stmt)).scalars().all()
    return list(rows), total


async def update(session: AsyncSession, material: Material, **kwargs: Any) -> Material:
    for k, v in kwargs.items():
        setattr(material, k, v)
    await session.flush()
    return material


async def soft_delete(session: AsyncSession, material: Material) -> None:
    material.is_deleted = True
    await session.flush()


async def set_batch_links(
    session: AsyncSession,
    material_id: uuid.UUID,
    batch_ids: list[uuid.UUID],
    linked_by: uuid.UUID,
) -> None:
    """Replace the material's batch link set. Idempotent."""
    await session.execute(
        delete(MaterialBatch).where(MaterialBatch.material_id == material_id)
    )
    for bid in batch_ids:
        session.add(
            MaterialBatch(material_id=material_id, batch_id=bid, linked_by=linked_by)
        )
    await session.flush()


async def get_batch_ids(
    session: AsyncSession, material_id: uuid.UUID
) -> list[uuid.UUID]:
    rows = (
        await session.execute(
            select(MaterialBatch.batch_id).where(MaterialBatch.material_id == material_id)
        )
    ).all()
    return [r[0] for r in rows]


# ── Facet counts ───────────────────────────────────────────────────────────

async def facet_counts(
    session: AsyncSession,
    *,
    branch_id: uuid.UUID,
    base_filters: dict[str, Any],
) -> dict[str, list[tuple[str, int]]]:
    """For each facet dimension, return (value, count) pairs. The
    counts reflect the *other* active filters — the facet's own
    selection is excluded from its own query so users can see what
    they'd switch to."""
    facets: dict[str, list[tuple[str, int]]] = {}

    def _where_excluding(exclude: str):
        return _list_filters(
            branch_id=branch_id,
            academic_year_id=base_filters.get("academic_year_id"),
            class_label=base_filters.get("class_label") if exclude != "class" else None,
            subject_id=base_filters.get("subject_id") if exclude != "subject" else None,
            category=base_filters.get("category") if exclude != "category" else None,
            exam_type=base_filters.get("exam_type") if exclude != "exam_type" else None,
            search=base_filters.get("search"),
        )

    # Class
    rows = (await session.execute(
        select(Material.class_label, func.count(Material.id))
        .where(_where_excluding("class"))
        .group_by(Material.class_label)
    )).all()
    facets["classes"] = [(r[0], r[1]) for r in rows]

    # Subject (return raw uuids; route formats with subject.code/name)
    rows = (await session.execute(
        select(Material.subject_id, func.count(Material.id))
        .where(_where_excluding("subject"))
        .group_by(Material.subject_id)
    )).all()
    facets["subjects"] = [(str(r[0]), r[1]) for r in rows]

    # Category
    rows = (await session.execute(
        select(Material.category, func.count(Material.id))
        .where(_where_excluding("category"))
        .group_by(Material.category)
    )).all()
    facets["categories"] = [(r[0], r[1]) for r in rows]

    # Exam types — Postgres ARRAY has unnest() but SQLite (test DB) doesn't,
    # so pull arrays into Python and aggregate. The dataset is small enough
    # that this is fine; switch back to unnest+GROUP BY in a follow-up
    # once tests use Postgres.
    arr_rows = (await session.execute(
        select(Material.exam_types).where(_where_excluding("exam_type"))
    )).all()
    et_counts: dict[str, int] = defaultdict(int)
    for (arr,) in arr_rows:
        for et in (arr or []):
            et_counts[et] += 1
    facets["exam_types"] = list(et_counts.items())

    # Batches — only includes materials with at least one batch link
    batch_rows = (await session.execute(
        select(MaterialBatch.batch_id, func.count(MaterialBatch.material_id))
        .join(Material, Material.id == MaterialBatch.material_id)
        .where(_where_excluding("batch"))
        .group_by(MaterialBatch.batch_id)
    )).all()
    facets["batches"] = [(str(r[0]), r[1]) for r in batch_rows]

    return facets


async def refresh_question_count(
    session: AsyncSession, material_id: uuid.UUID
) -> int:
    """Recompute denormalized question_count for one material."""
    from app.modules.tests.models.test_models import Question

    count = (await session.execute(
        select(func.count(Question.id)).where(
            Question.material_id == material_id,
            Question.is_deleted == False,
        )
    )).scalar_one()

    await session.execute(
        Material.__table__.update()
        .where(Material.id == material_id)
        .values(question_count=count)
    )
    return count
