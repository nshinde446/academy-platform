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


async def _seed_students(client, token, n):
    lines = [f"Student{i:02d} X,11,NEET,BATCH-A,R-{i:03d}" for i in range(n)]
    await client.post(
        f"/api/v1/students/import?branch_id={BRANCH}",
        files={"file": ("s.csv", _csv(*lines), "text/csv")},
        cookies={"access_token": token},
    )


class TestRosterPagination:
    @pytest.mark.usefixtures("seed_data")
    async def test_pagination_returns_page_and_total(self, client, seed_data):
        token = await _login(client)
        await _seed_students(client, token, 10)

        resp = await client.get(
            f"/api/v1/students/roster?branch_id={BRANCH}&offset=0&limit=4",
            cookies={"access_token": token},
        )
        body = resp.json()
        assert len(body["items"]) == 4
        assert body["total"] >= 10  # 10 imported + any seed student

        # Second page returns different rows.
        page2 = (
            await client.get(
                f"/api/v1/students/roster?branch_id={BRANCH}&offset=4&limit=4",
                cookies={"access_token": token},
            )
        ).json()
        first_ids = {r["id"] for r in body["items"]}
        second_ids = {r["id"] for r in page2["items"]}
        assert first_ids.isdisjoint(second_ids)

    @pytest.mark.usefixtures("seed_data")
    async def test_search_filters_total(self, client, seed_data):
        token = await _login(client)
        await _seed_students(client, token, 10)
        resp = await client.get(
            f"/api/v1/students/roster?branch_id={BRANCH}&search=Student03",
            cookies={"access_token": token},
        )
        body = resp.json()
        assert body["total"] == 1
        assert body["items"][0]["first_name"] == "Student03"

    @pytest.mark.usefixtures("seed_data")
    async def test_sort_by_name_desc(self, client, seed_data):
        token = await _login(client)
        await _seed_students(client, token, 5)
        resp = await client.get(
            f"/api/v1/students/roster?branch_id={BRANCH}"
            f"&search=Student&sort_by=name&order=desc",
            cookies={"access_token": token},
        )
        names = [r["first_name"] for r in resp.json()["items"]]
        assert names == sorted(names, reverse=True)
