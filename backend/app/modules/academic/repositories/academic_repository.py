import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.academic.models.academic_models import (
    AcademicYear,
    Chapter,
    Course,
    Institute,
    Subject,
    Subtopic,
    Topic,
)


async def create_institute(session: AsyncSession, **kwargs) -> Institute:
    inst = Institute(**kwargs)
    session.add(inst)
    await session.flush()
    return inst


async def get_institute(session: AsyncSession, inst_id: uuid.UUID) -> Institute | None:
    result = await session.execute(
        select(Institute).where(Institute.id == inst_id, Institute.is_deleted == False)
    )
    return result.scalar_one_or_none()


async def list_institutes(session: AsyncSession) -> list[Institute]:
    result = await session.execute(
        select(Institute).where(Institute.is_deleted == False)
    )
    return list(result.scalars().all())


async def create_academic_year(session: AsyncSession, **kwargs) -> AcademicYear:
    ay = AcademicYear(**kwargs)
    session.add(ay)
    await session.flush()
    return ay


async def get_academic_year(session: AsyncSession, ay_id: uuid.UUID) -> AcademicYear | None:
    result = await session.execute(
        select(AcademicYear).where(AcademicYear.id == ay_id, AcademicYear.is_deleted == False)
    )
    return result.scalar_one_or_none()


async def list_academic_years(session: AsyncSession, branch_id: uuid.UUID) -> list[AcademicYear]:
    result = await session.execute(
        select(AcademicYear).where(
            AcademicYear.branch_id == branch_id,
            AcademicYear.is_deleted == False,
        )
    )
    return list(result.scalars().all())


async def create_course(session: AsyncSession, **kwargs) -> Course:
    course = Course(**kwargs)
    session.add(course)
    await session.flush()
    return course


async def get_course(session: AsyncSession, course_id: uuid.UUID) -> Course | None:
    result = await session.execute(
        select(Course).where(Course.id == course_id, Course.is_deleted == False)
    )
    return result.scalar_one_or_none()


async def list_courses(session: AsyncSession, branch_id: uuid.UUID, academic_year_id: uuid.UUID) -> list[Course]:
    result = await session.execute(
        select(Course).where(
            Course.branch_id == branch_id,
            Course.academic_year_id == academic_year_id,
            Course.is_deleted == False,
        )
    )
    return list(result.scalars().all())


async def create_subject(session: AsyncSession, **kwargs) -> Subject:
    subj = Subject(**kwargs)
    session.add(subj)
    await session.flush()
    return subj


async def get_subject(session: AsyncSession, subject_id: uuid.UUID) -> Subject | None:
    result = await session.execute(
        select(Subject).where(Subject.id == subject_id, Subject.is_deleted == False)
    )
    return result.scalar_one_or_none()


async def list_subjects(session: AsyncSession, branch_id: uuid.UUID, course_id: uuid.UUID) -> list[Subject]:
    result = await session.execute(
        select(Subject).where(
            Subject.branch_id == branch_id,
            Subject.course_id == course_id,
            Subject.is_deleted == False,
        )
    )
    return list(result.scalars().all())


async def create_chapter(session: AsyncSession, **kwargs) -> Chapter:
    ch = Chapter(**kwargs)
    session.add(ch)
    await session.flush()
    return ch


async def get_chapter(session: AsyncSession, chapter_id: uuid.UUID) -> Chapter | None:
    result = await session.execute(
        select(Chapter).where(Chapter.id == chapter_id, Chapter.is_deleted == False)
    )
    return result.scalar_one_or_none()


async def list_chapters(session: AsyncSession, branch_id: uuid.UUID, subject_id: uuid.UUID) -> list[Chapter]:
    result = await session.execute(
        select(Chapter).where(
            Chapter.branch_id == branch_id,
            Chapter.subject_id == subject_id,
            Chapter.is_deleted == False,
        ).order_by(Chapter.order)
    )
    return list(result.scalars().all())


async def create_topic(session: AsyncSession, **kwargs) -> Topic:
    t = Topic(**kwargs)
    session.add(t)
    await session.flush()
    return t


async def get_topic(session: AsyncSession, topic_id: uuid.UUID) -> Topic | None:
    result = await session.execute(
        select(Topic).where(Topic.id == topic_id, Topic.is_deleted == False)
    )
    return result.scalar_one_or_none()


async def list_topics(session: AsyncSession, branch_id: uuid.UUID, chapter_id: uuid.UUID) -> list[Topic]:
    result = await session.execute(
        select(Topic).where(
            Topic.branch_id == branch_id,
            Topic.chapter_id == chapter_id,
            Topic.is_deleted == False,
        ).order_by(Topic.order)
    )
    return list(result.scalars().all())


async def create_subtopic(session: AsyncSession, **kwargs) -> Subtopic:
    st = Subtopic(**kwargs)
    session.add(st)
    await session.flush()
    return st


async def get_subtopic(session: AsyncSession, subtopic_id: uuid.UUID) -> Subtopic | None:
    result = await session.execute(
        select(Subtopic).where(Subtopic.id == subtopic_id, Subtopic.is_deleted == False)
    )
    return result.scalar_one_or_none()


async def list_subtopics(session: AsyncSession, branch_id: uuid.UUID, topic_id: uuid.UUID) -> list[Subtopic]:
    result = await session.execute(
        select(Subtopic).where(
            Subtopic.branch_id == branch_id,
            Subtopic.topic_id == topic_id,
            Subtopic.is_deleted == False,
        ).order_by(Subtopic.order)
    )
    return list(result.scalars().all())
