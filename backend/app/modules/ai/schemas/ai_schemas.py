import uuid
from datetime import datetime

from pydantic import BaseModel, field_validator

VALID_REQUEST_TYPES = {"QUESTION_GENERATION", "RECOMMENDATION", "TUTOR", "DPP_GENERATION"}
VALID_DIFFICULTIES = {"EASY", "MEDIUM", "HARD"}


class QuestionGenerateRequest(BaseModel):
    topic_id: uuid.UUID
    count: int = 5
    difficulty: str = "MEDIUM"
    branch_id: uuid.UUID | None = None

    @field_validator("difficulty")
    @classmethod
    def validate_difficulty(cls, v: str) -> str:
        if v.upper() not in VALID_DIFFICULTIES:
            raise ValueError(f"difficulty must be one of {VALID_DIFFICULTIES}")
        return v.upper()

    @field_validator("count")
    @classmethod
    def validate_count(cls, v: int) -> int:
        if v < 1 or v > 50:
            raise ValueError("count must be between 1 and 50")
        return v


class RecommendationRequest(BaseModel):
    student_id: uuid.UUID
    limit: int = 10
    branch_id: uuid.UUID | None = None


class TutorAskRequest(BaseModel):
    student_id: uuid.UUID
    question_text: str
    context: str | None = None
    branch_id: uuid.UUID | None = None

    @field_validator("question_text")
    @classmethod
    def validate_question(cls, v: str) -> str:
        if not v or len(v) > 2000:
            raise ValueError("question_text must be 1-2000 characters")
        return v


class DPPGenerateRequest(BaseModel):
    batch_id: uuid.UUID
    subjects: list[uuid.UUID]
    days: int = 7
    branch_id: uuid.UUID | None = None

    @field_validator("days")
    @classmethod
    def validate_days(cls, v: int) -> int:
        if v < 1 or v > 30:
            raise ValueError("days must be between 1 and 30")
        return v


class AIRequestResponse(BaseModel):
    id: uuid.UUID
    request_type: str
    request_status: str
    payload_json: str | None
    response_json: str | None
    error_message: str | None
    requested_by: uuid.UUID
    branch_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AIServiceConfigCreate(BaseModel):
    service_name: str
    config_key: str
    config_value: str
    is_secret: bool = False
    branch_id: uuid.UUID | None = None
