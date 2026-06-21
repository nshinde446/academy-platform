import json
import uuid
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.plugins.models.plugin_models import Plugin, PluginDependency, PluginEvent
from app.modules.plugins.services import plugin_service

BRANCH_A_ID = "00000000-0000-0000-0000-000000000001"
BRANCH_B_ID = "00000000-0000-0000-0000-000000000002"


async def _login_admin(client: AsyncClient):
    resp = await client.post("/api/v1/auth/login", json={
        "email": "admin@test.com",
        "password": "Admin123!",
    })
    assert resp.status_code == 200


async def _login_teacher(client: AsyncClient):
    resp = await client.post("/api/v1/auth/login", json={
        "email": "teacher@test.com",
        "password": "Teacher123!",
    })
    assert resp.status_code == 200


def _plugin_payload(**overrides):
    base = {
        "name": "test_plugin",
        "version": "1.0.0",
        "description": "A test plugin",
        "entry_point": "plugins.test_plugin.main:TestPlugin",
        "branch_id": BRANCH_A_ID,
    }
    base.update(overrides)
    return base


async def _create_plugin(client: AsyncClient, **overrides):
    resp = await client.post("/api/v1/plugins", json=_plugin_payload(**overrides))
    assert resp.status_code == 201
    return resp.json()


# ─── Test 1: Register plugin ──────────────────────────────────────────────

async def test_register_plugin(client: AsyncClient, seed_data):
    await _login_admin(client)
    resp = await client.post("/api/v1/plugins", json=_plugin_payload())
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "test_plugin"
    assert data["version"] == "1.0.0"
    assert data["is_enabled"] is False
    assert data["branch_id"] == BRANCH_A_ID


# ─── Test 2: Duplicate plugin name rejected ────────────────────────────────

async def test_duplicate_plugin_rejected(client: AsyncClient, seed_data):
    await _login_admin(client)
    await _create_plugin(client)
    resp = await client.post("/api/v1/plugins", json=_plugin_payload())
    assert resp.status_code == 409


# ─── Test 3: List plugins ─────────────────────────────────────────────────

async def test_list_plugins(client: AsyncClient, seed_data):
    await _login_admin(client)
    await _create_plugin(client, name="plugin_a")
    await _create_plugin(client, name="plugin_b")
    resp = await client.get("/api/v1/plugins")
    assert resp.status_code == 200
    assert len(resp.json()) >= 2


# ─── Test 4: Get plugin by ID ─────────────────────────────────────────────

async def test_get_plugin_by_id(client: AsyncClient, seed_data):
    await _login_admin(client)
    created = await _create_plugin(client)
    resp = await client.get(f"/api/v1/plugins/{created['id']}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "test_plugin"


# ─── Test 5: Enable plugin ────────────────────────────────────────────────

async def test_enable_plugin(client: AsyncClient, seed_data):
    await _login_admin(client)
    created = await _create_plugin(client)
    resp = await client.patch(f"/api/v1/plugins/{created['id']}/enable")
    assert resp.status_code == 200
    assert resp.json()["is_enabled"] is True


# ─── Test 6: Disable plugin ───────────────────────────────────────────────

async def test_disable_plugin(client: AsyncClient, seed_data):
    await _login_admin(client)
    created = await _create_plugin(client)
    await client.patch(f"/api/v1/plugins/{created['id']}/enable")
    resp = await client.patch(f"/api/v1/plugins/{created['id']}/disable")
    assert resp.status_code == 200
    assert resp.json()["is_enabled"] is False


# ─── Test 7: Soft delete plugin ───────────────────────────────────────────

async def test_soft_delete_plugin(client: AsyncClient, seed_data):
    await _login_admin(client)
    created = await _create_plugin(client)
    resp = await client.delete(f"/api/v1/plugins/{created['id']}")
    assert resp.status_code == 204

    resp = await client.get(f"/api/v1/plugins/{created['id']}")
    assert resp.status_code == 404


# ─── Test 8: Set config ───────────────────────────────────────────────────

async def test_set_config(client: AsyncClient, seed_data):
    await _login_admin(client)
    created = await _create_plugin(client)
    resp = await client.post(
        f"/api/v1/plugins/{created['id']}/config",
        json={"key": "api_key", "value": "sk-123456", "is_secret": False},
    )
    assert resp.status_code == 201
    assert resp.json()["key"] == "api_key"
    assert resp.json()["value"] == "sk-123456"


# ─── Test 9: Secret config is masked in listing ───────────────────────────

async def test_secret_config_masked(client: AsyncClient, seed_data):
    await _login_admin(client)
    created = await _create_plugin(client)
    await client.post(
        f"/api/v1/plugins/{created['id']}/config",
        json={"key": "secret_key", "value": "super-secret-value", "is_secret": True},
    )
    resp = await client.get(f"/api/v1/plugins/{created['id']}/config")
    assert resp.status_code == 200
    configs = resp.json()
    secret = next(c for c in configs if c["key"] == "secret_key")
    assert secret["value"] == "***"
    assert secret["is_secret"] is True


# ─── Test 10: Event subscription ──────────────────────────────────────────

async def test_subscribe_to_event(client: AsyncClient, seed_data):
    await _login_admin(client)
    created = await _create_plugin(client)
    resp = await client.post(
        f"/api/v1/plugins/{created['id']}/events",
        json={"event_type": "LECTURE_STARTED", "handler": "plugins.test:handle_lecture"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["event_type"] == "LECTURE_STARTED"
    assert data["handler"] == "plugins.test:handle_lecture"


# ─── Test 11: Plugin receives events when subscribed ──────────────────────

async def test_trigger_plugin_event(client: AsyncClient, seed_data, db_session: AsyncSession):
    await _login_admin(client)
    created = await _create_plugin(client)
    await client.patch(f"/api/v1/plugins/{created['id']}/enable")
    await client.post(
        f"/api/v1/plugins/{created['id']}/events",
        json={"event_type": "LECTURE_STARTED", "handler": "plugins.test:handle"},
    )

    results = await plugin_service.trigger_plugin_event(
        db_session,
        event_type="LECTURE_STARTED",
        event_data={"lecture_id": "abc"},
        branch_id=uuid.UUID(BRANCH_A_ID),
    )
    assert len(results) == 1
    assert results[0]["plugin"] == "test_plugin"
    assert results[0]["status"] in ("HANDLER_NOT_FOUND", "ERROR")


# ─── Test 12: Dependency validation – missing dep blocks enable ────────────

async def test_dependency_validation_blocks_enable(
    client: AsyncClient, seed_data, db_session: AsyncSession
):
    await _login_admin(client)
    created = await _create_plugin(client, name="dependent_plugin")

    # A real but *disabled* plugin: validate_dependencies treats a missing OR
    # not-enabled dependency as unsatisfied. (Pointing at a nonexistent id would
    # violate the depends_on_plugin_id FK, which the test DB now enforces.)
    disabled_dep = await _create_plugin(client, name="disabled_dep_plugin")
    dep = PluginDependency(
        plugin_id=uuid.UUID(created["id"]),
        depends_on_plugin_id=uuid.UUID(disabled_dep["id"]),
        min_version="1.0.0",
    )
    db_session.add(dep)
    await db_session.flush()
    await db_session.commit()

    resp = await client.patch(f"/api/v1/plugins/{created['id']}/enable")
    assert resp.status_code == 400
    assert "Unsatisfied dependencies" in resp.json()["error"]["message"]


# ─── Test 13: Dependency validation – satisfied dep allows enable ──────────

async def test_dependency_satisfied_allows_enable(
    client: AsyncClient, seed_data, db_session: AsyncSession
):
    await _login_admin(client)
    base_plugin = await _create_plugin(client, name="base_plugin")
    await client.patch(f"/api/v1/plugins/{base_plugin['id']}/enable")

    child_plugin = await _create_plugin(client, name="child_plugin", entry_point="plugins.child:Child")

    dep = PluginDependency(
        plugin_id=uuid.UUID(child_plugin["id"]),
        depends_on_plugin_id=uuid.UUID(base_plugin["id"]),
    )
    db_session.add(dep)
    await db_session.flush()
    await db_session.commit()

    resp = await client.patch(f"/api/v1/plugins/{child_plugin['id']}/enable")
    assert resp.status_code == 200
    assert resp.json()["is_enabled"] is True


# ─── Test 14: Branch isolation – plugin for branch A not in branch B ───────

async def test_branch_isolation(client: AsyncClient, seed_data):
    await _login_admin(client)
    await _create_plugin(client, name="branch_a_plugin", branch_id=BRANCH_A_ID)
    await _create_plugin(client, name="global_plugin", branch_id=None)

    resp = await client.get(f"/api/v1/plugins?branch_id={BRANCH_B_ID}")
    assert resp.status_code == 200
    names = [p["name"] for p in resp.json()]
    assert "branch_a_plugin" not in names
    assert "global_plugin" in names


# ─── Test 15: RBAC – teacher cannot register plugin ────────────────────────

async def test_teacher_cannot_register_plugin(client: AsyncClient, seed_data):
    await _login_teacher(client)
    resp = await client.post("/api/v1/plugins", json=_plugin_payload())
    assert resp.status_code == 403


# ─── Test 16: RBAC – teacher cannot enable plugin ─────────────────────────

async def test_teacher_cannot_enable_plugin(client: AsyncClient, seed_data):
    await _login_admin(client)
    created = await _create_plugin(client)

    await _login_teacher(client)
    resp = await client.patch(f"/api/v1/plugins/{created['id']}/enable")
    assert resp.status_code == 403


# ─── Test 17: Audit log for plugin registration ───────────────────────────

async def test_audit_log_on_register(client: AsyncClient, seed_data):
    await _login_admin(client)
    await _create_plugin(client)

    resp = await client.get("/api/v1/audit/logs", params={"table_name": "plugins"})
    assert resp.status_code == 200
    logs = resp.json()["items"]
    create_logs = [l for l in logs if l["action"] == "CREATE" and l["table_name"] == "plugins"]
    assert len(create_logs) >= 1


# ─── Test 18: Audit log for enable/disable ─────────────────────────────────

async def test_audit_log_on_enable_disable(client: AsyncClient, seed_data):
    await _login_admin(client)
    created = await _create_plugin(client)
    await client.patch(f"/api/v1/plugins/{created['id']}/enable")
    await client.patch(f"/api/v1/plugins/{created['id']}/disable")

    resp = await client.get("/api/v1/audit/logs", params={"table_name": "plugins"})
    assert resp.status_code == 200
    logs = resp.json()["items"]
    update_logs = [l for l in logs if l["action"] == "UPDATE" and l["table_name"] == "plugins"]
    assert len(update_logs) >= 2


# ─── Test 19: Config update overwrites existing key ────────────────────────

async def test_config_update_overwrites(client: AsyncClient, seed_data):
    await _login_admin(client)
    created = await _create_plugin(client)
    await client.post(
        f"/api/v1/plugins/{created['id']}/config",
        json={"key": "endpoint", "value": "http://old.com", "is_secret": False},
    )
    await client.post(
        f"/api/v1/plugins/{created['id']}/config",
        json={"key": "endpoint", "value": "http://new.com", "is_secret": False},
    )

    resp = await client.get(f"/api/v1/plugins/{created['id']}/config")
    configs = resp.json()
    endpoint_configs = [c for c in configs if c["key"] == "endpoint"]
    assert len(endpoint_configs) == 1
    assert endpoint_configs[0]["value"] == "http://new.com"


# ─── Test 20: Plugin loading with mock ─────────────────────────────────────

async def test_plugin_load_unload_mock(client: AsyncClient, seed_data):
    await _login_admin(client)

    with patch("app.modules.plugins.services.plugin_service.load_plugin") as mock_load:
        mock_load.return_value = None
        created = await _create_plugin(client)
        resp = await client.patch(f"/api/v1/plugins/{created['id']}/enable")
        assert resp.status_code == 200
        mock_load.assert_called_once()

    with patch("app.modules.plugins.services.plugin_service.unload_plugin") as mock_unload:
        mock_unload.return_value = None
        resp = await client.patch(f"/api/v1/plugins/{created['id']}/disable")
        assert resp.status_code == 200
        mock_unload.assert_called_once()
