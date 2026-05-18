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
