"""Encryption for the BioMax biometric backup.

Face/photo/fingerprint templates are highly sensitive PII. We keep them so a
lost/reset terminal can be restored without re-enrolling every student — but they
are encrypted at rest with a Fernet key that lives ONLY in the environment
(``BIOMAX_BIOMETRIC_KEY``), so a database dump alone can never reveal a template.

Backup is OFF unless the key is set: with no key the receiver drops the blobs
exactly as before and only the identity mirror is kept.
"""

from __future__ import annotations

from cryptography.fernet import Fernet

from app.core.config.settings import get_settings


def biometric_backup_enabled() -> bool:
    return bool(get_settings().BIOMAX_BIOMETRIC_KEY)


def _fernet() -> Fernet:
    key = get_settings().BIOMAX_BIOMETRIC_KEY
    if not key:
        raise RuntimeError("BIOMAX_BIOMETRIC_KEY is not set")
    return Fernet(key.encode())


def encrypt_template(value: str | None) -> bytes | None:
    """Encrypt one template (the device's base64 string) to a Fernet token, or
    None when there's nothing to store. The base64 string is preserved verbatim
    inside the ciphertext so a restore re-pushes the exact bytes the device gave."""
    if not value:
        return None
    return _fernet().encrypt(value.encode("utf-8"))


def decrypt_template(token: bytes | None) -> str | None:
    """Recover the original base64 template string for a restore push."""
    if not token:
        return None
    return _fernet().decrypt(bytes(token)).decode("utf-8")
