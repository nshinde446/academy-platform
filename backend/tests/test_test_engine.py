import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient

BRANCH_A_ID = "00000000-0000-0000-0000-000000000001"
BRANCH_B_ID = "00000000-0000-0000-0000-000000000002"
BATCH_ID = "00000000-0000-0000-0000-000000000070"
SUBJECT_ID = "00000000-0000-0000-0000-000000000050"
STUDENT_ID = "00000000-0000-0000-0000-000000000090"
ACADEMIC_YEAR_ID = "00000000-0000-0000-0000-000000000030"


async def _login_admin(client: AsyncClient):
    resp = await client.post("/api/v1/auth/login", json={
        "email": "admin@test.com",
        "password": "Admin123!",
    })
    assert resp.status_code == 200


def _question_payload():
    return {
        "content": "What is Newton's second law of motion?",
        "options": {"A": "F=ma", "B": "E=mc²", "C": "V=IR", "D": "P=IV"},
        "correct_answer": "A",
        "explanation": "Newton's second law relates force, mass, and acceleration.",
        "subject_id": SUBJECT_ID,
        "difficulty": "MEDIUM",
        "blooms_taxonomy": "REMEMBER",
        "concept_tags": ["physics", "mechanics", "newton"],
    }


async def _create_question(client: AsyncClient, payload=None):
    if payload is None:
        payload = _question_payload()
    resp = await client.post(
        "/api/v1/questions",
        params={"branch_id": BRANCH_A_ID, "academic_year_id": ACADEMIC_YEAR_ID},
        json=payload,
    )
    assert resp.status_code == 200
    return resp.json()


async def _create_test(client: AsyncClient):
    resp = await client.post("/api/v1/tests", json={
        "name": "Unit Test 1 - Physics",
        "description": "First unit test",
        "batch_id": BATCH_ID,
        "subject_id": SUBJECT_ID,
        "duration_minutes": 60,
        "total_marks": 100.0,
    })
    assert resp.status_code == 200
    return resp.json()


# ─── Test 1: Create a question ─────────────────────────────────────────────────

async def test_create_question(client: AsyncClient, seed_data):
    await _login_admin(client)
    question = await _create_question(client)
    assert question["content"] == "What is Newton's second law of motion?"
    assert question["difficulty"] == "MEDIUM"
    assert question["options"]["A"] == "F=ma"
    assert question["concept_tags"] == ["physics", "mechanics", "newton"]


# ─── Test 2: List questions with filtering ─────────────────────────────────────

async def test_list_questions(client: AsyncClient, seed_data):
    await _login_admin(client)
    await _create_question(client)
    resp = await client.get(
        "/api/v1/questions",
        params={"branch_id": BRANCH_A_ID, "difficulty": "MEDIUM"},
    )
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


# ─── Test 3: Get question by ID ────────────────────────────────────────────────

async def test_get_question(client: AsyncClient, seed_data):
    await _login_admin(client)
    question = await _create_question(client)
    resp = await client.get(
        f"/api/v1/questions/{question['id']}",
        params={"branch_id": BRANCH_A_ID},
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == question["id"]


# ─── Test 4: Update a question ─────────────────────────────────────────────────

async def test_update_question(client: AsyncClient, seed_data):
    await _login_admin(client)
    question = await _create_question(client)
    resp = await client.patch(
        f"/api/v1/questions/{question['id']}",
        params={"branch_id": BRANCH_A_ID},
        json={"difficulty": "HARD", "blooms_taxonomy": "APPLY"},
    )
    assert resp.status_code == 200
    assert resp.json()["difficulty"] == "HARD"
    assert resp.json()["blooms_taxonomy"] == "APPLY"


# ─── Test 5: Soft delete a question ────────────────────────────────────────────

async def test_delete_question(client: AsyncClient, seed_data):
    await _login_admin(client)
    question = await _create_question(client)
    resp = await client.delete(
        f"/api/v1/questions/{question['id']}",
        params={"branch_id": BRANCH_A_ID},
    )
    assert resp.status_code == 204
    resp = await client.get(
        f"/api/v1/questions/{question['id']}",
        params={"branch_id": BRANCH_A_ID},
    )
    assert resp.status_code == 404


# ─── Test 6: Create a test ─────────────────────────────────────────────────────

async def test_create_test(client: AsyncClient, seed_data):
    await _login_admin(client)
    test = await _create_test(client)
    assert test["name"] == "Unit Test 1 - Physics"
    assert test["test_status"] == "DRAFT"
    assert test["branch_id"] == BRANCH_A_ID


# ─── Test 7: Add questions to test ─────────────────────────────────────────────

async def test_add_questions_to_test(client: AsyncClient, seed_data):
    await _login_admin(client)
    question = await _create_question(client)
    test = await _create_test(client)
    resp = await client.post(
        f"/api/v1/tests/{test['id']}/questions",
        params={"branch_id": BRANCH_A_ID},
        json={"questions": [{"question_id": question["id"], "marks_allocated": 10.0, "order": 1}]},
    )
    assert resp.status_code == 200


# ─── Test 8: Publish a test ────────────────────────────────────────────────────

async def test_publish_test(client: AsyncClient, seed_data):
    await _login_admin(client)
    test = await _create_test(client)
    resp = await client.patch(
        f"/api/v1/tests/{test['id']}/publish",
        params={"branch_id": BRANCH_A_ID},
    )
    assert resp.status_code == 200
    assert resp.json()["test_status"] == "ACTIVE"


# ─── Test 9: Cannot publish already active test ────────────────────────────────

async def test_cannot_publish_active_test(client: AsyncClient, seed_data):
    await _login_admin(client)
    test = await _create_test(client)
    await client.patch(
        f"/api/v1/tests/{test['id']}/publish",
        params={"branch_id": BRANCH_A_ID},
    )
    resp = await client.patch(
        f"/api/v1/tests/{test['id']}/publish",
        params={"branch_id": BRANCH_A_ID},
    )
    assert resp.status_code == 422
    assert "Cannot publish" in resp.json()["error"]["message"]


# ─── Test 10: Submit marks ─────────────────────────────────────────────────────

async def test_submit_marks(client: AsyncClient, seed_data):
    await _login_admin(client)
    test = await _create_test(client)
    resp = await client.post(
        "/api/v1/marks",
        params={"test_id": test["id"], "branch_id": BRANCH_A_ID},
        json={"marks": [{"student_id": STUDENT_ID, "marks_obtained": 85.0}]},
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    mark = resp.json()[0]
    assert mark["marks_obtained"] == 85.0
    assert mark["percentage"] == 85.0
    assert mark["grade"] == "A"


# ─── Test 11: Submit marks for absent student ──────────────────────────────────

async def test_submit_marks_absent(client: AsyncClient, seed_data):
    await _login_admin(client)
    test = await _create_test(client)
    resp = await client.post(
        "/api/v1/marks",
        params={"test_id": test["id"], "branch_id": BRANCH_A_ID},
        json={"marks": [{"student_id": STUDENT_ID, "marks_obtained": 0, "is_absent": True}]},
    )
    assert resp.status_code == 200
    mark = resp.json()[0]
    assert mark["is_absent"] is True
    assert mark["grade"] is None


# ─── Test 12: Update marks (override) ─────────────────────────────────────────

async def test_update_marks_override(client: AsyncClient, seed_data):
    await _login_admin(client)
    test = await _create_test(client)
    await client.post(
        "/api/v1/marks",
        params={"test_id": test["id"], "branch_id": BRANCH_A_ID},
        json={"marks": [{"student_id": STUDENT_ID, "marks_obtained": 50.0}]},
    )
    resp = await client.post(
        "/api/v1/marks",
        params={"test_id": test["id"], "branch_id": BRANCH_A_ID},
        json={"marks": [{"student_id": STUDENT_ID, "marks_obtained": 75.0}]},
    )
    assert resp.status_code == 200
    assert resp.json()[0]["marks_obtained"] == 75.0
    assert resp.json()[0]["percentage"] == 75.0


# ─── Test 13: Get test marks ──────────────────────────────────────────────────

async def test_get_test_marks(client: AsyncClient, seed_data):
    await _login_admin(client)
    test = await _create_test(client)
    await client.post(
        "/api/v1/marks",
        params={"test_id": test["id"], "branch_id": BRANCH_A_ID},
        json={"marks": [{"student_id": STUDENT_ID, "marks_obtained": 80.0}]},
    )
    resp = await client.get(
        f"/api/v1/tests/{test['id']}/marks",
        params={"branch_id": BRANCH_A_ID},
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 1


# ─── Test 14: Get student marks history ────────────────────────────────────────

async def test_get_student_marks(client: AsyncClient, seed_data):
    await _login_admin(client)
    test = await _create_test(client)
    await client.post(
        "/api/v1/marks",
        params={"test_id": test["id"], "branch_id": BRANCH_A_ID},
        json={"marks": [{"student_id": STUDENT_ID, "marks_obtained": 70.0}]},
    )
    resp = await client.get(
        f"/api/v1/marks/student/{STUDENT_ID}",
        params={"branch_id": BRANCH_A_ID},
    )
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


# ─── Test 15: Test report generation ──────────────────────────────────────────

async def test_report_generation(client: AsyncClient, seed_data):
    await _login_admin(client)
    test = await _create_test(client)
    await client.post(
        "/api/v1/marks",
        params={"test_id": test["id"], "branch_id": BRANCH_A_ID},
        json={"marks": [{"student_id": STUDENT_ID, "marks_obtained": 72.0}]},
    )
    resp = await client.get(
        f"/api/v1/tests/{test['id']}/report",
        params={"branch_id": BRANCH_A_ID},
    )
    assert resp.status_code == 200
    report = resp.json()
    assert report["total_students"] == 1
    assert report["appeared"] == 1
    assert report["absent"] == 0
    assert report["highest"] == 72.0
    assert report["pass_count"] == 1


# ─── Test 16: Branch isolation on questions ────────────────────────────────────

async def test_branch_isolation_question(client: AsyncClient, seed_data):
    await _login_admin(client)
    question = await _create_question(client)
    resp = await client.get(
        f"/api/v1/questions/{question['id']}",
        params={"branch_id": BRANCH_B_ID},
    )
    assert resp.status_code == 403


# ─── Test 17: Branch isolation on tests ────────────────────────────────────────

async def test_branch_isolation_test(client: AsyncClient, seed_data):
    await _login_admin(client)
    test = await _create_test(client)
    resp = await client.get(
        f"/api/v1/tests/{test['id']}",
        params={"branch_id": BRANCH_B_ID},
    )
    assert resp.status_code == 403


# ─── Test 18: Audit log on question creation ──────────────────────────────────

async def test_audit_log_question(client: AsyncClient, seed_data):
    await _login_admin(client)
    await _create_question(client)
    resp = await client.get("/api/v1/audit/logs", params={"table_name": "questions"})
    assert resp.status_code == 200
    logs = resp.json()["items"]
    assert any(log["action"] == "CREATE" and log["table_name"] == "questions" for log in logs)


# ─── Test 19: Invalid difficulty ───────────────────────────────────────────────

async def test_invalid_difficulty(client: AsyncClient, seed_data):
    await _login_admin(client)
    payload = _question_payload()
    payload["difficulty"] = "IMPOSSIBLE"
    resp = await client.post(
        "/api/v1/questions",
        params={"branch_id": BRANCH_A_ID, "academic_year_id": ACADEMIC_YEAR_ID},
        json=payload,
    )
    assert resp.status_code == 422
    assert "Invalid difficulty" in resp.json()["error"]["message"]
