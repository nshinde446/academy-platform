import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.modules.auth.permissions.rbac import require_roles
from app.modules.ai.schemas.ai_schemas import (
    AIRequestResponse,
    DPPGenerateRequest,
    QuestionGenerateRequest,
    RecommendationRequest,
    TutorAskRequest,
)
from app.modules.ai.services import ai_service

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/questions/generate", status_code=201)
async def generate_questions(
    body: QuestionGenerateRequest,
    request: Request,
    current_user: dict = Depends(require_roles(["super_admin", "academic_head"])),
    session: AsyncSession = Depends(get_db),
):
    return await ai_service.generate_questions(
        session,
        topic_id=body.topic_id,
        count=body.count,
        difficulty=body.difficulty,
        branch_id=body.branch_id,
        current_user_id=current_user["user_id"],
        ip_address=request.client.host if request.client else None,
    )


@router.post("/recommendations", status_code=201)
async def get_recommendations(
    body: RecommendationRequest,
    request: Request,
    current_user: dict = Depends(
        require_roles(["super_admin", "branch_admin", "academic_head", "teacher", "student"])
    ),
    session: AsyncSession = Depends(get_db),
):
    return await ai_service.get_recommendations(
        session,
        student_id=body.student_id,
        limit=body.limit,
        branch_id=body.branch_id,
        current_user_id=current_user["user_id"],
        ip_address=request.client.host if request.client else None,
    )


@router.post("/tutor/ask", status_code=201)
async def tutor_ask(
    body: TutorAskRequest,
    request: Request,
    current_user: dict = Depends(require_roles(["super_admin", "student"])),
    session: AsyncSession = Depends(get_db),
):
    return await ai_service.tutor_ask(
        session,
        student_id=body.student_id,
        question_text=body.question_text,
        context=body.context,
        branch_id=body.branch_id,
        current_user_id=current_user["user_id"],
        ip_address=request.client.host if request.client else None,
    )


@router.post("/dpp/generate", status_code=201)
async def generate_dpp(
    body: DPPGenerateRequest,
    request: Request,
    current_user: dict = Depends(
        require_roles(["super_admin", "academic_head", "teacher"])
    ),
    session: AsyncSession = Depends(get_db),
):
    return await ai_service.generate_dpp(
        session,
        batch_id=body.batch_id,
        subjects=body.subjects,
        days=body.days,
        branch_id=body.branch_id,
        current_user_id=current_user["user_id"],
        ip_address=request.client.host if request.client else None,
    )


@router.get("/requests", response_model=list[AIRequestResponse])
async def list_requests(
    request_type: str | None = Query(None),
    request_status: str | None = Query(None),
    branch_id: uuid.UUID | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(require_roles(["super_admin"])),
    session: AsyncSession = Depends(get_db),
):
    return await ai_service.list_requests(
        session,
        request_type=request_type,
        request_status=request_status,
        branch_id=branch_id,
        offset=offset,
        limit=limit,
    )


@router.get("/requests/{request_id}", response_model=AIRequestResponse)
async def get_request(
    request_id: uuid.UUID,
    current_user: dict = Depends(require_roles(["super_admin"])),
    session: AsyncSession = Depends(get_db),
):
    return await ai_service.get_request(session, request_id)
