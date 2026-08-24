"""RBAC access-control endpoints: coordinator batch scope, accounts attendance
grants, audit logging, and the WhatsApp delivery-log report."""

import uuid
from datetime import datetime, timedelta, timezone

from httpx import AsyncClient

BRANCH_A_ID = "00000000-0000-0000-0000-000000000001"
COORD_USER_ID = "00000000-0000-0000-0000-000000000101"  # teacher_user, branch A
BATCH_A = "00000000-0000-0000-0000-000000000070"
BATCH_B = "00000000-0000-0000-0000-000000000071"


async def _login_admin(client: AsyncClient):
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.com", "password": "Admin123!"},
    )
    assert resp.status_code == 200


async def test_set_coordinator_batches_replace_semantics(client, seed_data):
    await _login_admin(client)

    # Assign two batches.
    resp = await client.put(
        f"/api/v1/access/coordinators/{COORD_USER_ID}/batches",
        json={"batch_ids": [BATCH_A, BATCH_B]},
    )
    assert resp.status_code == 200, resp.text
    assert {b["id"] for b in resp.json()["batches"]} == {BATCH_A, BATCH_B}

    # GET reflects it.
    got = await client.get(f"/api/v1/access/coordinators/{COORD_USER_ID}/batches")
    assert {b["id"] for b in got.json()["batches"]} == {BATCH_A, BATCH_B}

    # Replace with just one — the other is dropped.
    resp2 = await client.put(
        f"/api/v1/access/coordinators/{COORD_USER_ID}/batches",
        json={"batch_ids": [BATCH_A]},
    )
    assert {b["id"] for b in resp2.json()["batches"]} == {BATCH_A}


async def test_set_coordinator_rejects_foreign_batch(client, seed_data):
    await _login_admin(client)
    resp = await client.put(
        f"/api/v1/access/coordinators/{COORD_USER_ID}/batches",
        json={"batch_ids": [str(uuid.uuid4())]},
    )
    assert resp.status_code == 400


async def test_coordinator_change_is_audited(client, seed_data):
    await _login_admin(client)
    await client.put(
        f"/api/v1/access/coordinators/{COORD_USER_ID}/batches",
        json={"batch_ids": [BATCH_A]},
    )
    logs = await client.get(
        "/api/v1/audit/logs", params={"table_name": "batch_coordinators"}
    )
    assert logs.status_code == 200, logs.text
    items = logs.json()["items"]
    assert any(it["action"] == "Permission Change" for it in items)


async def test_accounts_grant_create_list_revoke(client, seed_data):
    await _login_admin(client)
    future = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()

    # Batch-scoped, time-limited grant.
    created = await client.post(
        "/api/v1/access/accounts-grants",
        json={"user_id": COORD_USER_ID, "batch_id": BATCH_A, "expires_at": future},
    )
    assert created.status_code == 200, created.text
    grant_id = created.json()["id"]
    assert created.json()["batch_name"] == "Batch A"
    assert created.json()["expires_at"] is not None

    # Branch-wide, permanent grant.
    perm = await client.post(
        "/api/v1/access/accounts-grants",
        json={"user_id": COORD_USER_ID, "batch_id": None, "expires_at": None},
    )
    assert perm.status_code == 200
    assert perm.json()["batch_id"] is None and perm.json()["expires_at"] is None

    listed = await client.get("/api/v1/access/accounts-grants")
    assert len(listed.json()) == 2

    # Revoke the first.
    rev = await client.delete(f"/api/v1/access/accounts-grants/{grant_id}")
    assert rev.status_code == 204
    listed2 = await client.get("/api/v1/access/accounts-grants")
    assert len(listed2.json()) == 1


async def test_accounts_grant_rejects_past_expiry(client, seed_data):
    await _login_admin(client)
    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    resp = await client.post(
        "/api/v1/access/accounts-grants",
        json={"user_id": COORD_USER_ID, "batch_id": None, "expires_at": past},
    )
    assert resp.status_code == 400


async def test_access_endpoints_require_manager(client, seed_data):
    # Not logged in → 401.
    resp = await client.get(
        f"/api/v1/access/coordinators/{COORD_USER_ID}/batches"
    )
    assert resp.status_code == 401


async def test_delivery_log_endpoint(client, seed_data):
    await _login_admin(client)
    resp = await client.get(
        "/api/v1/notifications/delivery-log", params={"branch_id": BRANCH_A_ID}
    )
    assert resp.status_code == 200, resp.text
    assert isinstance(resp.json(), list)
