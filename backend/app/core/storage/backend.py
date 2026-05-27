"""Storage backend abstraction for uploaded study material.

Today we serve everything from the VPS local filesystem
(``LocalFilesystemBackend``). The interface keeps the eventual swap to
S3 / MinIO / Vercel Blob a one-class change — no caller code touches
filesystem paths.

Per the M1 design in ``docs/study-material-and-question-bank.md``:
- Paths are keyed by ``<year>/class-<N>/<subject>/<category>/<uuid>--<filename>``
- Callers never see raw filesystem paths; they pass a ``storage_key``
  string back when they want to read.
- Reads return bytes for small files and a generator for large ones
  (the streaming API isn't built yet — M2 / M3 territory).
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
from abc import ABC, abstractmethod
from pathlib import Path
from typing import BinaryIO


def _safe_filename(filename: str) -> str:
    """Sanitize a user-supplied filename for filesystem safety.

    Removes path separators, collapses whitespace, strips control chars.
    Keeps the extension. Doesn't try to be exhaustive — the storage_key
    is UUID-prefixed so a hostile name still can't collide.
    """
    name = os.path.basename(filename)
    name = re.sub(r"[\x00-\x1f\x7f]", "", name)
    name = re.sub(r"\s+", " ", name).strip()
    name = name.replace("/", "_").replace("\\", "_")
    return name or "unnamed"


def compute_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_storage_key(
    *,
    material_id: str,
    academic_year_code: str,
    class_label: str,
    subject_slug: str,
    category: str,
    filename: str,
) -> str:
    """Canonical key derivation. Same logic every backend uses, so the
    layout is identical on disk and (later) in S3."""
    safe = _safe_filename(filename)
    return (
        f"{academic_year_code}/"
        f"class-{class_label}/"
        f"{subject_slug}/"
        f"{category}/"
        f"{material_id}--{safe}"
    )


class StorageBackend(ABC):
    """Abstract storage. Implementations: local FS today; S3/MinIO/Blob
    later via the same surface."""

    @abstractmethod
    def write(self, storage_key: str, data: bytes) -> None:
        """Persist ``data`` at ``storage_key``. Overwrites if it already
        exists — callers should dedup on sha256 before calling."""

    @abstractmethod
    def read(self, storage_key: str) -> bytes:
        """Return the bytes at ``storage_key`` or raise FileNotFoundError."""

    @abstractmethod
    def delete(self, storage_key: str) -> None:
        """Idempotent. No error if the key doesn't exist."""

    @abstractmethod
    def exists(self, storage_key: str) -> bool:
        ...

    @abstractmethod
    def size(self, storage_key: str) -> int:
        """Bytes on disk. Raises FileNotFoundError if missing."""


class LocalFilesystemBackend(StorageBackend):
    """Stores files under a root directory on the local filesystem.

    Default root is ``<repo>/study_material``. Override via the
    ``STUDY_MATERIAL_ROOT`` env var (used by tests with a tmp dir, and
    by the prod container where the path is bind-mounted)."""

    def __init__(self, root: Path | str | None = None) -> None:
        if root is None:
            root = os.environ.get("STUDY_MATERIAL_ROOT")
        if root is None:
            # backend/ → repo root → study_material/
            root = Path(__file__).resolve().parents[3].parent / "study_material"
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _full_path(self, storage_key: str) -> Path:
        if storage_key.startswith("/") or ".." in storage_key.split("/"):
            raise ValueError(f"Refusing path-escaping storage_key: {storage_key!r}")
        return self.root / storage_key

    def write(self, storage_key: str, data: bytes) -> None:
        path = self._full_path(storage_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        # Write to a tmp sibling then rename — atomic on same FS.
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_bytes(data)
        tmp.replace(path)

    def read(self, storage_key: str) -> bytes:
        return self._full_path(storage_key).read_bytes()

    def delete(self, storage_key: str) -> None:
        path = self._full_path(storage_key)
        if path.exists():
            path.unlink()

    def exists(self, storage_key: str) -> bool:
        return self._full_path(storage_key).is_file()

    def size(self, storage_key: str) -> int:
        return self._full_path(storage_key).stat().st_size


_default_backend: StorageBackend | None = None


def get_storage_backend() -> StorageBackend:
    """FastAPI dependency. Memoized so each request reuses the same
    instance — no per-request filesystem reinit."""
    global _default_backend
    if _default_backend is None:
        _default_backend = LocalFilesystemBackend()
    return _default_backend


def reset_storage_backend_for_tests(backend: StorageBackend | None) -> None:
    """Test helper. Pass an explicit backend (tmp-dir-rooted) or None
    to reset to the default."""
    global _default_backend
    _default_backend = backend
