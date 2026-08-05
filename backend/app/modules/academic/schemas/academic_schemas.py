import uuid

from pydantic import BaseModel


class InstituteCreate(BaseModel):
    name: str
    code: str
    address: str | None = None
    phone: str | None = None
    email: str | None = None


class InstituteResponse(BaseModel):
    id: uuid.UUID
    name: str
    code: str
    address: str | None = None
    phone: str | None = None
    email: str | None = None
    status: str
    model_config = {"from_attributes": True}


class AcademicYearCreate(BaseModel):
    branch_id: uuid.UUID
    name: str
    start_year: int
    end_year: int


class AcademicYearResponse(BaseModel):
    id: uuid.UUID
    branch_id: uuid.UUID
    name: str
    start_year: int
    end_year: int
    status: str
    model_config = {"from_attributes": True}


class CourseCreate(BaseModel):
    branch_id: uuid.UUID
    name: str
    code: str
    description: str | None = None
    duration_years: int = 1
    # Optional exam target — when set, the course's standard subjects are seeded
    # on creation (JEE->PCM, NEET->PCB, MHT-CET->PCMB) so its batches are
    # schedulable immediately. Not stored on the course; used only to seed.
    syllabus_key: str | None = None


class CourseUpdate(BaseModel):
    name: str | None = None
    code: str | None = None
    description: str | None = None
    duration_years: int | None = None


class CourseResponse(BaseModel):
    id: uuid.UUID
    branch_id: uuid.UUID
    name: str
    code: str
    description: str | None = None
    duration_years: int
    status: str
    model_config = {"from_attributes": True}


class SubjectCreate(BaseModel):
    branch_id: uuid.UUID
    academic_year_id: uuid.UUID
    course_id: uuid.UUID
    name: str
    code: str


class SubjectResponse(BaseModel):
    id: uuid.UUID
    branch_id: uuid.UUID
    academic_year_id: uuid.UUID
    course_id: uuid.UUID
    name: str
    code: str
    status: str
    model_config = {"from_attributes": True}


class SubjectSeedRequest(BaseModel):
    """Populate a course's subjects from a known syllabus (JEE / NEET / MHT-CET
    …). Idempotent — a course that already has subjects is left untouched."""

    branch_id: uuid.UUID
    course_id: uuid.UUID
    syllabus_key: str


class SubjectSeedResponse(BaseModel):
    created: int
    subjects: list[SubjectResponse]


class SyllabusOption(BaseModel):
    key: str
    label: str
    subjects: list[str]


class ChapterCreate(BaseModel):
    branch_id: uuid.UUID
    academic_year_id: uuid.UUID
    subject_id: uuid.UUID
    name: str
    order: int = 0


class ChapterResponse(BaseModel):
    id: uuid.UUID
    branch_id: uuid.UUID
    academic_year_id: uuid.UUID
    subject_id: uuid.UUID
    name: str
    order: int
    status: str
    model_config = {"from_attributes": True}


class TopicCreate(BaseModel):
    branch_id: uuid.UUID
    academic_year_id: uuid.UUID
    chapter_id: uuid.UUID
    name: str
    order: int = 0


class TopicResponse(BaseModel):
    id: uuid.UUID
    branch_id: uuid.UUID
    academic_year_id: uuid.UUID
    chapter_id: uuid.UUID
    name: str
    order: int
    status: str
    model_config = {"from_attributes": True}


class SubtopicCreate(BaseModel):
    branch_id: uuid.UUID
    academic_year_id: uuid.UUID
    topic_id: uuid.UUID
    name: str
    order: int = 0


class SubtopicResponse(BaseModel):
    id: uuid.UUID
    branch_id: uuid.UUID
    academic_year_id: uuid.UUID
    topic_id: uuid.UUID
    name: str
    order: int
    status: str
    model_config = {"from_attributes": True}


class CurriculumBackfillSummary(BaseModel):
    """Result of backfilling the bundled master curriculum onto a branch's
    existing course subjects that had no chapters yet."""

    courses_touched: int
    subjects_filled: int
    chapters_added: int
    topics_added: int
