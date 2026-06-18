"""CORS_ORIGINS env parsing — regression for the staging deploy failure where a
comma-separated CORS_ORIGINS in .env raised pydantic SettingsError at startup
(the env source JSON-decodes list fields before validators run)."""

from app.core.config.settings import Settings


def _settings(monkeypatch, value: str) -> Settings:
    monkeypatch.setenv("CORS_ORIGINS", value)
    return Settings()


def test_cors_origins_comma_separated(monkeypatch):
    s = _settings(monkeypatch, "https://staging.academy.com,https://academy.com")
    assert s.CORS_ORIGINS == [
        "https://staging.academy.com",
        "https://academy.com",
    ]


def test_cors_origins_json_array(monkeypatch):
    s = _settings(monkeypatch, '["https://a.com","https://b.com"]')
    assert s.CORS_ORIGINS == ["https://a.com", "https://b.com"]


def test_cors_origins_single_value(monkeypatch):
    s = _settings(monkeypatch, "https://only.com")
    assert s.CORS_ORIGINS == ["https://only.com"]


def test_cors_origins_strips_and_drops_blanks(monkeypatch):
    s = _settings(monkeypatch, " https://a.com , , https://b.com ")
    assert s.CORS_ORIGINS == ["https://a.com", "https://b.com"]
