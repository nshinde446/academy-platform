"""Batch-level access scoping for RBAC Phase 2 enforcement.

``require_roles`` is binary (role in list); it can't express "this Floor
Coordinator, these batches" or "this Accounts user, only granted attendance".
``BatchScope`` fills that gap. It is resolved LIVE from the DB per request (never
from the JWT) so a Manager's reassignment takes effect immediately.

Everything here no-ops when ``RBAC_ENFORCEMENT_ENABLED`` is off — the guards
return an unrestricted scope, so behaviour is byte-identical to before.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config.settings import get_settings
from app.core.database.session import get_db
from app.modules.auth.permissions.rbac import get_current_user
from app.modules.auth.repositories import access_repository

_MANAGER_ROLES = {"super_admin", "branch_admin"}
# Roles that already have UNRESTRICTED access to each feature today (besides
# Manager). Kept identical to the pre-Phase-2 require_roles lists so that, with
# enforcement OFF, these endpoints behave byte-for-byte as before.
_BASE_ROLES: dict[str, set[str]] = {
    "attendance": {"academic_head", "teacher"},
    "lectures": {"academic_head"},
}
Feature = Literal["attendance", "lectures"]


@dataclass(frozen=True)
class BatchScope:
    """Which batches the current user may act on for a feature.

    ``all`` = unrestricted within the branch (Managers, and non-scoped existing
    roles). Otherwise ``batch_ids`` is the explicit allow-set."""

    all: bool
    batch_ids: frozenset[uuid.UUID] = field(default_factory=frozenset)

    def allows(self, batch_id: uuid.UUID | None) -> bool:
        if self.all:
            return True
        return batch_id is not None and batch_id in self.batch_ids

    def require(self, batch_id: uuid.UUID | None) -> None:
        if not self.allows(batch_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not permitted for this batch",
            )

    def filter_arg(self) -> list[uuid.UUID] | None:
        """Batch-id list to pass into a list query, or None for unrestricted."""
        return None if self.all else list(self.batch_ids)


_UNRESTRICTED = BatchScope(all=True)


async def _accounts_attendance_scope(
    session: AsyncSession, user_id: uuid.UUID
) -> BatchScope:
    """Accounts users see attendance only where a Manager has granted it. A live
    branch-wide grant → unrestricted; batch grants → that set; none → denied."""
    grants = await access_repository.active_grants_for(
        session, user_id, datetime.now(timezone.utc)
    )
    if not grants:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Attendance access not granted",
        )
    if any(g.batch_id is None for g in grants):  # a branch-wide grant
        return _UNRESTRICTED
    return BatchScope(all=False, batch_ids=frozenset(g.batch_id for g in grants))


async def resolve_batch_scope(
    session: AsyncSession, current_user: dict, feature: Feature
) -> BatchScope:
    """Authorise + scope in one place — this is the SOLE gate on scoped endpoints.

    With enforcement OFF: only Manager + today's base roles pass (unrestricted);
    the new roles are denied, exactly as before this change. With enforcement ON:
    Floor Coordinators are narrowed to their assigned batches and Accounts users
    to their granted attendance."""
    roles = set(current_user.get("roles", []))
    if _MANAGER_ROLES & roles:  # Manager — always unrestricted, both flag states
        return _UNRESTRICTED
    if _BASE_ROLES[feature] & roles:  # roles that already had full access
        return _UNRESTRICTED

    if not get_settings().RBAC_ENFORCEMENT_ENABLED:
        # Inert: new roles don't get access until enforcement is switched on.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role"
        )

    if "floor_coordinator" in roles:
        ids = await access_repository.assigned_batch_ids(
            session, current_user["user_id"]
        )
        return BatchScope(all=False, batch_ids=frozenset(ids))
    if feature == "attendance" and "accounts" in roles:
        return await _accounts_attendance_scope(session, current_user["user_id"])

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role"
    )


async def require_lecture_in_scope(
    session: AsyncSession, scope: "BatchScope", lecture_id: uuid.UUID
) -> None:
    """Assert the caller may act on this lecture — i.e. its batch is in scope.
    A Manager / unrestricted caller passes without a lookup."""
    if scope.all:
        return
    from app.modules.lectures.models.lecture_models import Lecture

    res = await session.execute(
        select(Lecture.batch_id).where(
            Lecture.id == lecture_id,
            Lecture.is_deleted == False,  # noqa: E712
        )
    )
    scope.require(res.scalar_one_or_none())


async def require_student_in_scope(
    session: AsyncSession, scope: "BatchScope", student_id: uuid.UUID
) -> None:
    """Assert the caller may see this student — i.e. the student belongs to at
    least one batch in scope. Manager / unrestricted passes without a lookup."""
    if scope.all:
        return
    from app.modules.student.models.student_models import StudentBatchMapping

    res = await session.execute(
        select(StudentBatchMapping.batch_id).where(
            StudentBatchMapping.student_id == student_id,
            StudentBatchMapping.is_deleted == False,  # noqa: E712
        )
    )
    student_batches = {r[0] for r in res.all()}
    if not (student_batches & scope.batch_ids):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not permitted for this student",
        )


def require_batch_scope(feature: Feature):
    """FastAPI dependency yielding the caller's BatchScope for a feature."""

    async def dependency(
        current_user: dict = Depends(get_current_user),
        session: AsyncSession = Depends(get_db),
    ) -> BatchScope:
        return await resolve_batch_scope(session, current_user, feature)

    return dependency
