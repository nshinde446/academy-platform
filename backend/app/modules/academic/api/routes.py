import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.modules.auth.permissions.rbac import get_current_user, require_roles
from app.modules.academic.repositories import academic_repository
from app.modules.academic.schemas.academic_schemas import (
    AcademicYearCreate, AcademicYearResponse,
    ChapterCreate, ChapterResponse,
    CourseCreate, CourseResponse, CourseUpdate,
    InstituteCreate, InstituteResponse,
    SubjectCreate, SubjectResponse,
    SubtopicCreate, SubtopicResponse,
    TopicCreate, TopicResponse,
)
from app.modules.academic.services import academic_service

router = APIRouter(prefix="/academic", tags=["academic"])


@router.post("/institutes", response_model=InstituteResponse)
async def create_institute(
    body: InstituteCreate,
    request: Request,
    current_user: dict = Depends(require_roles(["super_admin"])),
    session: AsyncSession = Depends(get_db),
):
    inst = await academic_service.create_institute(
        session, body.model_dump(), current_user["user_id"], request.client.host if request.client else None,
    )
    return inst


@router.get("/institutes", response_model=list[InstituteResponse])
async def list_institutes(
    _current_user: dict = Depends(require_roles(["super_admin"])),
    session: AsyncSession = Depends(get_db),
):
    return await academic_repository.list_institutes(session)


@router.post("/academic-years", response_model=AcademicYearResponse)
async def create_academic_year(
    body: AcademicYearCreate,
    request: Request,
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin"])),
    session: AsyncSession = Depends(get_db),
):
    return await academic_service.create_academic_year(
        session, body.model_dump(), current_user["user_id"], request.client.host if request.client else None,
    )


@router.get("/academic-years", response_model=list[AcademicYearResponse])
async def list_academic_years(
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    return await academic_repository.list_academic_years(session, branch_id)


@router.delete("/academic-years/{ay_id}", status_code=204)
async def delete_academic_year(
    ay_id: uuid.UUID,
    request: Request,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin"])),
    session: AsyncSession = Depends(get_db),
):
    await academic_service.delete_academic_year(
        session, ay_id, branch_id, current_user["user_id"],
        request.client.host if request.client else None,
    )


@router.post("/courses", response_model=CourseResponse)
async def create_course(
    body: CourseCreate,
    request: Request,
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin"])),
    session: AsyncSession = Depends(get_db),
):
    return await academic_service.create_course(
        session, body.model_dump(), current_user["user_id"], request.client.host if request.client else None,
    )


@router.get("/courses", response_model=list[CourseResponse])
async def list_courses(
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    return await academic_repository.list_courses(session, branch_id)


@router.patch("/courses/{course_id}", response_model=CourseResponse)
async def update_course(
    course_id: uuid.UUID,
    body: CourseUpdate,
    request: Request,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin"])),
    session: AsyncSession = Depends(get_db),
):
    return await academic_service.update_course(
        session, course_id, body.model_dump(exclude_unset=True), branch_id,
        current_user["user_id"], request.client.host if request.client else None,
    )


@router.delete("/courses/{course_id}", status_code=204)
async def delete_course(
    course_id: uuid.UUID,
    request: Request,
    branch_id: uuid.UUID = Query(...),
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin"])),
    session: AsyncSession = Depends(get_db),
):
    await academic_service.delete_course(
        session, course_id, branch_id, current_user["user_id"],
        request.client.host if request.client else None,
    )


@router.post("/subjects", response_model=SubjectResponse)
async def create_subject(
    body: SubjectCreate,
    request: Request,
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin"])),
    session: AsyncSession = Depends(get_db),
):
    return await academic_service.create_subject(
        session, body.model_dump(), current_user["user_id"], request.client.host if request.client else None,
    )


@router.get("/subjects", response_model=list[SubjectResponse])
async def list_subjects(
    branch_id: uuid.UUID = Query(...),
    # course_id is optional — when omitted, returns every subject in the
    # branch. Callers like the Materials upload form want the full pool
    # without choosing a course first.
    course_id: uuid.UUID | None = Query(None),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    return await academic_repository.list_subjects(session, branch_id, course_id)


@router.post("/chapters", response_model=ChapterResponse)
async def create_chapter(
    body: ChapterCreate,
    request: Request,
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin"])),
    session: AsyncSession = Depends(get_db),
):
    return await academic_service.create_chapter(
        session, body.model_dump(), current_user["user_id"], request.client.host if request.client else None,
    )


@router.get("/chapters", response_model=list[ChapterResponse])
async def list_chapters(
    branch_id: uuid.UUID = Query(...),
    subject_id: uuid.UUID = Query(...),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    return await academic_repository.list_chapters(session, branch_id, subject_id)


@router.post("/topics", response_model=TopicResponse)
async def create_topic(
    body: TopicCreate,
    request: Request,
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin"])),
    session: AsyncSession = Depends(get_db),
):
    return await academic_service.create_topic(
        session, body.model_dump(), current_user["user_id"], request.client.host if request.client else None,
    )


@router.get("/topics", response_model=list[TopicResponse])
async def list_topics(
    branch_id: uuid.UUID = Query(...),
    chapter_id: uuid.UUID | None = Query(None),
    subject_id: uuid.UUID | None = Query(None),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    if subject_id is not None:
        return await academic_repository.list_topics_by_subject(
            session, branch_id, subject_id
        )
    if chapter_id is None:
        from fastapi import HTTPException, status as http_status
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Either chapter_id or subject_id is required",
        )
    return await academic_repository.list_topics(session, branch_id, chapter_id)


@router.post("/subtopics", response_model=SubtopicResponse)
async def create_subtopic(
    body: SubtopicCreate,
    request: Request,
    current_user: dict = Depends(require_roles(["super_admin", "branch_admin"])),
    session: AsyncSession = Depends(get_db),
):
    return await academic_service.create_subtopic(
        session, body.model_dump(), current_user["user_id"], request.client.host if request.client else None,
    )


@router.get("/subtopics", response_model=list[SubtopicResponse])
async def list_subtopics(
    branch_id: uuid.UUID = Query(...),
    topic_id: uuid.UUID = Query(...),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    return await academic_repository.list_subtopics(session, branch_id, topic_id)
