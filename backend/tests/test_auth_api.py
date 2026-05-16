import pytest


class TestLogin:
    @pytest.mark.usefixtures("seed_data")
    async def test_login_success(self, client, seed_data):
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "admin@test.com", "password": "Admin123!"},
        )
        assert response.status_code == 200
        assert response.json()["message"] == "Login successful"
        assert "access_token" in response.cookies
        assert "refresh_token" in response.cookies

    @pytest.mark.usefixtures("seed_data")
    async def test_login_wrong_password(self, client, seed_data):
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "admin@test.com", "password": "wrong"},
        )
        assert response.status_code == 401

    @pytest.mark.usefixtures("seed_data")
    async def test_login_nonexistent_user(self, client, seed_data):
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@test.com", "password": "pass"},
        )
        assert response.status_code == 401

    @pytest.mark.usefixtures("seed_data")
    async def test_login_inactive_user(self, client, seed_data):
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "inactive@test.com", "password": "Inactive123!"},
        )
        assert response.status_code == 403


class TestMe:
    @pytest.mark.usefixtures("seed_data")
    async def test_me_authenticated(self, client, seed_data):
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "admin@test.com", "password": "Admin123!"},
        )
        access_token = login_resp.cookies["access_token"]

        response = await client.get(
            "/api/v1/auth/me",
            cookies={"access_token": access_token},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "admin@test.com"
        assert "super_admin" in data["roles"]

    async def test_me_unauthenticated(self, client):
        response = await client.get("/api/v1/auth/me")
        assert response.status_code == 401


class TestLogout:
    @pytest.mark.usefixtures("seed_data")
    async def test_logout(self, client, seed_data):
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "admin@test.com", "password": "Admin123!"},
        )
        access_token = login_resp.cookies["access_token"]
        refresh_token = login_resp.cookies["refresh_token"]

        response = await client.post(
            "/api/v1/auth/logout",
            cookies={
                "access_token": access_token,
                "refresh_token": refresh_token,
            },
        )
        assert response.status_code == 200
        assert response.json()["message"] == "Logged out successfully"


class TestRefresh:
    @pytest.mark.usefixtures("seed_data")
    async def test_refresh_success(self, client, seed_data):
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "admin@test.com", "password": "Admin123!"},
        )
        refresh_token = login_resp.cookies["refresh_token"]

        response = await client.post(
            "/api/v1/auth/refresh",
            cookies={"refresh_token": refresh_token},
        )
        assert response.status_code == 200
        assert "access_token" in response.cookies

    async def test_refresh_no_token(self, client):
        response = await client.post("/api/v1/auth/refresh")
        assert response.status_code == 401

    @pytest.mark.usefixtures("seed_data")
    async def test_refresh_reuse_revoked(self, client, seed_data):
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "admin@test.com", "password": "Admin123!"},
        )
        refresh_token = login_resp.cookies["refresh_token"]

        await client.post(
            "/api/v1/auth/refresh",
            cookies={"refresh_token": refresh_token},
        )

        response = await client.post(
            "/api/v1/auth/refresh",
            cookies={"refresh_token": refresh_token},
        )
        assert response.status_code == 401
