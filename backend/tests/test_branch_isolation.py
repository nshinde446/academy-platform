import pytest


class TestBranchIsolation:
    @pytest.mark.usefixtures("seed_data")
    async def test_super_admin_accesses_any_branch(self, client, seed_data):
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "admin@test.com", "password": "Admin123!"},
        )
        access_token = login_resp.cookies["access_token"]

        branch_b_id = "00000000-0000-0000-0000-000000000002"
        response = await client.get(
            f"/api/v1/auth/branch-test/{branch_b_id}",
            cookies={"access_token": access_token},
        )
        assert response.status_code == 200

    @pytest.mark.usefixtures("seed_data")
    async def test_teacher_accesses_own_branch(self, client, seed_data):
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "teacher@test.com", "password": "Teacher123!"},
        )
        access_token = login_resp.cookies["access_token"]

        branch_a_id = "00000000-0000-0000-0000-000000000001"
        response = await client.get(
            f"/api/v1/auth/branch-test/{branch_a_id}",
            cookies={"access_token": access_token},
        )
        assert response.status_code == 200

    @pytest.mark.usefixtures("seed_data")
    async def test_teacher_blocked_from_other_branch(self, client, seed_data):
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "teacher@test.com", "password": "Teacher123!"},
        )
        access_token = login_resp.cookies["access_token"]

        branch_b_id = "00000000-0000-0000-0000-000000000002"
        response = await client.get(
            f"/api/v1/auth/branch-test/{branch_b_id}",
            cookies={"access_token": access_token},
        )
        assert response.status_code == 403

    async def test_unauthenticated_branch_access(self, client):
        response = await client.get(
            "/api/v1/auth/branch-test/00000000-0000-0000-0000-000000000001"
        )
        assert response.status_code == 401
