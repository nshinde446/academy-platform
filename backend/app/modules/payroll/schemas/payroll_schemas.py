"""Pydantic schemas for payroll month setup, the monthly report and the staff
ledger (§7/§11)."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


# ── month setup ──────────────────────────────────────────────────────────────

class HolidayResponse(BaseModel):
    id: str
    holiday_date: date
    title: str
    kind: str
    credit_days: float


class HolidayCreate(BaseModel):
    model_config = {"extra": "forbid"}
    holiday_date: date
    title: str = Field(min_length=1, max_length=200)
    kind: str = Field(default="HOLIDAY", pattern="^(HOLIDAY|LEAVE)$")
    credit_days: float = Field(default=1.0, ge=0, le=1)


class MonthSettingsResponse(BaseModel):
    year: int
    month: int
    required_days: float
    lifecycle: str
    notes: str | None = None
    holidays: list[HolidayResponse] = []


class MonthSettingsUpsert(BaseModel):
    model_config = {"extra": "forbid"}
    required_days: float = Field(ge=0, le=31)
    notes: str | None = None
    # Required when editing a month that is already CLOSED/LOCKED (§1/§12).
    reason: str | None = None


class LifecycleAction(BaseModel):
    model_config = {"extra": "forbid"}
    # Reason is mandatory for reopen (§6); optional for close/lock.
    reason: str | None = None


# ── monthly report (§7) ──────────────────────────────────────────────────────

class ReportRow(BaseModel):
    staff_id: str
    emp_code: str
    name: str
    department: str
    required_days: float
    present_days: float
    half_days: int
    paid_leave_days: float
    net_days: float
    balance_in: float
    balance_out: float
    uncovered_days: float
    deferred_days: float
    late_fine_total: float


class ReportTotals(BaseModel):
    staff_count: int
    present_days: float
    uncovered_days: float
    late_fine_total: float


class ReportResponse(BaseModel):
    year: int
    month: int
    lifecycle: str  # OPEN (preview) | CLOSED | LOCKED | NOT_SET
    rows: list[ReportRow]
    totals: ReportTotals


# ── staff ledger (§4/§11) ────────────────────────────────────────────────────

class LedgerRow(BaseModel):
    year: int
    month: int
    seq: int
    entry_type: str
    days: float
    running_balance: float
    note: str | None = None
    created_by: str | None = None
    created_at: datetime | None = None


class LedgerResponse(BaseModel):
    staff_id: str
    emp_code: str
    name: str
    current_balance: float
    rows: list[LedgerRow]
