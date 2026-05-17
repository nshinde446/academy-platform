import json
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ai.providers.mock_provider import MockAIProvider
from app.modules.ai.services import ai_service

BRANCH_A_ID = "00000000-0000-0000-0000-000000000001"
BRANCH_B_ID = "00000000-0000-0000-0000-000000000002"
TOPIC_ID = "00000000-0000-0000-0000-000000000050"
STUDENT_ID = "00000000-0000-0000-0000-000000000090"
BATCH_ID = "00000000-0000-0000-0000-000000000070"
SUBJECT_ID = "00000000-0000-0000-0000-000000000050"


async def _login_admin(client: AsyncClient):
    resp = await client.post("/api/v1/auth/login", json={
        "email": "admin@test.com",
        "password": "Admin123!",
    })
    assert resp.status_code == 200


async def _login_teacher(client: AsyncClient):
    resp = await client.post("/api/v1/auth/login", json={
        "email": "teacher@test.com",
        "password": "Teacher123!",
    })
    assert resp.status_code == 200


@pytest.fixture(autouse=True)
def reset_provider():
    ai_service.set_provider(MockAIProvider())
    yield
    ai_service.set_provider(MockAIProvider())


# ─── Test 1: Generate questions returns valid questions ────────────────────

async def test_generate_questions(client: AsyncClient, seed_data):
    await _login_admin(client)
    resp = await client.post("/api/v1/ai/questions/generate", json={
        "topic_id": TOPIC_ID,
        "count": 5,
        "difficulty": "MEDIUM",
        "branch_id": BRANCH_A_ID,
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "COMPLETED"
    assert len(data["questions"]) == 5
    q = data["questions"][0]
    assert "question_text" in q
    assert "options" in q
    assert len(q["options"]) == 4
    assert "correct_answer" in q
    assert q["difficulty"] == "MEDIUM"


# ─── Test 2: Recommendations return a list of topics/actions ───────────────

async def test_get_recommendations(client: AsyncClient, seed_data):
    await _login_admin(client)
    resp = await client.post("/api/v1/ai/recommendations", json={
        "student_id": STUDENT_ID,
        "limit": 5,
        "branch_id": BRANCH_A_ID,
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "COMPLETED"
    assert len(data["recommendations"]) == 5
    rec = data["recommendations"][0]
    assert "topic" in rec
    assert "action" in rec
    assert "priority" in rec


# ─── Test 3: Tutor response returns a coherent answer ─────────────────────

async def test_tutor_ask(client: AsyncClient, seed_data):
    await _login_admin(client)
    resp = await client.post("/api/v1/ai/tutor/ask", json={
        "student_id": STUDENT_ID,
        "question_text": "What is Newton's second law of motion?",
        "branch_id": BRANCH_A_ID,
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "COMPLETED"
    assert "answer" in data["response"]
    assert "confidence" in data["response"]
    assert data["response"]["confidence"] > 0


# ─── Test 4: DPP generation returns a schedule ────────────────────────────

async def test_generate_dpp(client: AsyncClient, seed_data):
    await _login_admin(client)
    resp = await client.post("/api/v1/ai/dpp/generate", json={
        "batch_id": BATCH_ID,
        "subjects": [SUBJECT_ID],
        "days": 3,
        "branch_id": BRANCH_A_ID,
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "COMPLETED"
    dpp = data["dpp"]
    assert dpp["total_days"] == 3
    assert len(dpp["schedule"]) == 3
    assert len(dpp["schedule"][0]["assignments"]) == 1


# ─── Test 5: Branch isolation – request tagged with correct branch ─────────

async def test_branch_isolation(client: AsyncClient, seed_data):
    await _login_admin(client)
    await client.post("/api/v1/ai/questions/generate", json={
        "topic_id": TOPIC_ID,
        "count": 2,
        "difficulty": "EASY",
        "branch_id": BRANCH_A_ID,
    })
    await client.post("/api/v1/ai/questions/generate", json={
        "topic_id": TOPIC_ID,
        "count": 2,
        "difficulty": "EASY",
        "branch_id": BRANCH_B_ID,
    })

    resp = await client.get("/api/v1/ai/requests", params={"branch_id": BRANCH_A_ID})
    assert resp.status_code == 200
    for req in resp.json():
        assert req["branch_id"] == BRANCH_A_ID

    resp = await client.get("/api/v1/ai/requests", params={"branch_id": BRANCH_B_ID})
    assert resp.status_code == 200
    for req in resp.json():
        assert req["branch_id"] == BRANCH_B_ID


# ─── Test 6: AI request tracking (list requests) ──────────────────────────

async def test_list_requests(client: AsyncClient, seed_data):
    await _login_admin(client)
    await client.post("/api/v1/ai/questions/generate", json={
        "topic_id": TOPIC_ID, "count": 1, "difficulty": "HARD", "branch_id": BRANCH_A_ID,
    })
    await client.post("/api/v1/ai/recommendations", json={
        "student_id": STUDENT_ID, "limit": 3, "branch_id": BRANCH_A_ID,
    })

    resp = await client.get("/api/v1/ai/requests")
    assert resp.status_code == 200
    assert len(resp.json()) >= 2


# ─── Test 7: Get single AI request detail ──────────────────────────────────

async def test_get_request_detail(client: AsyncClient, seed_data):
    await _login_admin(client)
    gen_resp = await client.post("/api/v1/ai/questions/generate", json={
        "topic_id": TOPIC_ID, "count": 1, "difficulty": "EASY", "branch_id": BRANCH_A_ID,
    })
    request_id = gen_resp.json()["request_id"]

    resp = await client.get(f"/api/v1/ai/requests/{request_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["request_type"] == "QUESTION_GENERATION"
    assert data["request_status"] == "COMPLETED"


# ─── Test 8: Audit logging for AI request ─────────────────────────────────

async def test_audit_log_for_ai_request(client: AsyncClient, seed_data):
    await _login_admin(client)
    await client.post("/api/v1/ai/questions/generate", json={
        "topic_id": TOPIC_ID, "count": 1, "difficulty": "EASY", "branch_id": BRANCH_A_ID,
    })

    resp = await client.get("/api/v1/audit/logs", params={"table_name": "ai_requests"})
    assert resp.status_code == 200
    logs = resp.json()["items"]
    ai_logs = [l for l in logs if l["table_name"] == "ai_requests"]
    assert len(ai_logs) >= 1


# ─── Test 9: Process request (mock Celery task) ───────────────────────────

async def test_process_request(client: AsyncClient, seed_data, db_session: AsyncSession):
    await _login_admin(client)

    from app.modules.ai.repositories import ai_repository
    ai_req = await ai_repository.create_request(
        db_session,
        request_type="QUESTION_GENERATION",
        request_status="PENDING",
        payload_json=json.dumps({"topic_id": TOPIC_ID, "count": 3, "difficulty": "EASY"}),
        requested_by=uuid.UUID("00000000-0000-0000-0000-000000000100"),
        branch_id=uuid.UUID(BRANCH_A_ID),
    )
    await db_session.commit()

    result = await ai_service.process_request(db_session, ai_req.id)
    assert result["status"] == "COMPLETED"


# ─── Test 10: Provider switching ──────────────────────────────────────────

async def test_provider_switching(client: AsyncClient, seed_data):
    await _login_admin(client)

    resp = await client.post("/api/v1/ai/questions/generate", json={
        "topic_id": TOPIC_ID, "count": 2, "difficulty": "EASY", "branch_id": BRANCH_A_ID,
    })
    assert resp.status_code == 201
    assert resp.json()["status"] == "COMPLETED"

    from app.modules.ai.providers.openai_provider import OpenAIProvider
    ai_service.register_provider("openai", OpenAIProvider)
    ai_service.set_provider(OpenAIProvider())

    resp = await client.post("/api/v1/ai/questions/generate", json={
        "topic_id": TOPIC_ID, "count": 2, "difficulty": "EASY", "branch_id": BRANCH_A_ID,
    })
    assert resp.status_code == 500

    ai_service.set_provider(MockAIProvider())

    resp = await client.post("/api/v1/ai/questions/generate", json={
        "topic_id": TOPIC_ID, "count": 2, "difficulty": "EASY", "branch_id": BRANCH_A_ID,
    })
    assert resp.status_code == 201
    assert resp.json()["status"] == "COMPLETED"


# ─── Test 11: RBAC – teacher cannot generate questions ─────────────────────

async def test_teacher_cannot_generate_questions(client: AsyncClient, seed_data):
    await _login_teacher(client)
    resp = await client.post("/api/v1/ai/questions/generate", json={
        "topic_id": TOPIC_ID, "count": 1, "difficulty": "EASY", "branch_id": BRANCH_A_ID,
    })
    assert resp.status_code == 403


# ─── Test 12: RBAC – teacher cannot list AI requests ──────────────────────

async def test_teacher_cannot_list_requests(client: AsyncClient, seed_data):
    await _login_teacher(client)
    resp = await client.get("/api/v1/ai/requests")
    assert resp.status_code == 403


# ─── Test 13: RBAC – teacher can generate DPP ─────────────────────────────

async def test_teacher_can_generate_dpp(client: AsyncClient, seed_data):
    await _login_teacher(client)
    resp = await client.post("/api/v1/ai/dpp/generate", json={
        "batch_id": BATCH_ID,
        "subjects": [SUBJECT_ID],
        "days": 2,
        "branch_id": BRANCH_A_ID,
    })
    assert resp.status_code == 201
    assert resp.json()["status"] == "COMPLETED"


# ─── Test 14: RBAC – teacher can get recommendations ──────────────────────

async def test_teacher_can_get_recommendations(client: AsyncClient, seed_data):
    await _login_teacher(client)
    resp = await client.post("/api/v1/ai/recommendations", json={
        "student_id": STUDENT_ID,
        "limit": 3,
        "branch_id": BRANCH_A_ID,
    })
    assert resp.status_code == 201
    assert resp.json()["status"] == "COMPLETED"


# ─── Test 15: Question count and difficulty validated ──────────────────────

async def test_question_validation(client: AsyncClient, seed_data):
    await _login_admin(client)
    resp = await client.post("/api/v1/ai/questions/generate", json={
        "topic_id": TOPIC_ID,
        "count": 3,
        "difficulty": "HARD",
        "branch_id": BRANCH_A_ID,
    })
    assert resp.status_code == 201
    questions = resp.json()["questions"]
    assert len(questions) == 3
    for q in questions:
        assert q["difficulty"] == "HARD"
