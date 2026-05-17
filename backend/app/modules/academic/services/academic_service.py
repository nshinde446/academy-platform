import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.academic.repositories import academic_repository
from app.modules.audit.services import audit_service


async def create_institute(session: AsyncSession, data: dict, current_user_id: uuid.UUID, ip_address: str | None = None):
    inst = await academic_repository.create_institute(session, **data)
    await audit_service.log_action(
        session, user_id=current_user_id, action="CREATE",
        table_name="institutes", record_id=inst.id, new_values=data, ip_address=ip_address,
    )
    return inst


async def create_academic_year(session: AsyncSession, data: dict, current_user_id: uuid.UUID, ip_address: str | None = None):
    ay = await academic_repository.create_academic_year(session, **data)
    await audit_service.log_action(
        session, user_id=current_user_id, action="CREATE",
        table_name="academic_years", record_id=ay.id, new_values=data,
        ip_address=ip_address, branch_id=data.get("branch_id"),
    )
    return ay


async def create_course(session: AsyncSession, data: dict, current_user_id: uuid.UUID, ip_address: str | None = None):
    course = await academic_repository.create_course(session, **data)
    await audit_service.log_action(
        session, user_id=current_user_id, action="CREATE",
        table_name="courses", record_id=course.id, new_values=data,
        ip_address=ip_address, branch_id=data.get("branch_id"),
    )
    return course


async def create_subject(session: AsyncSession, data: dict, current_user_id: uuid.UUID, ip_address: str | None = None):
    subj = await academic_repository.create_subject(session, **data)
    await audit_service.log_action(
        session, user_id=current_user_id, action="CREATE",
        table_name="subjects", record_id=subj.id, new_values=data,
        ip_address=ip_address, branch_id=data.get("branch_id"),
    )
    return subj


async def create_chapter(session: AsyncSession, data: dict, current_user_id: uuid.UUID, ip_address: str | None = None):
    ch = await academic_repository.create_chapter(session, **data)
    await audit_service.log_action(
        session, user_id=current_user_id, action="CREATE",
        table_name="chapters", record_id=ch.id, new_values=data,
        ip_address=ip_address, branch_id=data.get("branch_id"),
    )
    return ch


async def create_topic(session: AsyncSession, data: dict, current_user_id: uuid.UUID, ip_address: str | None = None):
    t = await academic_repository.create_topic(session, **data)
    await audit_service.log_action(
        session, user_id=current_user_id, action="CREATE",
        table_name="topics", record_id=t.id, new_values=data,
        ip_address=ip_address, branch_id=data.get("branch_id"),
    )
    return t


async def create_subtopic(session: AsyncSession, data: dict, current_user_id: uuid.UUID, ip_address: str | None = None):
    st = await academic_repository.create_subtopic(session, **data)
    await audit_service.log_action(
        session, user_id=current_user_id, action="CREATE",
        table_name="subtopics", record_id=st.id, new_values=data,
        ip_address=ip_address, branch_id=data.get("branch_id"),
    )
    return st
