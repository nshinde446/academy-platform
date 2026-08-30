"""Developer monitoring endpoint: email-gated (not role), snapshot shape."""

from httpx import AsyncClient


async def _login_admin(client: AsyncClient):
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.com", "password": "Admin123!"},
    )
    assert resp.status_code == 200


async def test_dev_monitoring_email_gated(client, seed_data, monkeypatch):
    from app.core.config.settings import get_settings

    await _login_admin(client)

    # admin@test.com is a super_admin but NOT in the developer allowlist → 403.
    # (Proves it's gated by email, not role.)
    denied = await client.get("/api/v1/dev/monitoring")
    assert denied.status_code == 403

    # Add the admin's email to the allowlist → now allowed.
    monkeypatch.setattr(get_settings(), "DEVELOPER_EMAILS", "admin@test.com")
    ok = await client.get("/api/v1/dev/monitoring")
    assert ok.status_code == 200, ok.text
    body = ok.json()
    for key in ("system", "devices", "attendance", "backup", "queue", "alerts"):
        assert key in body
    assert isinstance(body["alerts"], list)
    # No backup rows in a fresh test DB → a "no backup" alert is raised.
    assert any(a["area"] == "backup" for a in body["alerts"])
    assert "students" in body["system"]["counts"]


async def test_me_exposes_is_developer(client, seed_data, monkeypatch):
    from app.core.config.settings import get_settings

    await _login_admin(client)
    me = await client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["is_developer"] is False  # not in default allowlist

    monkeypatch.setattr(get_settings(), "DEVELOPER_EMAILS", "admin@test.com")
    me2 = await client.get("/api/v1/auth/me")
    assert me2.json()["is_developer"] is True
