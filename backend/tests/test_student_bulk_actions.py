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


async def _import(client, token, *lines, create_missing=False):
    suffix = "&create_missing_batches=true" if create_missing else ""
    return await client.post(
        f"/api/v1/students/import?branch_id={BRANCH}{suffix}",
        files={"file": ("s.csv", _csv(*lines), "text/csv")},
        cookies={"access_token": token},
    )


async def _ids_by_roll(client, token) -> dict[str, str]:
    resp = await client.get(
        f"/api/v1/students?branch_id={BRANCH}&limit=200",
        cookies={"access_token": token},
    )
    return {s["enrollment_number"]: s["id"] for s in resp.json()}


class TestBulkUpdate:
    @pytest.mark.usefixtures("seed_data")
    async def test_bulk_set_fees_and_class(self, client, seed_data):
        token = await _login(client)
        await _import(client, token, "Asha,11,NEET,BATCH-A,U-1", "Bina,11,NEET,BATCH-A,U-2")
        ids = await _ids_by_roll(client, token)
        targets = [ids["U-1"], ids["U-2"]]

        resp = await client.post(
            f"/api/v1/students/bulk-update?branch_id={BRANCH}",
            json={"student_ids": targets, "fees_status": "paid", "standard": "12"},
            cookies={"access_token": token},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["updated"] == 2

        for sid in targets:
            s = (
                await client.get(
                    f"/api/v1/students/{sid}?branch_id={BRANCH}",
                    cookies={"access_token": token},
                )
            ).json()
            assert s["fees_status"] == "paid"
            assert s["standard"] == "12"

    @pytest.mark.usefixtures("seed_data")
    async def test_invalid_fees_is_422(self, client, seed_data):
        token = await _login(client)
        await _import(client, token, "Asha,11,NEET,BATCH-A,U-3")
        ids = await _ids_by_roll(client, token)
        resp = await client.post(
            f"/api/v1/students/bulk-update?branch_id={BRANCH}",
            json={"student_ids": [ids["U-3"]], "fees_status": "not-a-status"},
            cookies={"access_token": token},
        )
        assert resp.status_code == 422

    @pytest.mark.usefixtures("seed_data")
    async def test_foreign_ids_are_ignored(self, client, seed_data):
        token = await _login(client)
        resp = await client.post(
            f"/api/v1/students/bulk-update?branch_id={BRANCH}",
            json={
                "student_ids": ["00000000-0000-0000-0000-0000000000ff"],
                "fees_status": "paid",
            },
            cookies={"access_token": token},
        )
        assert resp.status_code == 200
        assert resp.json()["updated"] == 0

    @pytest.mark.usefixtures("seed_data")
    async def test_bulk_assign_batch(self, client, seed_data, db_session):
        from sqlalchemy import select

        from app.modules.batch.models.batch_models import Batch

        token = await _login(client)
        await _import(client, token, "Asha,11,NEET,BATCH-A,U-5")
        # Create a second batch to reassign into.
        await _import(client, token, "Tmp,11,NEET,NEET-11-A,U-6", create_missing=True)
        ids = await _ids_by_roll(client, token)

        new_batch_id = str(
            (
                await db_session.execute(select(Batch.id).where(Batch.code == "NEET-11-A"))
            ).scalar_one()
        )

        resp = await client.post(
            f"/api/v1/students/bulk-update?branch_id={BRANCH}",
            json={"student_ids": [ids["U-5"]], "batch_id": new_batch_id},
            cookies={"access_token": token},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["updated"] == 1

        roster = (
            await client.get(
                f"/api/v1/students/roster?branch_id={BRANCH}&search=U-5",
                cookies={"access_token": token},
            )
        ).json()
        moved = next(r for r in roster["items"] if r["enrollment_number"] == "U-5")
        assert moved["batch_name"] == "NEET-11-A"


class TestBulkDeleteSelected:
    @pytest.mark.usefixtures("seed_data")
    async def test_delete_subset_keeps_the_rest(self, client, seed_data):
        token = await _login(client)
        await _import(
            client,
            token,
            "A,11,NEET,BATCH-A,B-1",
            "B,11,NEET,BATCH-A,B-2",
            "C,11,NEET,BATCH-A,B-3",
        )
        ids = await _ids_by_roll(client, token)

        resp = await client.post(
            f"/api/v1/students/bulk-delete?branch_id={BRANCH}",
            json={"student_ids": [ids["B-1"], ids["B-2"]]},
            cookies={"access_token": token},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["deleted"] == 2

        remaining = await _ids_by_roll(client, token)
        assert "B-3" in remaining
        assert "B-1" not in remaining and "B-2" not in remaining
