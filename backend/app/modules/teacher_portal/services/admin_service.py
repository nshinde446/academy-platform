"""Admin management of teacher login accounts (spec section 3 Admin APIs).

Create (bulk), reset password, unlock, disable/enable. Username = employee code;
a random temporary password is issued and returned ONCE (never stored in plain
text, never logged). Every action writes the business audit log + an auth_event.
Permission is role-gated in the route (super_admin / branch_admin / accounts).
"""

from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.services import audit_service
from app.modules.auth.models.auth_models import Role, User
from app.modules.auth.repositories import user_repository
from app.modules.auth.services.auth_service import hash_password
from app.modules.staff.models.staff_models import Department, Staff
from app.modules.teacher_portal.services import auth_events, config_service

# Unambiguous alphabet for a temporary password the admin reads out loud
# (no O/0, I/l/1).
_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789"


def _gen_temp_password(length: int = 10) -> str:
    length = max(8, length)
    return "".join(secrets.choice(_ALPHABET) for _ in range(length))


async def _teacher_role(session: AsyncSession) -> Role:
    role = (await session.execute(
        select(Role).where(func.lower(Role.name) == "teacher")
    )).scalar_one_or_none()
    if role is None:
        raise HTTPException(status_code=500, detail="teacher role is not configured")
    return role


async def _min_len(session: AsyncSession) -> int:
    cfg = await config_service.get_config(session)
    return int(cfg.get("min_password_length") or 8)


async def _teachers_dept_staff(
    session: AsyncSession, branch_id: uuid.UUID, staff_ids: list[uuid.UUID] | None,
) -> list[Staff]:
    """Active staff in a Teachers department (department name contains
    'teacher'), optionally narrowed to ``staff_ids``."""
    q = (
        select(Staff)
        .join(Department, Department.id == Staff.department_id)
        .where(
            Staff.branch_id == branch_id,
            Staff.is_deleted == False,  # noqa: E712
            Staff.status == "active",
            func.lower(Department.name).like("%teacher%"),
        )
    )
    if staff_ids:
        q = q.where(Staff.id.in_(staff_ids))
    return list((await session.execute(q.order_by(Staff.emp_code))).scalars().all())


async def _user_for_staff(session: AsyncSession, staff_id: uuid.UUID) -> User | None:
    return (await session.execute(
        select(User).where(User.staff_id == staff_id, User.is_deleted == False)  # noqa: E712
    )).scalar_one_or_none()


async def _issue_temp(
    session: AsyncSession, user: User, min_len: int
) -> str:
    temp = _gen_temp_password(min_len)
    await user_repository.set_password(session, user, hash_password(temp))
    user.must_change_password = True
    user.failed_attempts = 0
    user.locked_until = None
    await session.flush()
    return temp


async def bulk_create(
    session: AsyncSession, *, branch_id: uuid.UUID, actor_id: uuid.UUID,
    staff_ids: list[uuid.UUID] | None = None, ip: str | None = None,
) -> list[dict]:
    """Create login accounts for active Teachers-department staff that don't yet
    have one. Returns ``[{employee_code, name, temporary_password}]`` ONCE."""
    role = await _teacher_role(session)
    min_len = await _min_len(session)
    created: list[dict] = []
    for s in await _teachers_dept_staff(session, branch_id, staff_ids):
        if await _user_for_staff(session, s.id) is not None:
            continue  # already has an account
        temp = _gen_temp_password(min_len)
        user = User(
            email=f"{s.emp_code}@teacher.local",
            password_hash=hash_password(temp),
            first_name=s.first_name, last_name=s.last_name,
            username=s.emp_code, staff_id=s.id, primary_branch_id=branch_id,
            must_change_password=True, status="active", created_by=actor_id,
        )
        session.add(user)
        await session.flush()
        await user_repository.set_user_role(
            session, user_id=user.id, role_id=role.id, branch_id=branch_id
        )
        await audit_service.log_action(
            session, user_id=actor_id, action="CREATE", table_name="users",
            record_id=user.id, new_values={"username": s.emp_code, "teacher_account": True},
            ip_address=ip, branch_id=branch_id,
        )
        await auth_events.record(
            session, event="account_created", user_id=user.id, actor_id=actor_id,
            username_attempted=s.emp_code, ip=ip,
        )
        created.append({
            "employee_code": s.emp_code,
            "name": f"{s.first_name} {s.last_name}".strip(),
            "temporary_password": temp,
        })
    return created


async def _get_account(session: AsyncSession, staff_id: uuid.UUID) -> User:
    user = await _user_for_staff(session, staff_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Teacher account not found")
    return user


async def reset_password(
    session: AsyncSession, *, staff_id: uuid.UUID, actor_id: uuid.UUID, ip: str | None = None,
) -> dict:
    user = await _get_account(session, staff_id)
    min_len = await _min_len(session)
    temp = await _issue_temp(session, user, min_len)
    await user_repository.revoke_all_refresh_tokens(session, user.id)  # end sessions
    await audit_service.log_action(
        session, user_id=actor_id, action="UPDATE", table_name="users",
        record_id=user.id, new_values={"password_reset": True}, ip_address=ip,
        branch_id=user.primary_branch_id,
    )
    await auth_events.record(
        session, event="password_reset", user_id=user.id, actor_id=actor_id, ip=ip,
    )
    return {"employee_code": user.username, "temporary_password": temp}


async def unlock(
    session: AsyncSession, *, staff_id: uuid.UUID, actor_id: uuid.UUID, ip: str | None = None,
) -> None:
    user = await _get_account(session, staff_id)
    user.locked_until = None
    user.failed_attempts = 0
    await session.flush()
    await audit_service.log_action(
        session, user_id=actor_id, action="UPDATE", table_name="users",
        record_id=user.id, new_values={"unlocked": True}, ip_address=ip,
        branch_id=user.primary_branch_id,
    )
    await auth_events.record(session, event="unlocked", user_id=user.id, actor_id=actor_id, ip=ip)


async def set_enabled(
    session: AsyncSession, *, staff_id: uuid.UUID, enabled: bool, actor_id: uuid.UUID,
    ip: str | None = None,
) -> None:
    user = await _get_account(session, staff_id)
    user.status = "active" if enabled else "inactive"
    user.updated_at = datetime.now(timezone.utc)
    await session.flush()
    if not enabled:
        await user_repository.revoke_all_refresh_tokens(session, user.id)
    await audit_service.log_action(
        session, user_id=actor_id, action="UPDATE", table_name="users",
        record_id=user.id, new_values={"enabled": enabled}, ip_address=ip,
        branch_id=user.primary_branch_id,
    )
    await auth_events.record(
        session, event="account_enabled" if enabled else "account_disabled",
        user_id=user.id, actor_id=actor_id, ip=ip,
    )


async def list_accounts(
    session: AsyncSession, *, branch_id: uuid.UUID, status_filter: str | None = None,
    q: str | None = None,
) -> list[dict]:
    """Teacher accounts with status + last login, for the admin screen."""
    query = select(User).where(
        User.staff_id.isnot(None), User.is_deleted == False,  # noqa: E712
        User.primary_branch_id == branch_id,
    )
    users = list((await session.execute(query)).scalars().all())
    out = []
    now = datetime.now(timezone.utc)
    for u in users:
        locked = u.locked_until is not None and (
            u.locked_until.replace(tzinfo=timezone.utc) if u.locked_until.tzinfo is None
            else u.locked_until
        ) > now
        if u.status != "active":
            st = "disabled"
        elif locked:
            st = "locked"
        elif u.must_change_password:
            st = "must_change_password"
        else:
            st = "active"
        if status_filter and st != status_filter:
            continue
        name = f"{u.first_name} {u.last_name}".strip()
        if q and q.lower() not in (u.username or "").lower() and q.lower() not in name.lower():
            continue
        out.append({
            "staff_id": u.staff_id, "employee_code": u.username, "name": name,
            "status": st, "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
        })
    out.sort(key=lambda r: r["employee_code"] or "")
    return out
