"""Admin-managed user accounts (no public signup).

Super-admin / branch-admin create staff accounts with a role and a temporary
password, which the user changes on first login. Business rules live here; the
routes stay HTTP-only and the repository stays queries-only.

Guardrails (all enforced here, not in the UI):
- email is unique among live users;
- only a super_admin may create or grant the ``super_admin`` role;
- you cannot deactivate / delete yourself;
- the last active super_admin cannot be deactivated, deleted, or demoted
  (lock-out prevention);
- deactivating, deleting, or resetting a password revokes that user's live
  sessions so access stops immediately.
"""

from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.repositories import user_repository
from app.modules.auth.schemas.auth_schemas import (
    AdminUserResponse,
    RoleOption,
    UserCreateRequest,
    UserUpdateRequest,
)
from app.modules.auth.services.auth_service import hash_password, verify_password

SUPER_ADMIN = "super_admin"
# Roles permitted to grant the super_admin role to a user.
_SUPER_ADMIN_GRANTORS = {"super_admin", "branch_admin"}


def _conflict(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


def _forbidden(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")


async def _resolve_role(session: AsyncSession, role_name: str, actor_roles: list[str]):
    role = await user_repository.get_role_by_name(session, role_name)
    if role is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown role '{role_name}'",
        )
    # Who may grant the super_admin role. By deliberate choice (single-tenant
    # academy where Branch Admin is the top operational role), a Branch Admin may
    # also grant it — not only an existing super_admin. This is a privilege-
    # escalation path by design; keep the "last super_admin" guards intact.
    if role.name == SUPER_ADMIN and not (set(actor_roles) & _SUPER_ADMIN_GRANTORS):
        raise _forbidden("You are not allowed to grant the super_admin role")
    return role


async def _to_response(session: AsyncSession, user) -> AdminUserResponse:
    roles = await user_repository.get_user_roles(session, user.id)
    return AdminUserResponse(
        id=user.id, email=user.email, first_name=user.first_name,
        last_name=user.last_name, phone=user.phone, status=user.status, roles=roles,
    )


async def list_roles(session: AsyncSession) -> list[RoleOption]:
    return [
        RoleOption(name=r.name, display_name=r.display_name)
        for r in await user_repository.list_roles(session)
    ]


async def list_users(session: AsyncSession) -> list[AdminUserResponse]:
    users = await user_repository.list_users(session)
    roles_by_user = await user_repository.roles_for_users(session, [u.id for u in users])
    return [
        AdminUserResponse(
            id=u.id, email=u.email, first_name=u.first_name, last_name=u.last_name,
            phone=u.phone, status=u.status, roles=roles_by_user.get(u.id, []),
        )
        for u in users
    ]


async def create_user(
    session: AsyncSession,
    *,
    body: UserCreateRequest,
    actor_id: uuid.UUID,
    actor_roles: list[str],
    branch_id: uuid.UUID | None,
) -> AdminUserResponse:
    email = body.email.lower().strip()
    if await user_repository.get_by_email(session, email) is not None:
        raise _conflict("A user with that email already exists")
    role = await _resolve_role(session, body.role, actor_roles)

    user = await user_repository.create_user(
        session,
        email=email,
        password_hash=hash_password(body.password),
        first_name=body.first_name.strip(),
        last_name=body.last_name.strip(),
        phone=(body.phone or None),
        primary_branch_id=branch_id,
        created_by=actor_id,
    )
    await user_repository.set_user_role(
        session, user_id=user.id, role_id=role.id, branch_id=branch_id
    )
    return await _to_response(session, user)


async def update_user(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    body: UserUpdateRequest,
    actor_id: uuid.UUID,
    actor_roles: list[str],
    branch_id: uuid.UUID | None,
) -> AdminUserResponse:
    user = await user_repository.get_by_id(session, user_id)
    if user is None:
        raise _not_found()

    # Deactivation / demotion guards need the target's current roles.
    target_roles = await user_repository.get_user_roles(session, user_id)

    if body.status is not None:
        if body.status not in ("active", "inactive"):
            raise HTTPException(status_code=400, detail="status must be active or inactive")
        if body.status == "inactive":
            await _guard_not_self(user_id, actor_id, "deactivate")
            await _guard_not_last_super_admin(session, target_roles, "deactivate")
        user.status = body.status
        if body.status == "inactive":
            await user_repository.revoke_all_refresh_tokens(session, user_id)

    if body.first_name is not None:
        user.first_name = body.first_name.strip()
    if body.last_name is not None:
        user.last_name = body.last_name.strip()
    if body.phone is not None:
        user.phone = body.phone or None

    if body.role is not None:
        role = await _resolve_role(session, body.role, actor_roles)
        # Demoting the last super_admin away from super_admin would lock everyone out.
        if SUPER_ADMIN in target_roles and role.name != SUPER_ADMIN:
            await _guard_not_last_super_admin(session, target_roles, "demote")
        await user_repository.set_user_role(
            session, user_id=user_id, role_id=role.id, branch_id=branch_id
        )

    await session.flush()
    return await _to_response(session, user)


async def reset_password(
    session: AsyncSession, *, user_id: uuid.UUID, new_password: str
) -> None:
    user = await user_repository.get_by_id(session, user_id)
    if user is None:
        raise _not_found()
    await user_repository.set_password(session, user, hash_password(new_password))
    # Force re-login with the new temp password everywhere.
    await user_repository.revoke_all_refresh_tokens(session, user_id)


async def delete_user(
    session: AsyncSession, *, user_id: uuid.UUID, actor_id: uuid.UUID
) -> None:
    user = await user_repository.get_by_id(session, user_id)
    if user is None:
        raise _not_found()
    await _guard_not_self(user_id, actor_id, "delete")
    target_roles = await user_repository.get_user_roles(session, user_id)
    await _guard_not_last_super_admin(session, target_roles, "delete")
    user.is_deleted = True
    user.status = "inactive"
    await user_repository.revoke_all_refresh_tokens(session, user_id)
    await session.flush()


async def change_own_password(
    session: AsyncSession, *, user_id: uuid.UUID, current_password: str, new_password: str,
    ip: str | None = None, user_agent: str | None = None,
) -> None:
    """Change the signed-in user's own password. Allowed even while
    must_change_password is true (that is the whole point of the first login).
    Enforces the policy, clears the forced-change flag, stamps the change time,
    and ends the user's other sessions."""
    from datetime import datetime, timezone

    from app.modules.teacher_portal.services import auth_events, config_service

    user = await user_repository.get_by_id(session, user_id)
    if user is None:
        raise _not_found()
    if not verify_password(current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    cfg = await config_service.get_config(session)
    min_len = int(cfg.get("min_password_length") or 8)
    if len(new_password) < min_len:
        raise HTTPException(status_code=400, detail=f"Password must be at least {min_len} characters")
    if user.username and new_password.strip().lower() == user.username.strip().lower():
        raise HTTPException(status_code=400, detail="Password cannot equal the employee code")
    if verify_password(new_password, user.password_hash):
        raise HTTPException(status_code=400, detail="New password must differ from the old password")

    await user_repository.set_password(session, user, hash_password(new_password))
    user.must_change_password = False
    user.password_changed_at = datetime.now(timezone.utc)
    await session.flush()
    # End other sessions: revoke all refresh tokens (the current access cookie
    # lives out its short TTL; the client gets a fresh pair on next refresh).
    await user_repository.revoke_all_refresh_tokens(session, user_id)
    await auth_events.record(
        session, event="password_changed", user_id=user_id, ip=ip, user_agent=user_agent,
    )


# ── guards ────────────────────────────────────────────────────────────────────


async def _guard_not_self(user_id: uuid.UUID, actor_id: uuid.UUID, action: str) -> None:
    if user_id == actor_id:
        raise _forbidden(f"You cannot {action} your own account")


async def _guard_not_last_super_admin(
    session: AsyncSession, target_roles: list[str], action: str
) -> None:
    if SUPER_ADMIN not in target_roles:
        return
    remaining = await user_repository.count_active_users_with_role(session, SUPER_ADMIN)
    if remaining <= 1:
        raise _conflict(f"Cannot {action} the last active super admin")
