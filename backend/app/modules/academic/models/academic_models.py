import uuid

from sqlalchemy import ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.base import BaseModel


class Institute(BaseModel):
    __tablename__ = "institutes"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)


class AcademicYear(BaseModel):
    __tablename__ = "academic_years"

    branch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("branch.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    start_year: Mapped[int] = mapped_column(Integer, nullable=False)
    end_year: Mapped[int] = mapped_column(Integer, nullable=False)
    # Set when a student import auto-created this year, so "undo import" can
    # reclaim it (only when nothing else references it). Null for years made
    # through the Academic Years UI.
    import_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, nullable=True, index=True
    )


class Course(BaseModel):
    __tablename__ = "courses"

    branch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("branch.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    duration_years: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    # Set when a student import auto-created this course, so "undo import" can
    # reclaim it (only when no batch/subject still references it).
    import_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, nullable=True, index=True
    )


class Subject(BaseModel):
    __tablename__ = "subjects"

    branch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("branch.id"), nullable=False
    )
    academic_year_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("academic_years.id"), nullable=False
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("courses.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    # Set when a student import auto-created this subject as part of a course's
    # skeleton, so "undo import" can reclaim it (only if no chapters loaded).
    import_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, nullable=True, index=True
    )


class Chapter(BaseModel):
    __tablename__ = "chapters"

    branch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("branch.id"), nullable=False
    )
    academic_year_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("academic_years.id"), nullable=False
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("subjects.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Set when a student import auto-populated this chapter from the bundled
    # master curriculum, so "undo import" can reclaim the curriculum it created.
    import_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, nullable=True, index=True
    )


class Topic(BaseModel):
    __tablename__ = "topics"

    branch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("branch.id"), nullable=False
    )
    academic_year_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("academic_years.id"), nullable=False
    )
    chapter_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("chapters.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Set when a student import auto-populated this topic from the bundled
    # master curriculum, so "undo import" can reclaim it.
    import_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, nullable=True, index=True
    )


class Subtopic(BaseModel):
    __tablename__ = "subtopics"

    branch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("branch.id"), nullable=False
    )
    academic_year_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("academic_years.id"), nullable=False
    )
    topic_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("topics.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
