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

    # ── Biometric device integrations ──────────────────────────────────────
    # See docs/biometric-attendance-design.md (integrations section).
    #
    # eTimeOffice / TeamOffice (cloud SaaS) — we PULL punches from their REST
    # API on a schedule. Credentials come from the client's API panel. When
    # ETO_ENABLED is false the poll job and pull route are no-ops, so the
    # rest of the platform runs without these set.
    ETO_ENABLED: bool = False
    ETO_BASE_URL: str = "https://api.etimeoffice.com/api"
    ETO_CORP_ID: str = ""
    ETO_USERNAME: str = ""
    ETO_PASSWORD: str = ""
    # How far back each poll re-pulls, to catch punches the device synced late.
    ETO_LOOKBACK_DAYS: int = 2
    # Branch every eTimeOffice punch is attributed to. Single-corporate setups
    # have one branch; multi-branch mapping can come later.
    ETO_BRANCH_ID: str = ""

    # BioMax SmartOffice (on-prem devices) — devices PUSH punches to us via the
    # ZKTeco/ADMS "iclock" protocol. We trust a device only if its serial is in
    # this allowlist (comma-separated). Empty = reject all (fail-safe).
    BIOMAX_DEVICE_SERIALS: str = ""
    # Branch that iclock push devices attribute punches to (single-site
    # assumption, mirroring ETO_BRANCH_ID). Per-serial branch mapping can come
    # later; for now all allowed devices map here.
    BIOMAX_BRANCH_ID: str = ""

    # SmartOffice (SmartOfficePayroll) cloud middleware — the ZKTeco devices
    # push to SmartOffice's server and we PULL the aggregated logs from its REST
    # API (GetDeviceLogs) on a short interval for near-real-time attendance.
    # When SMARTOFFICE_ENABLED is false the poll job and pull route are no-ops.
    SMARTOFFICE_ENABLED: bool = False
    # Base host of the client's SmartOffice deployment, e.g. "http://45.118.183.175:86".
    SMARTOFFICE_BASE_URL: str = ""
    # APIKey issued from the SmartOffice web app.
    SMARTOFFICE_API_KEY: str = ""
    # How far back each poll re-pulls, to catch punches SmartOffice recorded late.
    SMARTOFFICE_LOOKBACK_DAYS: int = 1
    # Branch every SmartOffice punch is attributed to (single-site assumption,
    # mirroring ETO_BRANCH_ID). Multi-branch serial->branch mapping comes later.
    SMARTOFFICE_BRANCH_ID: str = ""
    # Optional device-serial allowlist (comma-separated). Empty = accept every
    # serial GetDeviceLogs returns; set it to ignore devices from other sites.
    SMARTOFFICE_DEVICE_SERIALS: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
