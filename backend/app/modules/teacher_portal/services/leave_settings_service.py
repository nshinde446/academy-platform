"""Admin leave settings — per-year quota per leave type + WOF opening balances
(Teacher Portal Changes §3 + WOF). Super Admin only (enforced in the routes)."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.staff.models.staff_models import Staff
from app.modules.teacher.models.teacher_models import (
    LeaveTypeQuota,
    Teacher,
    TeacherWofOpening,
)
from app.modules.teacher_portal.services import wof_service
from app.modules.teacher_portal.services.leave_service import QUOTA_TYPES


async def get_quotas(session: AsyncSession, branch_id: uuid.UUID, year: int) -> dict:
    rows = (await session.execute(
        select(LeaveTypeQuota).where(
            LeaveTypeQuota.branch_id == branch_id,
            LeaveTypeQuota.year == year,
            LeaveTypeQuota.is_deleted == False,  # noqa: E712
        )
    )).scalars().all()
    by_type = {r.leave_type: float(r.quota_days) for r in rows}
    return {"year": year, "quotas": {t: by_type.get(t) for t in QUOTA_TYPES}}


async def set_quotas(
    session: AsyncSession, *, branch_id: uuid.UUID, year: int,
    quotas: dict[str, float], user_id: uuid.UUID,
) -> dict:
    existing = {
        r.leave_type: r for r in (await session.execute(
            select(LeaveTypeQuota).where(
                LeaveTypeQuota.branch_id == branch_id,
                LeaveTypeQuota.year == year,
                LeaveTypeQuota.is_deleted == False,  # noqa: E712
            )
        )).scalars().all()
    }
    for lt, val in quotas.items():
        if lt not in QUOTA_TYPES or val is None:
            continue
        row = existing.get(lt)
        if row is None:
            session.add(LeaveTypeQuota(
                branch_id=branch_id, year=year, leave_type=lt,
                quota_days=val, created_by=user_id,
            ))
        else:
            row.quota_days = val
            row.updated_by = user_id
    await session.flush()
    return await get_quotas(session, branch_id, year)


async def _teachers_with_staff(
    session: AsyncSession, branch_id: uuid.UUID
) -> list[tuple[Teacher, Staff | None]]:
    teachers = (await session.execute(
        select(Teacher).where(
            Teacher.branch_id == branch_id, Teacher.is_deleted == False,  # noqa: E712
        )
    )).scalars().all()
    staff = {
        s.linked_teacher_id: s for s in (await session.execute(
            select(Staff).where(
                Staff.branch_id == branch_id, Staff.is_deleted == False,  # noqa: E712
                Staff.linked_teacher_id.isnot(None),
            )
        )).scalars().all()
    }
    return [(t, staff.get(t.id)) for t in teachers]


async def list_wof(session: AsyncSession, branch_id: uuid.UUID) -> list[dict]:
    openings = {
        o.teacher_id: o for o in (await session.execute(
            select(TeacherWofOpening).where(
                TeacherWofOpening.branch_id == branch_id,
                TeacherWofOpening.is_deleted == False,  # noqa: E712
            )
        )).scalars().all()
    }
    out: list[dict] = []
    for t, s in await _teachers_with_staff(session, branch_id):
        o = openings.get(t.id)
        bal = await wof_service.balance(session, s) if s is not None else None
        out.append({
            "teacher_id": str(t.id),
            "emp_code": s.emp_code if s else None,
            "name": f"{t.first_name} {t.last_name}".strip(),
            "opening_balance": float(o.opening_balance) if o else None,
            "as_of_date": o.as_of_date.isoformat() if o else None,
            "current_balance": bal["balance"] if bal else None,
        })
    out.sort(key=lambda r: r["name"])
    return out


async def set_wof_opening(
    session: AsyncSession, *, branch_id: uuid.UUID, teacher_id: uuid.UUID,
    opening_balance: float, as_of_date: date, user_id: uuid.UUID,
) -> dict:
    t = (await session.execute(
        select(Teacher).where(Teacher.id == teacher_id, Teacher.is_deleted == False)  # noqa: E712
    )).scalar_one_or_none()
    if t is None or t.branch_id != branch_id:
        raise HTTPException(status_code=404, detail="Teacher not found in this branch")
    row = (await session.execute(
        select(TeacherWofOpening).where(
            TeacherWofOpening.teacher_id == teacher_id,
            TeacherWofOpening.is_deleted == False,  # noqa: E712
        )
    )).scalar_one_or_none()
    if row is None:
        session.add(TeacherWofOpening(
            teacher_id=teacher_id, branch_id=branch_id,
            opening_balance=opening_balance, as_of_date=as_of_date, created_by=user_id,
        ))
    else:
        row.opening_balance = opening_balance
        row.as_of_date = as_of_date
        row.updated_by = user_id
        row.updated_at = datetime.now(timezone.utc)
    await session.flush()
    return {"teacher_id": str(teacher_id), "opening_balance": opening_balance,
            "as_of_date": as_of_date.isoformat()}
