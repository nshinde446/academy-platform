import pytest

BRANCH = "00000000-0000-0000-0000-000000000001"


async def _login(client) -> str:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.com", "password": "Admin123!"},
    )
    return resp.cookies["access_token"]


def _csv(*lines: str) -> bytes:
    header = "Name,Class,Target,Batch,Roll No"
    return ("\n".join([header, *lines]) + "\n").encode("utf-8")


class TestStudentImportPreview:
    @pytest.mark.usefixtures("seed_data")
    async def test_preview_splits_existing_and_missing_batches(self, client, seed_data):
        token = await _login(client)
        content = _csv(
            "Aman Sharma,11,NEET,BATCH-A,S-001",       # existing (seed)
            "Priya Singh,12,NEET,NEET-11-A,S-002",      # missing
            "Rohan Patel,11,JEE-Main,NEET-11-A,S-003",  # missing, same code
        )
        resp = await client.post(
            f"/api/v1/students/import/preview?branch_id={BRANCH}",
            files={"file": ("students.csv", content, "text/csv")},
            cookies={"access_token": token},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_rows"] == 3
        assert data["importable_rows"] == 3
        assert data["existing_batches"] == 1
        assert data["missing_batches"] == 1

        by_code = {b["code"]: b for b in data["batches"]}
        assert by_code["BATCH-A"]["exists"] is True
        missing = by_code["NEET-11-A"]
        assert missing["exists"] is False
        assert missing["student_count"] == 2
        # Dominant Target across the two rows is NEET -> NEET course.
        assert missing["target"] == "NEET"
        assert missing["suggested_course_code"] == "NEET"
        assert missing["suggested_exam_date"] is not None

    @pytest.mark.usefixtures("seed_data")
    async def test_preview_flags_row_issues(self, client, seed_data):
        token = await _login(client)
        content = _csv(
            ",11,NEET,BATCH-A,S-001",                 # missing name
            "Bad Target,11,JEE,BATCH-A,S-002",         # invalid target
        )
        resp = await client.post(
            f"/api/v1/students/import/preview?branch_id={BRANCH}",
            files={"file": ("students.csv", content, "text/csv")},
            cookies={"access_token": token},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["rows_missing_name"] == 1
        assert data["rows_invalid_enrolment"] == 1
        assert any("Invalid target_exam" in m for m in data["row_issues"])


class TestStudentImportCreateMissing:
    @pytest.mark.usefixtures("seed_data")
    async def test_import_without_flag_skips_unknown_batch(self, client, seed_data):
        token = await _login(client)
        content = _csv("Priya Singh,12,NEET,NEET-11-A,S-002")
        resp = await client.post(
            f"/api/v1/students/import?branch_id={BRANCH}",
            files={"file": ("students.csv", content, "text/csv")},
            cookies={"access_token": token},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["imported"] == 0
        assert data["skipped"] == 1
        assert data["batches_created"] == []
        assert any("unknown batch code 'NEET-11-A'" in e for e in data["errors"])

    @pytest.mark.usefixtures("seed_data")
    async def test_import_with_flag_creates_batch_and_assigns(self, client, seed_data):
        token = await _login(client)
        content = _csv(
            "Priya Singh,12,NEET,NEET-11-A,S-002",
            "Rohan Patel,11,NEET,NEET-11-A,S-003",
        )
        resp = await client.post(
            f"/api/v1/students/import?branch_id={BRANCH}&create_missing_batches=true",
            files={"file": ("students.csv", content, "text/csv")},
            cookies={"access_token": token},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["imported"] == 2
        assert data["skipped"] == 0
        assert data["batches_created"] == ["NEET-11-A"]

        # The new batch is now visible on the batches endpoint.
        batches = await client.get(
            f"/api/v1/batches?branch_id={BRANCH}",
            cookies={"access_token": token},
        )
        codes = {b["code"] for b in batches.json()}
        assert "NEET-11-A" in codes

    @pytest.mark.usefixtures("seed_data")
    async def test_import_existing_batch_still_matches(self, client, seed_data):
        token = await _login(client)
        content = _csv("Aman Sharma,11,NEET,BATCH-A,S-001")
        resp = await client.post(
            f"/api/v1/students/import?branch_id={BRANCH}",
            files={"file": ("students.csv", content, "text/csv")},
            cookies={"access_token": token},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["imported"] == 1
        assert data["skipped"] == 0
