"""Teacher bulk soft-delete — the roster's bulk-select clean-up path."""

from httpx import AsyncClient

BRANCH_A_ID = "00000000-0000-0000-0000-000000000001"


async def _login_admin(client: AsyncClient):
    resp = await client.post("/api/v1/auth/login", json={
        "email": "admin@test.com",
        "password": "Admin123!",
    })
    assert resp.status_code == 200


async def _create_teacher(client: AsyncClient, first: str) -> str:
    resp = await client.post(
        "/api/v1/teachers",
        json={"branch_id": BRANCH_A_ID, "first_name": first, "last_name": "Temp"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


async def test_bulk_delete_removes_selected_teachers(client: AsyncClient, seed_data):
    await _login_admin(client)
    a = await _create_teacher(client, "BulkA")
    b = await _create_teacher(client, "BulkB")
    c = await _create_teacher(client, "BulkC")

    # Delete A + B, keep C.
    resp = await client.post(
        "/api/v1/teachers/bulk-delete",
        params={"branch_id": BRANCH_A_ID},
        json={"teacher_ids": [a, b]},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["deleted"] == 2

    # A + B gone from the roster, C remains.
    resp = await client.get("/api/v1/teachers", params={"branch_id": BRANCH_A_ID})
    ids = [t["id"] for t in resp.json()]
    assert a not in ids
    assert b not in ids
    assert c in ids


async def test_bulk_delete_empty_list_is_noop(client: AsyncClient, seed_data):
    await _login_admin(client)
    resp = await client.post(
        "/api/v1/teachers/bulk-delete",
        params={"branch_id": BRANCH_A_ID},
        json={"teacher_ids": []},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["deleted"] == 0


async def test_bulk_delete_ignores_other_branch_ids(client: AsyncClient, seed_data):
    """Only live teachers in the caller's branch are affected — a bogus id
    contributes nothing to the count."""
    await _login_admin(client)
    a = await _create_teacher(client, "BranchScoped")
    bogus = "00000000-0000-0000-0000-0000000009ff"

    resp = await client.post(
        "/api/v1/teachers/bulk-delete",
        params={"branch_id": BRANCH_A_ID},
        json={"teacher_ids": [a, bogus]},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["deleted"] == 1
