from httpx import AsyncClient


async def test_health_returns_200(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["version"] == "0.1.0"


async def test_health_includes_request_id_header(client: AsyncClient):
    response = await client.get("/health")
    assert "x-request-id" in response.headers


async def test_auth_me_rejects_unauthenticated(client: AsyncClient):
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401


async def test_auth_me_rejects_invalid_cookie(client: AsyncClient):
    response = await client.get(
        "/api/v1/auth/me",
        cookies={"access_token": "fake-token"},
    )
    assert response.status_code == 401
