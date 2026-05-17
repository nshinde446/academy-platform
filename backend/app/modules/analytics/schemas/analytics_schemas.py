import uuid
from datetime import datetime

from pydantic import BaseModel


class StudentAnalyticsResponse(BaseModel):
    student_id: uuid.UUID
    branch_id: uuid.UUID
    academic_year_id: uuid.UUID
    total_attendance: int
    present_count: int
    absent_count: int
    late_count: int
    attendance_percentage: float
    total_tests: int
    average_score: float
    weak_topics: list[str] | None = None
    risk_score: float
    last_updated: datetime


class TeacherAnalyticsResponse(BaseModel):
    teacher_id: uuid.UUID
    branch_id: uuid.UUID
    academic_year_id: uuid.UUID
    total_lectures: int
    completed_lectures: int
    completion_rate: float
    avg_delay_minutes: float
    avg_student_attendance: float
    last_updated: datetime


class BatchAnalyticsResponse(BaseModel):
    batch_id: uuid.UUID
    branch_id: uuid.UUID
    academic_year_id: uuid.UUID
    total_students: int
    avg_attendance: float
    avg_score: float
    weak_subjects: list[str] | None = None
    top_performers: list[str] | None = None
    last_updated: datetime


class RiskStudentResponse(BaseModel):
    student_id: uuid.UUID
    risk_score: float
    attendance_percentage: float
    average_score: float
