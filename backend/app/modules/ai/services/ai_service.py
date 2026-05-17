import json
import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ai.providers.base_provider import BaseAIProvider
from app.modules.ai.providers.mock_provider import MockAIProvider
from app.modules.ai.repositories import ai_repository
from app.modules.audit.services import audit_service

_provider_registry: dict[str, type[BaseAIProvider]] = {
    "mock": MockAIProvider,
}

_active_provider: BaseAIProvider = MockAIProvider()


def get_provider() -> BaseAIProvider:
    return _active_provider


def set_provider(provider: BaseAIProvider) -> None:
    global _active_provider
    _active_provider = provider


def register_provider(name: str, provider_class: type[BaseAIProvider]) -> None:
    _provider_registry[name] = provider_class


async def switch_provider(
    session: AsyncSession, provider_name: str, branch_id: uuid.UUID | None = None
) -> None:
    if provider_name not in _provider_registry:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown provider: {provider_name}",
        )
    global _active_provider
    _active_provider = _provider_registry[provider_name]()


async def generate_questions(
    session: AsyncSession,
    *,
    topic_id: uuid.UUID,
    count: int,
    difficulty: str,
    branch_id: uuid.UUID | None,
    current_user_id: uuid.UUID,
    ip_address: str | None = None,
) -> dict:
    payload = {
        "topic_id": str(topic_id),
        "count": count,
        "difficulty": difficulty,
    }

    ai_req = await ai_repository.create_request(
        session,
        request_type="QUESTION_GENERATION",
        request_status="PENDING",
        payload_json=json.dumps(payload, default=str),
        requested_by=current_user_id,
        branch_id=branch_id,
    )

    await audit_service.log_action(
        session,
        user_id=current_user_id,
        action="CREATE",
        table_name="ai_requests",
        record_id=ai_req.id,
        new_values=payload,
        ip_address=ip_address,
    )

    try:
        provider = get_provider()
        questions = await provider.generate_questions(topic_id, count, difficulty, branch_id)
        response_data = {"questions": questions}
        ai_req = await ai_repository.update_request(
            session,
            ai_req,
            request_status="COMPLETED",
            response_json=json.dumps(response_data, default=str),
        )
    except Exception as exc:
        ai_req = await ai_repository.update_request(
            session,
            ai_req,
            request_status="FAILED",
            error_message=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI request failed: {exc}",
        )

    return {
        "request_id": ai_req.id,
        "status": ai_req.request_status,
        "questions": questions,
    }


async def get_recommendations(
    session: AsyncSession,
    *,
    student_id: uuid.UUID,
    limit: int,
    branch_id: uuid.UUID | None,
    current_user_id: uuid.UUID,
    ip_address: str | None = None,
) -> dict:
    payload = {"student_id": str(student_id), "limit": limit}

    ai_req = await ai_repository.create_request(
        session,
        request_type="RECOMMENDATION",
        request_status="PENDING",
        payload_json=json.dumps(payload, default=str),
        requested_by=current_user_id,
        branch_id=branch_id,
    )

    await audit_service.log_action(
        session,
        user_id=current_user_id,
        action="CREATE",
        table_name="ai_requests",
        record_id=ai_req.id,
        new_values=payload,
        ip_address=ip_address,
    )

    try:
        provider = get_provider()
        recommendations = await provider.get_recommendations(student_id, limit, branch_id)
        response_data = {"recommendations": recommendations}
        ai_req = await ai_repository.update_request(
            session,
            ai_req,
            request_status="COMPLETED",
            response_json=json.dumps(response_data, default=str),
        )
    except Exception as exc:
        await ai_repository.update_request(
            session, ai_req, request_status="FAILED", error_message=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI request failed: {exc}",
        )

    return {
        "request_id": ai_req.id,
        "status": ai_req.request_status,
        "recommendations": recommendations,
    }


async def tutor_ask(
    session: AsyncSession,
    *,
    student_id: uuid.UUID,
    question_text: str,
    context: str | None,
    branch_id: uuid.UUID | None,
    current_user_id: uuid.UUID,
    ip_address: str | None = None,
) -> dict:
    payload = {
        "student_id": str(student_id),
        "question_text": question_text,
        "context": context,
    }

    ai_req = await ai_repository.create_request(
        session,
        request_type="TUTOR",
        request_status="PENDING",
        payload_json=json.dumps(payload, default=str),
        requested_by=current_user_id,
        branch_id=branch_id,
    )

    await audit_service.log_action(
        session,
        user_id=current_user_id,
        action="CREATE",
        table_name="ai_requests",
        record_id=ai_req.id,
        new_values=payload,
        ip_address=ip_address,
    )

    try:
        provider = get_provider()
        response = await provider.tutor_response(student_id, question_text, context, branch_id)
        ai_req = await ai_repository.update_request(
            session,
            ai_req,
            request_status="COMPLETED",
            response_json=json.dumps(response, default=str),
        )
    except Exception as exc:
        await ai_repository.update_request(
            session, ai_req, request_status="FAILED", error_message=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI request failed: {exc}",
        )

    return {
        "request_id": ai_req.id,
        "status": ai_req.request_status,
        "response": response,
    }


async def generate_dpp(
    session: AsyncSession,
    *,
    batch_id: uuid.UUID,
    subjects: list[uuid.UUID],
    days: int,
    branch_id: uuid.UUID | None,
    current_user_id: uuid.UUID,
    ip_address: str | None = None,
) -> dict:
    payload = {
        "batch_id": str(batch_id),
        "subjects": [str(s) for s in subjects],
        "days": days,
    }

    ai_req = await ai_repository.create_request(
        session,
        request_type="DPP_GENERATION",
        request_status="PENDING",
        payload_json=json.dumps(payload, default=str),
        requested_by=current_user_id,
        branch_id=branch_id,
    )

    await audit_service.log_action(
        session,
        user_id=current_user_id,
        action="CREATE",
        table_name="ai_requests",
        record_id=ai_req.id,
        new_values=payload,
        ip_address=ip_address,
    )

    try:
        provider = get_provider()
        dpp = await provider.generate_dpp(batch_id, subjects, days, branch_id)
        ai_req = await ai_repository.update_request(
            session,
            ai_req,
            request_status="COMPLETED",
            response_json=json.dumps(dpp, default=str),
        )
    except Exception as exc:
        await ai_repository.update_request(
            session, ai_req, request_status="FAILED", error_message=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI request failed: {exc}",
        )

    return {
        "request_id": ai_req.id,
        "status": ai_req.request_status,
        "dpp": dpp,
    }


async def process_request(session: AsyncSession, request_id: uuid.UUID) -> dict:
    ai_req = await ai_repository.get_request(session, request_id)
    if not ai_req:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="AI request not found"
        )

    if ai_req.request_status != "PENDING":
        return {
            "request_id": ai_req.id,
            "status": ai_req.request_status,
        }

    await ai_repository.update_request(session, ai_req, request_status="PROCESSING")

    try:
        payload = json.loads(ai_req.payload_json) if ai_req.payload_json else {}
        provider = get_provider()

        if ai_req.request_type == "QUESTION_GENERATION":
            result = await provider.generate_questions(
                uuid.UUID(payload["topic_id"]),
                payload.get("count", 5),
                payload.get("difficulty", "MEDIUM"),
                ai_req.branch_id,
            )
        elif ai_req.request_type == "RECOMMENDATION":
            result = await provider.get_recommendations(
                uuid.UUID(payload["student_id"]),
                payload.get("limit", 10),
                ai_req.branch_id,
            )
        elif ai_req.request_type == "TUTOR":
            result = await provider.tutor_response(
                uuid.UUID(payload["student_id"]),
                payload["question_text"],
                payload.get("context"),
                ai_req.branch_id,
            )
        elif ai_req.request_type == "DPP_GENERATION":
            result = await provider.generate_dpp(
                uuid.UUID(payload["batch_id"]),
                [uuid.UUID(s) for s in payload["subjects"]],
                payload.get("days", 7),
                ai_req.branch_id,
            )
        else:
            raise ValueError(f"Unknown request type: {ai_req.request_type}")

        await ai_repository.update_request(
            session,
            ai_req,
            request_status="COMPLETED",
            response_json=json.dumps(result, default=str),
        )
        return {"request_id": ai_req.id, "status": "COMPLETED"}

    except Exception as exc:
        await ai_repository.update_request(
            session, ai_req, request_status="FAILED", error_message=str(exc),
        )
        return {"request_id": ai_req.id, "status": "FAILED", "error": str(exc)}


async def list_requests(
    session: AsyncSession,
    request_type: str | None = None,
    request_status: str | None = None,
    branch_id: uuid.UUID | None = None,
    offset: int = 0,
    limit: int = 50,
):
    return await ai_repository.list_requests(
        session, request_type, request_status, branch_id, offset=offset, limit=limit,
    )


async def get_request(session: AsyncSession, request_id: uuid.UUID):
    req = await ai_repository.get_request(session, request_id)
    if not req:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="AI request not found"
        )
    return req
