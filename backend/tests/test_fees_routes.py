"""Accounts / Fees — route wiring + RBAC (slice 1)."""

from httpx import AsyncClient

BRANCH = "00000000-0000-0000-0000-000000000001"
STUDENT = "00000000-0000-0000-0000-000000000090"
BATCH = "00000000-0000-0000-0000-000000000070"


async def _login_admin(client: AsyncClient):
    r = await client.post("/api/v1/auth/login", json={
        "email": "admin@test.com", "password": "Admin123!",
    })
    assert r.status_code == 200


async def test_config_and_profile_roundtrip(client: AsyncClient, seed_data):
    await _login_admin(client)
    # Manager sets a course fee.
    r = await client.post(
        f"/api/v1/fees/config?branch_id={BRANCH}",
        json={"course_name": "CET", "standard_fee": 160000},
    )
    assert r.status_code == 200, r.text
    assert r.json()["standard_fee"] == 160000

    # Create an installment fee profile; the schedule comes back.
    r = await client.post(
        f"/api/v1/fees/student?branch_id={BRANCH}",
        json={
            "student_id": STUDENT, "batch_id": BATCH,
            "actual_fee": 160000, "agreed_fee": 150000,
            "payment_mode": "INSTALLMENT", "admission_date": "2026-10-08",
            "first_installment": 50000, "remaining_installments": 4,
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["discount_amount"] == 10000
    assert len(body["installments"]) == 5

    # Read it back.
    r = await client.get(f"/api/v1/fees/student/{STUDENT}?branch_id={BRANCH}")
    assert r.status_code == 200
    assert r.json()["total_pending"] == 150000


async def test_endpoints_require_auth(client: AsyncClient, seed_data):
    # No login → rejected, nothing created.
    r = await client.get(f"/api/v1/fees/config?branch_id={BRANCH}")
    assert r.status_code in (401, 403)
    r = await client.post(
        f"/api/v1/fees/config?branch_id={BRANCH}",
        json={"course_name": "CET", "standard_fee": 1},
    )
    assert r.status_code in (401, 403)
