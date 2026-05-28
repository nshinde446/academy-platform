import io
import uuid
from pathlib import Path

import pytest

from app.core.storage.backend import (
    LocalFilesystemBackend,
    build_storage_key,
    compute_sha256,
)


# ── Storage backend unit tests (no DB) ────────────────────────────────────


class TestLocalFilesystemBackend:
    def test_write_read_roundtrip(self, tmp_path: Path):
        backend = LocalFilesystemBackend(tmp_path)
        key = "2026-27/class-11/physics/ncert/abc--file.pdf"
        backend.write(key, b"hello world")
        assert backend.exists(key)
        assert backend.read(key) == b"hello world"
        assert backend.size(key) == 11

    def test_overwrite_replaces_content(self, tmp_path: Path):
        backend = LocalFilesystemBackend(tmp_path)
        key = "year/class-11/phy/ncert/x--a.pdf"
        backend.write(key, b"v1")
        backend.write(key, b"v2-longer")
        assert backend.read(key) == b"v2-longer"

    def test_delete_idempotent(self, tmp_path: Path):
        backend = LocalFilesystemBackend(tmp_path)
        key = "year/class-11/phy/ncert/x--a.pdf"
        backend.write(key, b"x")
        backend.delete(key)
        backend.delete(key)  # second delete must not raise
        assert not backend.exists(key)

    def test_rejects_path_escape(self, tmp_path: Path):
        backend = LocalFilesystemBackend(tmp_path)
        with pytest.raises(ValueError):
            backend.write("../../etc/passwd", b"x")
        with pytest.raises(ValueError):
            backend.write("/abs/path.pdf", b"x")

    def test_read_missing_raises(self, tmp_path: Path):
        backend = LocalFilesystemBackend(tmp_path)
        with pytest.raises(FileNotFoundError):
            backend.read("year/class-11/phy/ncert/x--a.pdf")


class TestStorageHelpers:
    def test_compute_sha256_known_vector(self):
        # Standard "hello" SHA-256 digest.
        digest = compute_sha256(b"hello")
        assert digest == (
            "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
        )

    def test_build_storage_key_canonical(self):
        key = build_storage_key(
            material_id="aaaa",
            academic_year_code="2026-27",
            class_label="11",
            subject_slug="physics",
            category="ncert",
            filename="Work, Energy & Power.pdf",
        )
        assert key == "2026-27/class-11/physics/ncert/aaaa--Work, Energy & Power.pdf"

    def test_build_storage_key_strips_path_components(self):
        # Hostile filename with path components — must be flattened.
        key = build_storage_key(
            material_id="x",
            academic_year_code="2026-27",
            class_label="11",
            subject_slug="physics",
            category="ncert",
            filename="../../etc/passwd",
        )
        # _safe_filename keeps only the basename, so the dirs are gone.
        assert "/../" not in key
        assert key.endswith("--passwd")


# ── API integration tests ─────────────────────────────────────────────────


async def _login_admin(client) -> str:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.com", "password": "Admin123!"},
    )
    assert resp.status_code == 200, resp.text
    return resp.cookies["access_token"]


async def _upload_pdf(
    client,
    token: str,
    *,
    seed_data,
    content: bytes = b"%PDF-1.4 fake bytes",
    filename: str = "ncert-mcq.pdf",
    category: str = "ncert",
    exam_types: str = "neet,jee_main",
    batch_ids: str | None = None,
):
    files = {"file": (filename, io.BytesIO(content), "application/pdf")}
    data = {
        "academic_year_id": str(seed_data["academic_year"].id),
        "class_label": "11",
        "subject_id": str(seed_data["subject"].id),
        "category": category,
        "exam_types": exam_types,
        "topic": "mechanics",
    }
    if batch_ids:
        data["batch_ids"] = batch_ids
    return await client.post(
        f"/api/v1/materials?branch_id={seed_data['branch_a'].id}",
        files=files,
        data=data,
        cookies={"access_token": token},
    )


class TestMaterialsAPI:
    @pytest.mark.usefixtures("seed_data")
    async def test_upload_happy_path(self, client, seed_data, monkeypatch, tmp_path):
        # Pin the storage backend to tmp_path so we don't pollute repo dirs.
        from app.core.storage import backend as backend_mod
        backend_mod._default_backend = LocalFilesystemBackend(tmp_path)

        token = await _login_admin(client)
        resp = await _upload_pdf(client, token, seed_data=seed_data)
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["filename"] == "ncert-mcq.pdf"
        assert body["category"] == "ncert"
        assert body["exam_types"] == ["neet", "jee_main"]
        assert body["class_label"] == "11"
        assert body["question_count"] == 0
        assert body["ingest_status"] == "uploaded"
        # File actually landed on disk.
        assert (tmp_path / body["storage_key"]).is_file()

        backend_mod._default_backend = None  # reset

    @pytest.mark.usefixtures("seed_data")
    async def test_upload_dedup_on_sha256(self, client, seed_data, tmp_path):
        from app.core.storage import backend as backend_mod
        backend_mod._default_backend = LocalFilesystemBackend(tmp_path)

        token = await _login_admin(client)
        r1 = await _upload_pdf(client, token, seed_data=seed_data, content=b"same-bytes")
        r2 = await _upload_pdf(
            client, token, seed_data=seed_data, content=b"same-bytes",
            filename="different-name.pdf",
        )
        assert r1.status_code == 201
        assert r2.status_code == 201
        # Second upload returns the same material (no duplicate row).
        assert r1.json()["id"] == r2.json()["id"]
        assert r1.json()["sha256"] == r2.json()["sha256"]

        backend_mod._default_backend = None

    @pytest.mark.usefixtures("seed_data")
    async def test_list_with_filters(self, client, seed_data, tmp_path):
        from app.core.storage import backend as backend_mod
        backend_mod._default_backend = LocalFilesystemBackend(tmp_path)

        token = await _login_admin(client)
        # Upload three materials with distinct content + categories.
        await _upload_pdf(
            client, token, seed_data=seed_data, content=b"a", category="ncert"
        )
        await _upload_pdf(
            client, token, seed_data=seed_data, content=b"b",
            category="dpp", filename="dpp1.pdf",
        )
        await _upload_pdf(
            client, token, seed_data=seed_data, content=b"c",
            category="dpp", filename="dpp2.pdf",
        )

        # Filter by category
        resp = await client.get(
            f"/api/v1/materials?branch_id={seed_data['branch_a'].id}&category=dpp",
            cookies={"access_token": token},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2
        assert all(m["category"] == "dpp" for m in body["items"])

        # Facet counts reflect the same scoping (category facet itself excluded
        # from its own filter — both ncert and dpp visible).
        resp = await client.get(
            f"/api/v1/materials/facets?branch_id={seed_data['branch_a'].id}",
            cookies={"access_token": token},
        )
        assert resp.status_code == 200
        cats = {b["value"]: b["count"] for b in resp.json()["categories"]}
        assert cats == {"ncert": 1, "dpp": 2}

        backend_mod._default_backend = None

    @pytest.mark.usefixtures("seed_data")
    async def test_ingest_endpoint_serializes(
        self, client, seed_data, tmp_path, monkeypatch
    ):
        """Regression: the ingest endpoint must serialize its response
        (MaterialResponse includes updated_at, which the UPDATE expires —
        without an in-context refresh this raised MissingGreenlet during
        FastAPI serialization)."""
        from app.core.storage import backend as backend_mod
        backend_mod._default_backend = LocalFilesystemBackend(tmp_path)

        # Stub the background extractor so the test doesn't call Gemini.
        called = {}

        async def _fake_extract(material_id, branch_id, **kw):
            called["material_id"] = material_id
            return {"ok": True, "inserted": 0}

        from app.modules.materials.services import ingest_service
        monkeypatch.setattr(ingest_service, "extract_and_store", _fake_extract)

        token = await _login_admin(client)
        resp = await _upload_pdf(client, token, seed_data=seed_data)
        material_id = resp.json()["id"]

        ingest_resp = await client.post(
            f"/api/v1/materials/{material_id}/ingest?branch_id={seed_data['branch_a'].id}",
            cookies={"access_token": token},
        )
        assert ingest_resp.status_code == 200, ingest_resp.text
        body = ingest_resp.json()
        assert body["ingest_status"] == "ingesting"
        assert body["updated_at"]  # serialized cleanly, no MissingGreenlet

        backend_mod._default_backend = None

    @pytest.mark.usefixtures("seed_data")
    async def test_soft_delete(self, client, seed_data, tmp_path):
        from app.core.storage import backend as backend_mod
        backend_mod._default_backend = LocalFilesystemBackend(tmp_path)

        token = await _login_admin(client)
        resp = await _upload_pdf(client, token, seed_data=seed_data)
        material_id = resp.json()["id"]

        del_resp = await client.delete(
            f"/api/v1/materials/{material_id}?branch_id={seed_data['branch_a'].id}",
            cookies={"access_token": token},
        )
        assert del_resp.status_code == 204

        # Re-fetch should 404.
        get_resp = await client.get(
            f"/api/v1/materials/{material_id}?branch_id={seed_data['branch_a'].id}",
            cookies={"access_token": token},
        )
        assert get_resp.status_code == 404

        backend_mod._default_backend = None
