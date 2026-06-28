import uuid

from pydantic import BaseModel


class TeacherCreate(BaseModel):
    branch_id: uuid.UUID
    first_name: str
    last_name: str
    email: str | None = None
    phone: str | None = None
    qualification: str | None = None
    years_experience: int | None = None
    user_id: uuid.UUID | None = None
    # Subject names the teacher teaches (resolved to every matching subject row
    # across courses). Drives the Subject→Teacher schedule lock.
    subjects: list[str] = []


class TeacherSubjectsUpdate(BaseModel):
    subjects: list[str] = []


class TeacherSubjectsResponse(BaseModel):
    subjects: list[str]


class TeacherUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    phone: str | None = None
    qualification: str | None = None
    years_experience: int | None = None


class TeacherResponse(BaseModel):
    id: uuid.UUID
    branch_id: uuid.UUID
    user_id: uuid.UUID | None = None
    first_name: str
    last_name: str
    email: str | None = None
    phone: str | None = None
    qualification: str | None = None
    years_experience: int | None = None
    status: str
    model_config = {"from_attributes": True}


class TeacherWithStats(BaseModel):
    """Teacher row enriched with adherence + outcome metrics for the
    MSA_Design teachers list. Lectures count is over the last 30 days;
    sub rate and outcome delta align with /insights data."""

    id: uuid.UUID
    first_name: str
    last_name: str
    qualification: str | None = None
    years_experience: int | None = None
    subject_id: uuid.UUID | None = None
    subject_name: str | None = None
    # Computed
    lectures_30d: int
    sub_rate_pct: float
    avg_outcome_delta_pp: float | None = None


class ImportSummary(BaseModel):
    imported: int
    skipped: int
    errors: list[str] = []


class BulkTeacherDelete(BaseModel):
    teacher_ids: list[uuid.UUID]


class BulkDeleteSummary(BaseModel):
    """Result of a bulk soft-delete of teachers."""

    deleted: int
