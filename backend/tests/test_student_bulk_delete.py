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


class TestBulkDelete:
    @pytest.mark.usefixtures("seed_data")
    async def test_delete_all_requires_confirm(self, client, seed_data):
        token = await _login(client)
        resp = await client.post(
            f"/api/v1/students/delete-all?branch_id={BRANCH}",
            cookies={"access_token": token},
        )
        assert resp.status_code == 400

    @pytest.mark.usefixtures("seed_data")
    async def test_delete_all_soft_deletes_and_is_idempotent(self, client, seed_data):
        token = await _login(client)
        await client.post(
            f"/api/v1/students/import?branch_id={BRANCH}",
            files={
                "file": (
                    "s.csv",
                    _csv("Asha,11,NEET,BATCH-A,D-1", "Bina,11,NEET,BATCH-A,D-2"),
                    "text/csv",
                )
            },
            cookies={"access_token": token},
        )
        before = await client.get(
            f"/api/v1/students?branch_id={BRANCH}", cookies={"access_token": token}
        )
        assert len(before.json()) >= 2

        wiped = await client.post(
            f"/api/v1/students/delete-all?branch_id={BRANCH}&confirm=true",
            cookies={"access_token": token},
        )
        assert wiped.status_code == 200
        assert wiped.json()["deleted"] >= 2

        after = await client.get(
            f"/api/v1/students?branch_id={BRANCH}", cookies={"access_token": token}
        )
        assert after.json() == []

        # Idempotent: nothing left to delete.
        again = await client.post(
            f"/api/v1/students/delete-all?branch_id={BRANCH}&confirm=true",
            cookies={"access_token": token},
        )
        assert again.json()["deleted"] == 0

    @pytest.mark.usefixtures("seed_data")
    async def test_reimport_after_delete_recreates_students(self, client, seed_data):
        """After a wipe, the same roll numbers import again (not skipped as
        duplicates) — enabling a clean stream-enhanced re-import."""
        token = await _login(client)
        file = {"file": ("s.csv", _csv("Asha,11,NEET,BATCH-A,D-9"), "text/csv")}
        await client.post(
            f"/api/v1/students/import?branch_id={BRANCH}",
            files=file,
            cookies={"access_token": token},
        )
        await client.post(
            f"/api/v1/students/delete-all?branch_id={BRANCH}&confirm=true",
            cookies={"access_token": token},
        )
        again = await client.post(
            f"/api/v1/students/import?branch_id={BRANCH}",
            files={"file": ("s.csv", _csv("Asha,11,NEET,BATCH-A,D-9"), "text/csv")},
            cookies={"access_token": token},
        )
        data = again.json()
        assert data["imported"] == 1  # recreated, not skipped as duplicate
