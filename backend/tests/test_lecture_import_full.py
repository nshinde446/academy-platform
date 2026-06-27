"""Full scenario matrix for the schedule importer — POST /lectures/import.

Covers the happy path, every per-row failure mode (resolution, parsing,
validation, the Subject→Teacher lock, conflicts), partial-accept, online vs
offline, header normalization, and .xlsx parsing.
"""

import io
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models.auth_models import User
from app.modules.auth.services.auth_service import hash_password
from app.modules.batch.models.batch_models import BatchSubjectMapping
from app.modules.teacher.models.teacher_models import Teacher

BRANCH_A_ID = "00000000-0000-0000-0000-000000000001"
BATCH_A_ID = "00000000-0000-0000-0000-000000000070"
SUBJECT_ID = "00000000-0000-0000-0000-000000000050"

HEADER = (
    "date,start_time,end_time,teacher_email,batch_code,"
    "subject_code,classroom_code,delivery_mode,notes\n"
)
# Valid building block: teacher@test.com → Teacher 060 (teaches PHY), batch
# BATCH-A, subject PHY, classroom R101.
TEACHER_EMAIL = "teacher@test.com"


async def _login_admin(client: AsyncClient):
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.com", "password": "Admin123!"},
    )
    assert resp.status_code == 200


async def _map_subject(session: AsyncSession):
    """PHY must be mapped to BATCH-A for the importer to resolve it."""
    session.add(
        BatchSubjectMapping(
            batch_id=uuid.UUID(BATCH_A_ID),
            subject_id=uuid.UUID(SUBJECT_ID),
            branch_id=uuid.UUID(BRANCH_A_ID),
            status="active",
        )
    )
    await session.commit()


async def _import_csv(client: AsyncClient, text: str):
    return await client.post(
        "/api/v1/lectures/import",
        params={"branch_id": BRANCH_A_ID},
        files={"file": ("schedule.csv", text.encode("utf-8"), "text/csv")},
    )


async def _list(client: AsyncClient) -> list[dict]:
    return (
        await client.get("/api/v1/lectures", params={"branch_id": BRANCH_A_ID})
    ).json()


# ── Happy path ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_valid_row_imports(client: AsyncClient, db_session, seed_data):
    await _login_admin(client)
    await _map_subject(db_session)
    csv = HEADER + "2026-06-01,09:00,10:00,teacher@test.com,BATCH-A,PHY,R101,offline,Intro\n"
    resp = await _import_csv(client, csv)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["imported"] == 1 and body["skipped"] == 0
    assert len(await _list(client)) == 1


@pytest.mark.asyncio
async def test_missing_required_columns(client: AsyncClient, seed_data):
    await _login_admin(client)
    resp = await _import_csv(client, "date,start_time\n2026-06-01,09:00\n")
    assert resp.status_code == 400
    assert "Missing required columns" in resp.json()["error"]["message"]


# ── Partial accept: 1 good row + every failure mode in one file ────────────

@pytest.mark.asyncio
async def test_partial_accept_reports_each_failure(
    client: AsyncClient, db_session, seed_data
):
    await _login_admin(client)
    await _map_subject(db_session)
    rows = [
        # valid
        "2026-06-01,09:00,10:00,teacher@test.com,BATCH-A,PHY,R101,offline,ok",
        # unknown teacher
        "2026-06-02,09:00,10:00,nobody@x.com,BATCH-A,PHY,R101,offline,",
        # unknown batch
        "2026-06-03,09:00,10:00,teacher@test.com,NOPE,PHY,R101,offline,",
        # subject not mapped to batch
        "2026-06-04,09:00,10:00,teacher@test.com,BATCH-A,CHEM,R101,offline,",
        # unknown classroom
        "2026-06-05,09:00,10:00,teacher@test.com,BATCH-A,PHY,ZZZ,offline,",
        # bad date
        "2026-13-99,09:00,10:00,teacher@test.com,BATCH-A,PHY,R101,offline,",
        # bad time
        "2026-06-07,99:99,10:00,teacher@test.com,BATCH-A,PHY,R101,offline,",
        # end <= start
        "2026-06-08,10:00,09:00,teacher@test.com,BATCH-A,PHY,R101,offline,",
        # offline but no classroom
        "2026-06-09,09:00,10:00,teacher@test.com,BATCH-A,PHY,,offline,",
    ]
    resp = await _import_csv(client, HEADER + "\n".join(rows) + "\n")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["imported"] == 1
    assert body["skipped"] == 8
    blob = " | ".join(body["errors"]).lower()
    for needle in [
        "no teacher",
        "unknown batch_code",
        "isn't mapped",
        "unknown classroom_code",
        "bad date",
        "bad time",
        "after start_time",
        "offline lectures require",
    ]:
        assert needle in blob, f"missing error: {needle}\n{blob}"
    # Only the one valid row was actually created.
    assert len(await _list(client)) == 1


# ── Delivery mode ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_online_without_classroom_ok(
    client: AsyncClient, db_session, seed_data
):
    await _login_admin(client)
    await _map_subject(db_session)
    csv = HEADER + "2026-06-01,09:00,10:00,teacher@test.com,BATCH-A,PHY,,online,\n"
    body = (await _import_csv(client, csv)).json()
    assert body["imported"] == 1 and body["skipped"] == 0


# ── Conflict ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_overlapping_rows_conflict(
    client: AsyncClient, db_session, seed_data
):
    await _login_admin(client)
    await _map_subject(db_session)
    rows = [
        "2026-06-01,09:00,10:00,teacher@test.com,BATCH-A,PHY,R101,offline,a",
        "2026-06-01,09:30,10:30,teacher@test.com,BATCH-A,PHY,R101,offline,b",
    ]
    body = (await _import_csv(client, HEADER + "\n".join(rows) + "\n")).json()
    assert body["imported"] == 1
    assert body["skipped"] == 1
    assert any("conflict" in e.lower() for e in body["errors"])


# ── Subject→Teacher lock ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_unqualified_teacher_blocked(
    client: AsyncClient, db_session: AsyncSession, seed_data
):
    await _login_admin(client)
    await _map_subject(db_session)
    # A real teacher who does NOT teach PHY.
    user = User(
        id=uuid.uuid4(),
        email="other@test.com",
        password_hash=hash_password("x"),
        first_name="Other",
        last_name="Teach",
        status="active",
        is_deleted=False,
    )
    db_session.add(user)
    await db_session.flush()
    db_session.add(
        Teacher(
            id=uuid.uuid4(),
            user_id=user.id,
            branch_id=uuid.UUID(BRANCH_A_ID),
            first_name="Other",
            last_name="Teach",
            status="active",
            is_deleted=False,
        )
    )
    await db_session.commit()

    csv = HEADER + "2026-06-01,09:00,10:00,other@test.com,BATCH-A,PHY,R101,offline,\n"
    body = (await _import_csv(client, csv)).json()
    assert body["imported"] == 0
    assert body["skipped"] == 1
    assert any("not assigned to this subject" in e for e in body["errors"])


# ── Header normalization ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_header_case_and_spaces_normalized(
    client: AsyncClient, db_session, seed_data
):
    await _login_admin(client)
    await _map_subject(db_session)
    header = (
        "DATE, Start Time ,End Time,Teacher Email,Batch Code,"
        "Subject Code,Classroom Code,Delivery Mode,Notes\n"
    )
    csv = header + "2026-06-01,09:00,10:00,teacher@test.com,BATCH-A,PHY,R101,offline,ok\n"
    body = (await _import_csv(client, csv)).json()
    assert body["imported"] == 1, body


# ── Holiday awareness ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_holiday_row_is_skipped(client: AsyncClient, db_session, seed_data):
    await _login_admin(client)
    await _map_subject(db_session)
    await client.post(
        "/api/v1/lectures/holidays",
        params={"branch_id": BRANCH_A_ID},
        json={"holiday_date": "2026-06-01", "name": "Founder's Day"},
    )
    csv = HEADER + "2026-06-01,09:00,10:00,teacher@test.com,BATCH-A,PHY,R101,offline,\n"
    body = (await _import_csv(client, csv)).json()
    assert body["imported"] == 0
    assert body["skipped"] == 1
    assert any("holiday" in e.lower() for e in body["errors"])
    assert len(await _list(client)) == 0


@pytest.mark.asyncio
async def test_preview_flags_holiday_row(client: AsyncClient, db_session, seed_data):
    await _login_admin(client)
    await _map_subject(db_session)
    await client.post(
        "/api/v1/lectures/holidays",
        params={"branch_id": BRANCH_A_ID},
        json={"holiday_date": "2026-06-01", "name": "Founder's Day"},
    )
    csv = HEADER + "2026-06-01,09:00,10:00,teacher@test.com,BATCH-A,PHY,R101,offline,\n"
    resp = await client.post(
        "/api/v1/lectures/import/preview",
        params={"branch_id": BRANCH_A_ID},
        files={"file": ("schedule.csv", csv.encode(), "text/csv")},
    )
    body = resp.json()
    assert body["ok_count"] == 0 and body["error_count"] == 1
    assert "holiday" in body["rows"][0]["message"].lower()


# ── Excel (.xlsx) ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_xlsx_import(client: AsyncClient, db_session, seed_data):
    from openpyxl import Workbook

    await _login_admin(client)
    await _map_subject(db_session)
    wb = Workbook()
    ws = wb.active
    ws.append(
        [
            "date", "start_time", "end_time", "teacher_email", "batch_code",
            "subject_code", "classroom_code", "delivery_mode", "notes",
        ]
    )
    ws.append(
        ["2026-06-01", "09:00", "10:00", "teacher@test.com", "BATCH-A",
         "PHY", "R101", "offline", "xl"]
    )
    buf = io.BytesIO()
    wb.save(buf)
    resp = await client.post(
        "/api/v1/lectures/import",
        params={"branch_id": BRANCH_A_ID},
        files={
            "file": (
                "schedule.xlsx",
                buf.getvalue(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["imported"] == 1 and body["skipped"] == 0
