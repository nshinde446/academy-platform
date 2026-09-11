"""Staff module — department seeding, per-department ID allocation, legacy
codes, CRUD, and teacher linkage."""

from httpx import AsyncClient

BRANCH_A_ID = "00000000-0000-0000-0000-000000000001"
TEACHER_ID = "00000000-0000-0000-0000-000000000060"


async def _login_admin(client: AsyncClient) -> None:
    resp = await client.post("/api/v1/auth/login", json={
        "email": "admin@test.com",
        "password": "Admin123!",
    })
    assert resp.status_code == 200


async def _departments(client: AsyncClient) -> dict[str, dict]:
    resp = await client.get("/api/v1/staff/departments", params={"branch_id": BRANCH_A_ID})
    assert resp.status_code == 200, resp.text
    return {d["name"]: d for d in resp.json()}


async def test_departments_seeded_with_ranges(client: AsyncClient, seed_data):
    await _login_admin(client)
    depts = await _departments(client)
    assert set(depts) == {
        "MSA-Teachers", "MSA-Administration", "MSA-Accounts",
        "Security", "Cleaning Unit", "MSA-Marketing",
    }
    assert (depts["MSA-Teachers"]["id_range_start"], depts["MSA-Teachers"]["id_range_end"]) == (1, 50)
    assert (depts["MSA-Marketing"]["id_range_start"], depts["MSA-Marketing"]["id_range_end"]) == (101, 110)
    # Empty department -> next code is the range start.
    assert depts["Security"]["next_emp_code"] == "81"
    assert depts["Security"]["used"] == 0


async def test_emp_code_allocates_in_range_and_rolls_forward(client: AsyncClient, seed_data):
    await _login_admin(client)
    depts = await _departments(client)
    sec = depts["Security"]["id"]

    r1 = await client.post("/api/v1/staff", json={
        "branch_id": BRANCH_A_ID, "first_name": "Guard", "last_name": "One",
        "department_id": sec,
    })
    assert r1.status_code == 200, r1.text
    assert r1.json()["emp_code"] == "81"
    assert r1.json()["is_legacy_code"] is False

    r2 = await client.post("/api/v1/staff", json={
        "branch_id": BRANCH_A_ID, "first_name": "Guard", "last_name": "Two",
        "department_id": sec,
    })
    assert r2.json()["emp_code"] == "82"

    # Preview reflects the two used slots.
    depts = await _departments(client)
    assert depts["Security"]["used"] == 2
    assert depts["Security"]["next_emp_code"] == "83"


async def test_legacy_out_of_range_code_flagged_and_does_not_block_allocation(
    client: AsyncClient, seed_data
):
    await _login_admin(client)
    depts = await _departments(client)
    accounts = depts["MSA-Accounts"]["id"]  # range 71-80

    # Import-style legacy code (2, outside 71-80).
    legacy = await client.post("/api/v1/staff", json={
        "branch_id": BRANCH_A_ID, "first_name": "Ram", "last_name": "Wable",
        "department_id": accounts, "emp_code": "2",
    })
    assert legacy.status_code == 200, legacy.text
    assert legacy.json()["is_legacy_code"] is True

    # A subsequent auto-allocation still starts at the range floor.
    auto = await client.post("/api/v1/staff", json={
        "branch_id": BRANCH_A_ID, "first_name": "New", "last_name": "Joiner",
        "department_id": accounts,
    })
    assert auto.json()["emp_code"] == "71"
    assert auto.json()["is_legacy_code"] is False


async def test_duplicate_emp_code_rejected(client: AsyncClient, seed_data):
    await _login_admin(client)
    depts = await _departments(client)
    admin = depts["MSA-Administration"]["id"]

    first = await client.post("/api/v1/staff", json={
        "branch_id": BRANCH_A_ID, "first_name": "A", "department_id": admin,
        "emp_code": "55",
    })
    assert first.status_code == 200
    dup = await client.post("/api/v1/staff", json={
        "branch_id": BRANCH_A_ID, "first_name": "B", "department_id": admin,
        "emp_code": "55",
    })
    assert dup.status_code == 409, dup.text


async def test_link_teacher_and_list_and_delete(client: AsyncClient, seed_data):
    await _login_admin(client)
    depts = await _departments(client)
    teachers_dept = depts["MSA-Teachers"]["id"]

    created = await client.post("/api/v1/staff", json={
        "branch_id": BRANCH_A_ID, "first_name": "Teach", "last_name": "Er",
        "department_id": teachers_dept,
    })
    sid = created.json()["id"]

    linked = await client.post(
        f"/api/v1/staff/{sid}/link-teacher",
        params={"branch_id": BRANCH_A_ID},
        json={"teacher_id": TEACHER_ID},
    )
    assert linked.status_code == 200, linked.text
    assert linked.json()["linked_teacher_id"] == TEACHER_ID

    listed = await client.get("/api/v1/staff", params={"branch_id": BRANCH_A_ID})
    assert sid in [s["id"] for s in listed.json()]

    gone = await client.delete(f"/api/v1/staff/{sid}", params={"branch_id": BRANCH_A_ID})
    assert gone.status_code == 204
    listed = await client.get("/api/v1/staff", params={"branch_id": BRANCH_A_ID})
    assert sid not in [s["id"] for s in listed.json()]
