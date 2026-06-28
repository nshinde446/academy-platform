import json
from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    PROJECT_NAME: str = "Academy Platform"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"

    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/academy_platform"
    REDIS_URL: str = "redis://localhost:6379/0"

    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    COOKIE_SECURE: bool = False
    COOKIE_SAMESITE: str = "lax"
    # NoDecode: don't let pydantic-settings JSON-decode the env value itself —
    # the validator below handles both a JSON array (["a","b"]) and a plain
    # comma-separated string (a,b). Without this a comma-separated CORS_ORIGINS
    # in .env raises SettingsError at startup (the env source decodes first).
    CORS_ORIGINS: Annotated[list[str], NoDecode] = ["http://localhost:3000"]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _parse_cors_origins(cls, v: object) -> object:
        if isinstance(v, str):
            s = v.strip()
            if not s:
                return []
            if s.startswith("["):
                return json.loads(s)
            return [o.strip() for o in s.split(",") if o.strip()]
        return v

    ATTENDANCE_GRACE_PERIOD_MINUTES: int = 10
    ATTENDANCE_DUPLICATE_WINDOW_MINUTES: int = 5
    # Day-attendance (biometric) — see docs/biometric-attendance-design.md.
    # Timezone is stored per branch (branch.timezone); this is only the
    # fallback for branches with no value set.
    DEFAULT_TIMEZONE: str = "Asia/Kolkata"
    # Local wall-clock the coaching day's first lecture starts. A first punch
    # at or before START + grace is on-time (PRESENT), later is LATE.
    ATTENDANCE_CLASS_START_HOUR: int = 10
    ATTENDANCE_CLASS_START_MINUTE: int = 0
    # Campus operating window (local). Punches outside it aren't attributed to
    # the day's sign-in/sign-off (Reference B header: "07:00 - 15:00").
    ATTENDANCE_CAMPUS_OPEN_HOUR: int = 7
    ATTENDANCE_CAMPUS_CLOSE_HOUR: int = 15

    # Safety cap on Materials ingest — at most this many PDF pages get
    # sent to Gemini Vision per ingest, bounding worst-case API cost if
    # someone uploads a huge document. Most coaching PDFs are well under
    # this. Raise if you legitimately ingest larger files.
    MATERIALS_INGEST_MAX_PAGES: int = 100

    # Institute name printed in the header of generated paper PDFs
    # (Tier 14). Full per-branch branding (logo/colours) comes later;
    # for now this single name is enough.
    ACADEMY_BRAND_NAME: str = "Academy Institute"


@lru_cache
def get_settings() -> Settings:
    return Settings()
