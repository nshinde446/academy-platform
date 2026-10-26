"""Pydantic schemas for the payroll settings endpoint (§8)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PayrollConfigUpdate(BaseModel):
    """Partial update of payroll settings. Every field is optional — only the
    ones sent are written. Unknown keys are rejected by the model; recognised
    keys the service doesn't know are dropped there."""

    model_config = {"extra": "forbid"}

    payroll_enabled: bool | None = None
    holiday_treatment: str | None = Field(default=None, pattern="^(credited|reduce_required)$")
    allow_half_day: bool | None = None
    carry_forward_cap: int | None = Field(default=None, ge=0)
    carry_forward_expiry_months: int | None = Field(default=None, ge=0)
    allow_payout: bool | None = None
    allow_negative_balance: bool | None = None
    unapproved_shortfall: str | None = Field(default=None, pattern="^(unpaid|absent)$")
    request_raiser_roles: list[str] | None = None
    request_approver_role: str | None = None
    allow_manager_approver: bool | None = None
    prorate_on_join_leave: bool | None = None
    prorate_rounding: float | None = Field(default=None, ge=0)

    def changes(self) -> dict[str, object]:
        """Only the fields the caller actually set."""
        return self.model_dump(exclude_unset=True)
