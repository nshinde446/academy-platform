"""The range recompute is enqueued as a Celery task (a 30-day range is far longer
than the HTTP gateway's ~30s). The endpoint returns 202 + a task_id to poll; it
never runs the recompute inline."""

from httpx import AsyncClient

from app.modules.attendance.jobs import tasks as attendance_tasks

BRANCH_A_ID = "00000000-0000-0000-0000-000000000001"


async def _login_admin(client: AsyncClient):
    r = await client.post("/api/v1/auth/login", json={
        "email": "admin@test.com", "password": "Admin123!",
    })
    assert r.status_code == 200


class _FakeResult:
    id = "fake-task-123"


async def test_recompute_endpoint_enqueues_and_returns_task_id(
    client: AsyncClient, seed_data, monkeypatch
):
    await _login_admin(client)
    calls = {}

    def fake_delay(branch_id, start_iso, end_iso):
        calls["args"] = (branch_id, start_iso, end_iso)
        return _FakeResult()

    # Patch the task's .delay so no broker/worker is needed in the test.
    monkeypatch.setattr(attendance_tasks.recompute_range, "delay", fake_delay)

    r = await client.post(
        "/api/v1/attendance/daily/recompute",
        params={"branch_id": BRANCH_A_ID, "start": "2026-09-08", "end": "2026-10-07"},
    )
    assert r.status_code == 202, r.text
    body = r.json()
    assert body["task_id"] == "fake-task-123"
    assert body["state"] == "PENDING"
    assert body["poll"].endswith("/daily/recompute/fake-task-123")
    # The task is enqueued with the branch + range, not run inline.
    assert calls["args"] == (BRANCH_A_ID, "2026-09-08", "2026-10-07")


async def test_recompute_endpoint_requires_admin(client: AsyncClient, seed_data):
    # No login -> unauthenticated -> rejected (401/403), never enqueued.
    r = await client.post(
        "/api/v1/attendance/daily/recompute",
        params={"branch_id": BRANCH_A_ID, "start": "2026-10-01", "end": "2026-10-01"},
    )
    assert r.status_code in (401, 403)


async def test_recompute_status_reports_celery_state(
    client: AsyncClient, seed_data, monkeypatch
):
    await _login_admin(client)

    class _Res:
        state = "SUCCESS"
        result = {"recomputed": 1183, "branch_id": BRANCH_A_ID,
                  "start": "2026-10-06", "end": "2026-10-06"}

        def __init__(self, task_id, app=None):
            pass

        def successful(self):
            return True

        def failed(self):
            return False

    import celery.result
    monkeypatch.setattr(celery.result, "AsyncResult", _Res)

    r = await client.get("/api/v1/attendance/daily/recompute/fake-task-123")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["state"] == "SUCCESS"
    assert body["result"]["recomputed"] == 1183
