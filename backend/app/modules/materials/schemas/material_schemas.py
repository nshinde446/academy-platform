import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel as PydanticBaseModel, ConfigDict, Field


class MaterialCategory(str, Enum):
    NCERT = "ncert"
    DPP = "dpp"
    CPP = "cpp"
    TOPIC_WISE = "topic_wise"
    PYQ = "pyq"
    NOTES = "notes"
    OTHER = "other"


class ExamType(str, Enum):
    NEET = "neet"
    JEE_MAIN = "jee_main"
    JEE_ADVANCED = "jee_advanced"
    BOARDS = "boards"
    CET = "cet"
    OTHER = "other"


class IngestStatus(str, Enum):
    UPLOADED = "uploaded"
    INGESTING = "ingesting"
    INGESTED = "ingested"
    INGEST_FAILED = "ingest_failed"
    ARCHIVED = "archived"


# Free-form class labels rather than an enum so coaching can adjust
# without a code change (drop years, gap years, board-prep additions).
ALLOWED_CLASS_LABELS = {"9", "10", "11", "12", "drop"}


class MaterialUploadMetadata(PydanticBaseModel):
    """Form-data fields that accompany the file in the multipart upload.
    Pydantic validates them after the route parses the form."""

    academic_year_id: uuid.UUID
    class_label: str = Field(..., max_length=8)
    subject_id: uuid.UUID
    category: MaterialCategory
    exam_types: list[ExamType] = Field(default_factory=list)
    topic: str | None = Field(None, max_length=120)
    description: str | None = None
    batch_ids: list[uuid.UUID] = Field(default_factory=list)


class MaterialResponse(PydanticBaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    filename: str
    storage_key: str
    mime_type: str
    size_bytes: int
    sha256: str
    academic_year_id: uuid.UUID
    class_label: str
    subject_id: uuid.UUID
    topic: str | None
    category: MaterialCategory
    exam_types: list[str]
    description: str | None
    ingest_status: IngestStatus
    ingest_error: str | None
    question_count: int
    branch_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    created_by: uuid.UUID | None


class MaterialUpdate(PydanticBaseModel):
    """PATCH body. All fields optional; batch_ids replaces the link set
    when present (None = leave links alone)."""

    class_label: str | None = Field(None, max_length=8)
    subject_id: uuid.UUID | None = None
    category: MaterialCategory | None = None
    exam_types: list[ExamType] | None = None
    topic: str | None = Field(None, max_length=120)
    description: str | None = None
    batch_ids: list[uuid.UUID] | None = None


class MaterialListFilters(PydanticBaseModel):
    """Query params parsed from GET /materials. Lists are comma-sep
    strings handled by the route, converted into proper lists here."""

    branch_id: uuid.UUID
    academic_year_id: uuid.UUID | None = None
    class_label: str | None = None
    subject_id: uuid.UUID | None = None
    category: MaterialCategory | None = None
    exam_type: ExamType | None = None
    batch_id: uuid.UUID | None = None
    search: str | None = None


class FacetBucket(PydanticBaseModel):
    value: str
    count: int


class MaterialFacetCounts(PydanticBaseModel):
    classes: list[FacetBucket]
    subjects: list[FacetBucket]
    categories: list[FacetBucket]
    exam_types: list[FacetBucket]
    batches: list[FacetBucket]


class MaterialListResponse(PydanticBaseModel):
    items: list[MaterialResponse]
    total: int
