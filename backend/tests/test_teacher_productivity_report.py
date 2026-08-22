"""Advanced Teacher Productivity report: scheduled-vs-conducted, completion %,
punctuality %, avg late-delay, subject/batch splits, week trend, filters, export.
"""

from datetime import datetime, timedelta, timezone
import uuid

from httpx import AsyncClient

BRANCH_A_ID = "00000000-0000-0000-0000-000000000001"
TEACHER_ID = "00000000-0000-0000-0000-000000000060"
BATCH_ID = "00000000-0000-0000-0000-000000000070"
CLASSROOM_ID = "00000000-0000-0000-0000-000000000080"
SUBJECT_ID = "00000000-0000-0000-0000-000000000050"


async def _login_admin(client: AsyncClient):
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.com", "password": "Admin123!"},
    )
    assert resp.status_code == 200


def _payload(start: datetime, end: datetime):
    return {
        "teacher_id": TEACHER_ID,
        "batch_id": BATCH_ID,
        "classroom_id": CLASSROOM_ID,
        "subject_id": SUBJECT_ID,
        "scheduled_start": start.isoformat(),
        "scheduled_end": end.isoformat(),
        "delivery_mode": "offline",
    }


async def _create(client: AsyncClient, start: datetime) -> dict:
    resp = await client.post(
        "/api/v1/lectures", json=_payload(start, start + timedelta(hours=1))
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


async def _backfill(client: AsyncClient, lecture_id: str, a_start: datetime, minutes: int):
    resp = await client.patch(
        f"/api/v1/lectures/{lecture_id}/actuals",
        params={"branch_id": BRANCH_A_ID},
        json={
            "actual_start": a_start.isoformat(),
            "actual_end": (a_start + timedelta(minutes=minutes)).isoformat(),
        },
    )
    assert resp.status_code == 200, resp.text


async def _seed_three(client: AsyncClient):
    """3 planned lectures: one on-time completed, one late completed, one left
    scheduled (not conducted)."""
    now = datetime.now(timezone.utc)
    s1 = now - timedelta(hours=30)
    s2 = now - timedelta(hours=28)
    s3 = now - timedelta(hours=26)
    l1 = await _create(client, s1)
    l2 = await _create(client, s2)
    await _create(client, s3)  # left scheduled
    await _backfill(client, l1["id"], s1, 60)  # on time
    await _backfill(client, l2["id"], s2 + timedelta(minutes=20), 60)  # 20 min late


async def _report(client: AsyncClient, **params):
    resp = await client.get(
        "/api/v1/lectures/productivity/report",
        params={"branch_id": BRANCH_A_ID, **params},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


async def test_report_scheduled_vs_conducted_and_completion(client, seed_data):
    await _login_admin(client)
    await _seed_three(client)

    body = await _report(client)
    row = next(r for r in body["by_teacher"] if r["teacher_id"] == TEACHER_ID)
    assert row["scheduled"] == 3
    assert row["conducted"] == 2
    assert row["completion_pct"] == 66.7  # 2/3
    assert row["hours"] == 2.0  # two 60-min lectures

    s = body["summary"]
    assert s["total_scheduled"] == 3
    assert s["total_conducted"] == 2
    assert s["completion_pct"] == 66.7


async def test_report_punctuality_and_avg_delay(client, seed_data):
    await _login_admin(client)
    await _seed_three(client)

    row = next(
        r for r in (await _report(client))["by_teacher"] if r["teacher_id"] == TEACHER_ID
    )
    assert row["on_time_count"] == 1
    assert row["late_count"] == 1
    assert row["punctuality_pct"] == 50.0  # 1 of 2 timed on time
    # One lecture 20 minutes late → avg delay 20.
    assert row["avg_delay_min"] == 20.0


async def test_report_subject_and_batch_splits(client, seed_data):
    await _login_admin(client)
    await _seed_three(client)
    body = await _report(client)

    subj = next(s for s in body["by_subject"] if s["subject_id"] == SUBJECT_ID)
    assert subj["scheduled"] == 3 and subj["conducted"] == 2
    batch = next(b for b in body["by_batch"] if b["batch_id"] == BATCH_ID)
    assert batch["scheduled"] == 3 and batch["conducted"] == 2


async def test_report_week_trend(client, seed_data):
    await _login_admin(client)
    await _seed_three(client)
    body = await _report(client)
    assert len(body["trend"]) >= 1
    assert sum(p["scheduled"] for p in body["trend"]) == 3
    assert sum(p["conducted"] for p in body["trend"]) == 2


async def test_report_filters(client, seed_data):
    await _login_admin(client)
    await _seed_three(client)

    # Matching teacher filter keeps the row.
    kept = await _report(client, teacher_ids=[TEACHER_ID])
    assert any(r["teacher_id"] == TEACHER_ID for r in kept["by_teacher"])

    # A teacher who taught nothing → empty report.
    empty = await _report(client, teacher_ids=[str(uuid.uuid4())])
    assert empty["by_teacher"] == []
    assert empty["summary"]["total_scheduled"] == 0

    # A subject nobody scheduled → empty.
    empty_subj = await _report(client, subject_ids=[str(uuid.uuid4())])
    assert empty_subj["by_teacher"] == []


async def test_report_excel_export(client, seed_data):
    await _login_admin(client)
    await _seed_three(client)
    resp = await client.get(
        "/api/v1/lectures/productivity/report/export",
        params={"branch_id": BRANCH_A_ID, "fmt": "xlsx"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith(
        "application/vnd.openxmlformats"
    )
    # A valid .xlsx is a zip — starts with the PK magic bytes.
    assert resp.content[:2] == b"PK"
    assert "attachment" in resp.headers.get("content-disposition", "")
