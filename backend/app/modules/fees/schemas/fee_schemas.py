import uuid
from datetime import date

from pydantic import BaseModel


# ── Course fee config (spec §1) ──────────────────────────────────────────────

class CourseFeeConfigUpsert(BaseModel):
    course_name: str          # CET / JEE / NEET
    standard_fee: float


class CourseFeeConfigResponse(BaseModel):
    id: uuid.UUID
    branch_id: uuid.UUID
    course_name: str
    standard_fee: float
    model_config = {"from_attributes": True}


# ── Student fee profile (spec §2) ────────────────────────────────────────────

class InstallmentInput(BaseModel):
    """An explicit installment row (the accounts team's edited plan)."""
    number: int
    due_date: date
    amount: float


class StudentFeeProfileCreate(BaseModel):
    student_id: uuid.UUID
    batch_id: uuid.UUID
    actual_fee: float
    agreed_fee: float
    payment_mode: str                    # ONE_TIME | INSTALLMENT
    admission_date: date

    # INSTALLMENT mode: give an explicit `installments` plan, OR the auto-generate
    # inputs (first_installment + remaining_installments [+ interval_months]) and
    # the server computes the 2.5-month schedule. Ignored for ONE_TIME.
    installments: list[InstallmentInput] | None = None
    first_installment: float | None = None
    remaining_installments: int | None = None
    interval_months: float = 2.5


class InstallmentResponse(BaseModel):
    id: uuid.UUID
    installment_number: int
    due_date: date
    amount: float
    installment_status: str
    paid_amount: float
    paid_date: date | None = None
    payment_mode: str | None = None
    model_config = {"from_attributes": True}


class StudentFeeProfileResponse(BaseModel):
    id: uuid.UUID
    student_id: uuid.UUID
    branch_id: uuid.UUID
    batch_id: uuid.UUID
    actual_fee: float
    agreed_fee: float
    discount_amount: float
    payment_mode: str
    total_paid: float
    total_pending: float
    admission_date: date
    installments: list[InstallmentResponse] = []
    model_config = {"from_attributes": True}
