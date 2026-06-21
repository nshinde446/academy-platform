import uuid as _uuid

import pytest

BRANCH = "00000000-0000-0000-0000-000000000001"
# The seeded admin (audit_logs.user_id is a real FK, enforced in tests).
USER = _uuid.UUID("00000000-0000-0000-0000-000000000100")


async def _login(client):
    r = await client.post("/api/v1/auth/login",
        json={"email": "admin@test.com", "password": "Admin123!"})
    return r.cookies["access_token"]


def _csv(*lines):
    return ("\n".join(["Name,Class,Target,Batch,Roll No", *lines]) + "\n").encode("utf-8")


class TestImportJob:
    @pytest.mark.usefixtures("seed_data")
    async def test_process_job_completes_with_results(self, client, seed_data, db_session):
        from app.modules.student.models.student_models import StudentImportJob
        from app.modules.student.services import import_service

        content = _csv(
            "Job One,11,NEET,JOB-A,J-1",
            "Job Two,11,NEET,JOB-A,J-2",
        )
        job = await import_service.start_import_job(
            db_session, content, "j.csv", _uuid.UUID(BRANCH), USER, True
        )
        await db_session.commit()
        assert job.job_status == "pending"
        assert job.total_rows == 2

        await import_service._process_import_job(
            db_session, job.id, content, "j.csv", _uuid.UUID(BRANCH), USER, True
        )

        fresh = await db_session.get(StudentImportJob, job.id)
        assert fresh.job_status == "completed"
        assert fresh.imported == 2
        assert fresh.processed_rows == 2
        assert fresh.batches_created == ["JOB-A"]

    @pytest.mark.usefixtures("seed_data")
    async def test_process_job_records_failure(self, client, seed_data, db_session, monkeypatch):
        from app.modules.student.models.student_models import StudentImportJob
        from app.modules.student.services import import_service

        async def _boom(*a, **k):
            raise RuntimeError("kaboom")

        # Force the engine to blow up mid-run.
        monkeypatch.setattr(import_service, "import_students", _boom)

        content = _csv("X,11,NEET,BATCH-A,JF-1")
        job = await import_service.start_import_job(
            db_session, content, "j.csv", _uuid.UUID(BRANCH), USER, False
        )
        await db_session.commit()
        await import_service._process_import_job(
            db_session, job.id, content, "j.csv", _uuid.UUID(BRANCH), USER, False
        )
        fresh = await db_session.get(StudentImportJob, job.id)
        assert fresh.job_status == "failed"
        assert "kaboom" in (fresh.error_detail or "")

    @pytest.mark.usefixtures("seed_data")
    async def test_start_endpoint_returns_job_and_status_polls(
        self, client, seed_data, monkeypatch
    ):
        from app.modules.student.services import import_service

        # The real background task opens its own (prod) session; stub it so this
        # test exercises only the endpoint wiring. Processing is covered by
        # test_process_job_completes_with_results.
        async def _noop(*a, **k):
            return None

        monkeypatch.setattr(import_service, "run_import_job", _noop)

        token = await _login(client)
        resp = await client.post(
            f"/api/v1/students/import/start?branch_id={BRANCH}&create_missing_batches=true",
            files={"file": ("j.csv", _csv("Poll Me,11,NEET,POLL-A,P-1"), "text/csv")},
            cookies={"access_token": token},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["total_rows"] == 1
        assert body["job_status"] in ("pending", "processing", "completed")
        job_id = body["id"]

        status = await client.get(
            f"/api/v1/students/import/jobs/{job_id}?branch_id={BRANCH}",
            cookies={"access_token": token},
        )
        assert status.status_code == 200
        assert status.json()["id"] == job_id

    @pytest.mark.usefixtures("seed_data")
    async def test_status_404_for_unknown_job(self, client, seed_data):
        token = await _login(client)
        resp = await client.get(
            f"/api/v1/students/import/jobs/{_uuid.uuid4()}?branch_id={BRANCH}",
            cookies={"access_token": token},
        )
        assert resp.status_code == 404
