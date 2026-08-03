"""Admin-managed user accounts — create/list/update/delete + self password.

Covers the guardrails that keep an admin from locking themselves (or everyone)
out: no self-deactivate/delete, no removing the last super_admin, email
uniqueness, and role-gated access.
"""

import pytest

BASE = "/api/v1/auth"


async def _cookies(client, email: str, password: str) -> dict:
    resp = await client.post(f"{BASE}/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return {"access_token": resp.cookies["access_token"]}


async def _admin(client) -> dict:
    return await _cookies(client, "admin@test.com", "Admin123!")


@pytest.mark.usefixtures("seed_data")
class TestUserAdmin:
    async def test_create_lists_and_logs_in(self, client, seed_data):
        c = await _admin(client)
        resp = await client.post(
            f"{BASE}/users",
            cookies=c,
            json={
                "email": "New.Teacher@test.com", "first_name": "New",
                "last_name": "Teacher", "role": "teacher", "password": "Temp1234!",
            },
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["email"] == "new.teacher@test.com"  # normalised lower-case
        assert body["roles"] == ["teacher"]
        assert body["status"] == "active"

        listed = await client.get(f"{BASE}/users", cookies=c)
        assert any(u["email"] == "new.teacher@test.com" for u in listed.json())

        # The new user can sign in with the temp password.
        login = await client.post(
            f"{BASE}/login",
            json={"email": "new.teacher@test.com", "password": "Temp1234!"},
        )
        assert login.status_code == 200

    async def test_duplicate_email_conflicts(self, client, seed_data):
        c = await _admin(client)
        resp = await client.post(
            f"{BASE}/users", cookies=c,
            json={"email": "admin@test.com", "first_name": "Dup", "last_name": "X",
                  "role": "teacher", "password": "Temp1234!"},
        )
        assert resp.status_code == 409

    async def test_unknown_role_rejected(self, client, seed_data):
        c = await _admin(client)
        resp = await client.post(
            f"{BASE}/users", cookies=c,
            json={"email": "x@test.com", "first_name": "X", "last_name": "Y",
                  "role": "wizard", "password": "Temp1234!"},
        )
        assert resp.status_code == 400

    async def test_non_admin_cannot_manage_users(self, client, seed_data):
        c = await _cookies(client, "teacher@test.com", "Teacher123!")
        assert (await client.get(f"{BASE}/users", cookies=c)).status_code == 403
        assert (await client.post(
            f"{BASE}/users", cookies=c,
            json={"email": "z@test.com", "first_name": "Z", "last_name": "Z",
                  "role": "teacher", "password": "Temp1234!"},
        )).status_code == 403

    async def test_deactivate_then_login_blocked(self, client, seed_data):
        c = await _admin(client)
        created = (await client.post(
            f"{BASE}/users", cookies=c,
            json={"email": "temp@test.com", "first_name": "T", "last_name": "T",
                  "role": "teacher", "password": "Temp1234!"},
        )).json()
        patch = await client.patch(
            f"{BASE}/users/{created['id']}", cookies=c, json={"status": "inactive"},
        )
        assert patch.status_code == 200
        assert patch.json()["status"] == "inactive"
        # An inactive account is refused at login (403).
        login = await client.post(
            f"{BASE}/login", json={"email": "temp@test.com", "password": "Temp1234!"},
        )
        assert login.status_code == 403

    async def test_cannot_deactivate_self(self, client, seed_data):
        c = await _admin(client)
        admin_id = "00000000-0000-0000-0000-000000000100"
        resp = await client.patch(
            f"{BASE}/users/{admin_id}", cookies=c, json={"status": "inactive"},
        )
        assert resp.status_code == 403

    async def test_cannot_delete_last_super_admin(self, client, seed_data):
        c = await _admin(client)
        admin_id = "00000000-0000-0000-0000-000000000100"
        # Also blocked by the self-delete guard, but the intent is lock-out safety.
        resp = await client.delete(f"{BASE}/users/{admin_id}", cookies=c)
        assert resp.status_code in (403, 409)

    async def test_reset_password_and_relogin(self, client, seed_data):
        c = await _admin(client)
        created = (await client.post(
            f"{BASE}/users", cookies=c,
            json={"email": "reset@test.com", "first_name": "R", "last_name": "R",
                  "role": "teacher", "password": "Temp1234!"},
        )).json()
        resp = await client.post(
            f"{BASE}/users/{created['id']}/reset-password", cookies=c,
            json={"password": "Brand5678!"},
        )
        assert resp.status_code == 200
        assert (await client.post(
            f"{BASE}/login", json={"email": "reset@test.com", "password": "Brand5678!"},
        )).status_code == 200

    async def test_change_own_password(self, client, seed_data):
        c = await _admin(client)
        ok = await client.post(
            f"{BASE}/change-password", cookies=c,
            json={"current_password": "Admin123!", "new_password": "Admin9999!"},
        )
        assert ok.status_code == 200
        assert (await client.post(
            f"{BASE}/login", json={"email": "admin@test.com", "password": "Admin9999!"},
        )).status_code == 200

    async def test_change_own_password_wrong_current(self, client, seed_data):
        c = await _admin(client)
        resp = await client.post(
            f"{BASE}/change-password", cookies=c,
            json={"current_password": "nope", "new_password": "Admin9999!"},
        )
        assert resp.status_code == 400

    async def test_roles_list_available(self, client, seed_data):
        c = await _admin(client)
        resp = await client.get(f"{BASE}/roles", cookies=c)
        assert resp.status_code == 200
        names = {r["name"] for r in resp.json()}
        assert {"super_admin", "teacher"} <= names
