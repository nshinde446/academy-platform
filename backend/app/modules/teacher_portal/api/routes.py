"""Teacher portal — read-only ``/api/v1/me/*`` endpoints (self only).

The staff id comes ONLY from the login session. Any ``staff_id`` /
``employee_code`` / ``user_id`` in the query, path or body is ignored, and the
attempt is logged as an ``idor_attempt`` auth event (spec section 1/3). While a
teacher account must change its password, every data route returns 403
``PASSWORD_CHANGE_REQUIRED`` (the gate is enforced here and by the allowlist
middleware).
"""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.modules.auth.models.auth_models import User
from app.modules.auth.permissions.rbac import get_current_user
from app.modules.teacher_portal.schemas.portal_schemas import (
    LeaveApply,
    MonthSummary,
    ProfileContactUpdate,
    TeacherProfile,
    TeacherSession,
)
from app.modules.teacher_portal.services import (
    auth_events,
    config_service,
    leave_service,
    portal_service,
    productivity_service,
)

me_router = APIRouter(prefix="/me", tags=["teacher-portal"])

# Any of these in the request is an IDOR probe — the id is session-derived, so
# we ignore the value and log the attempt.
_IDOR_PARAMS = ("staff_id", "staffId", "employee_code", "employeeCode", "user_id", "userId")


async def _resolve_user(session: AsyncSession, user_id: uuid.UUID) -> User:
    user = (await session.execute(
        select(User).where(User.id == user_id)
    )).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user


async def _log_idor_if_present(
    session: AsyncSession, request: Request, user_id: uuid.UUID
) -> None:
    """If the request carries any identity override, log it (the value is never
    used — identity is the session's own staff link)."""
    qp = request.query_params
    if any(p in qp for p in _IDOR_PARAMS):
        await auth_events.record(
            session, event="idor_attempt", user_id=user_id,
            ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            detail=f"identity override ignored on {request.url.path}: "
                   + ",".join(p for p in _IDOR_PARAMS if p in qp),
        )


async def get_current_teacher(
    request: Request,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> TeacherSession:
    """Resolve the logged-in teacher's own staff id from the session. Enforces
    the forced-password-change gate and logs any identity-override attempt."""
    user_id = current_user["user_id"]
    user = await _resolve_user(session, user_id)

    if user.must_change_password:
        # The global exception handler reshapes HTTPException into
        # {"error": {"code", "message"}}; carry the machine-readable marker in
        # the message so the client can route to the change-password screen.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="PASSWORD_CHANGE_REQUIRED",
        )
    if user.staff_id is None:
        # Not a staff-linked (teacher) account — the portal has no data for them.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account is not linked to a staff record.",
        )
    await _log_idor_if_present(session, request, user_id)
    return TeacherSession(
        user_id=user_id, staff_id=user.staff_id, branch_id=current_user.get("branch_id"),
    )


async def _check_history_window(session: AsyncSession, day_: date) -> None:
    """Dates are limited to the last ``history_days`` and never in the future."""
    cfg = await config_service.get_config(session)
    import datetime as _dt
    today = _dt.date.today()
    if day_ > today:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Date cannot be in the future.")
    history = int(cfg.get("history_days") or 90)
    if (today - day_).days > history:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Date is outside the allowed {history}-day window.",
        )


@me_router.get("/profile", response_model=TeacherProfile)
async def my_profile(
    me: TeacherSession = Depends(get_current_teacher),
    session: AsyncSession = Depends(get_db),
):
    return await portal_service.profile(session, me.staff_id)


@me_router.patch("/profile", response_model=TeacherProfile)
async def update_my_profile(
    body: ProfileContactUpdate,
    request: Request,
    me: TeacherSession = Depends(get_current_teacher),
    session: AsyncSession = Depends(get_db),
):
    """Self-service contact update — phone / email only. The staff id is the
    session's own (never from the body), so a teacher can only edit themselves.
    ``model_fields_set`` tells us which fields were actually sent."""
    if not body.model_fields_set:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide at least one of: phone, email.",
        )
    return await portal_service.update_contact(
        session, me.staff_id, actor_user_id=me.user_id,
        phone=body.phone, email=body.email,
        phone_set="phone" in body.model_fields_set,
        email_set="email" in body.model_fields_set,
        ip=request.client.host if request.client else None,
    )


@me_router.get("/day")
async def my_day(
    me: TeacherSession = Depends(get_current_teacher),
    date_: date | None = Query(default=None, alias="date"),
    session: AsyncSession = Depends(get_db),
):
    import datetime as _dt
    day_ = date_ or _dt.date.today()
    await _check_history_window(session, day_)
    return await portal_service.day(session, me.staff_id, day_)


@me_router.get("/month-summary", response_model=MonthSummary)
async def my_month_summary(
    me: TeacherSession = Depends(get_current_teacher),
    year: int | None = Query(default=None),
    month: int | None = Query(default=None),
    session: AsyncSession = Depends(get_db),
):
    import datetime as _dt
    today = _dt.date.today()
    y, m = year or today.year, month or today.month
    if not (1 <= m <= 12):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="month must be 1-12")
    if (y, m) > (today.year, today.month):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="month cannot be in the future")
    data = await portal_service.month_summary(session, me.staff_id, y, m)
    return MonthSummary(**data)


@me_router.get("/attendance")
async def my_attendance(
    me: TeacherSession = Depends(get_current_teacher),
    year: int | None = Query(default=None),
    month: int | None = Query(default=None),
    from_: date | None = Query(default=None, alias="from"),
    to: date | None = Query(default=None),
    session: AsyncSession = Depends(get_db),
):
    """Per-day attendance for the signed-in teacher (Change 1). Either a month
    (year+month, default current month) or an explicit from/to range."""
    import calendar as _cal
    import datetime as _dt

    today = _dt.date.today()
    if from_ is not None or to is not None:
        start = from_ or to
        end = to or from_
    else:
        y, m = year or today.year, month or today.month
        if not (1 <= m <= 12):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="month must be 1-12")
        start = date(y, m, 1)
        end = date(y, m, _cal.monthrange(y, m)[1])
    return await portal_service.attendance(session, me.staff_id, start, end)


# ── leave (self-service: apply / list / withdraw) ────────────────────────────


@me_router.get("/productivity")
async def my_productivity(
    range: str = Query(default="month"),
    me: TeacherSession = Depends(get_current_teacher),
    session: AsyncSession = Depends(get_db),
):
    """Factual productivity metrics for the signed-in teacher, bucketed for a
    chart (week / month / quarter / year)."""
    return await productivity_service.productivity(session, me.staff_id, range)


@me_router.get("/leaves")
async def my_leaves(
    me: TeacherSession = Depends(get_current_teacher),
    session: AsyncSession = Depends(get_db),
):
    return await leave_service.my_leaves(session, me.staff_id)


@me_router.post("/leaves", status_code=status.HTTP_201_CREATED)
async def apply_leave(
    body: LeaveApply,
    request: Request,
    me: TeacherSession = Depends(get_current_teacher),
    session: AsyncSession = Depends(get_db),
):
    return await leave_service.apply_leave(
        session, staff_id=me.staff_id, user_id=me.user_id,
        start_date=body.start_date, end_date=body.end_date, reason=body.reason,
        ip=request.client.host if request.client else None,
    )


@me_router.delete("/leaves/{leave_id}")
async def withdraw_leave(
    leave_id: uuid.UUID,
    request: Request,
    me: TeacherSession = Depends(get_current_teacher),
    session: AsyncSession = Depends(get_db),
):
    await leave_service.cancel_leave(
        session, staff_id=me.staff_id, leave_id=leave_id, user_id=me.user_id,
        ip=request.client.host if request.client else None,
    )
    return {"message": "withdrawn"}
