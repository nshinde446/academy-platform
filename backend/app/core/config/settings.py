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

    # --- Error reporting (Sentry) ---
    # Empty DSN disables reporting entirely, which is the correct state for
    # local dev and CI. See app/core/observability/sentry.py.
    SENTRY_DSN: str = ""
    # Release identifier, so a stack trace maps to a deployed commit. The
    # deploy sets this to the image SHA.
    SENTRY_RELEASE: str = ""
    # Performance tracing is off by default — errors are the point, and traces
    # are the expensive part of the quota.
    SENTRY_TRACES_SAMPLE_RATE: float = 0.0

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

    # Institute name printed in the header of generated paper PDFs and
    # attendance reports. Single-tenant deployment (Matrix Science Academy), so
    # this is the brand default; override via env for another institute. Full
    # per-branch branding (logo/colours) comes later.
    ACADEMY_BRAND_NAME: str = "Matrix Science Academy"

    # Comma-separated emails allowed into the developer-only monitoring dashboard
    # (/dev). Gated by email, not role — so no branch_admin or other role can see
    # it, only the listed developer(s).
    DEVELOPER_EMAILS: str = "nshinde446@gmail.com"

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
    # Server → device provisioning (push student identity to the terminal so
    # staff never hand-type a name + roll number). Off by default: while false
    # the provisioning API returns 503 and the queue is never emitted to the
    # device, so shipping the plumbing cannot affect live attendance. See
    # docs/biomax-provisioning-implementation.md.
    # RBAC enforcement kill-switch (Phase 2). OFF = every new role/batch-scope
    # guard no-ops and access behaves exactly as before, so the code ships inert.
    # Flip ON per deploy once Floor Coordinator batch lists + Accounts grants are
    # set; flip OFF for instant rollback. Managers are never restricted either way.
    RBAC_ENFORCEMENT_ENABLED: bool = False

    BIOMAX_PROVISIONING_ENABLED: bool = False
    # Shared secret the on-site device-user sync agent presents
    # (``X-BioMax-Sync-Token`` header) when it POSTs the device's real user table
    # (read via the terminal's local ``/bin/cmd`` API) to
    # ``/attendance/provisioning/device-users/sync``. That snapshot is the ground
    # truth for which students are actually enrolled on the device — it rebuilds
    # the ``device_users`` mirror so reconcile's "awaiting face" / name-drift stop
    # relying on catching the device's one-time enrollment pushes. Empty = agent
    # sync disabled (fail-safe: reject rather than accept a spoofed snapshot).
    BIOMAX_SYNC_TOKEN: str = ""
    # Fernet key (urlsafe-base64 32 bytes) that encrypts the biometric backup —
    # face/photo/fingerprint templates the device pushes on each enrolment, kept
    # so a lost/reset terminal can be restored WITHOUT re-enrolling every student.
    # Empty = biometric backup OFF (blobs are dropped as before; the identity
    # mirror still works). This is sensitive PII: the key lives ONLY in the env,
    # never in the repo, so a DB dump alone can't reveal templates. Generate with
    # `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.
    BIOMAX_BIOMETRIC_KEY: str = ""

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
    # Shared secret the on-prem agent presents (X-SmartOffice-Token header) when
    # it pushes rows read from SmartOffice's SQL table to /attendance/smartoffice/
    # ingest. Empty = agent push disabled (fail-safe: reject rather than accept
    # spoofed punches). Generate a long random value; keep it only on the agent
    # PC and this server.
    SMARTOFFICE_INGEST_TOKEN: str = ""

    # ── WhatsApp (Meta Cloud API) parent notifications ─────────────────────
    # We send transactional "utility" template messages (attendance alerts)
    # to parents directly through Meta's Cloud API — no BSP middleman. Off by
    # default: while false the sender is a no-op and the queue-drain job skips
    # WhatsApp rows, so shipping the plumbing cannot send a message or incur a
    # Meta charge until a real token + phone-number id are set and this is
    # flipped on (mirrors BIOMAX_PROVISIONING_ENABLED). See
    # docs/whatsapp-attendance-notifications.md.
    WHATSAPP_ENABLED: bool = False
    # Permanent access token from the Meta app (System User token recommended).
    WHATSAPP_ACCESS_TOKEN: str = ""
    # The WhatsApp Business phone number's ID (not the phone number itself) —
    # from Meta > WhatsApp > API Setup.
    WHATSAPP_PHONE_NUMBER_ID: str = ""
    # Graph API version the Cloud API is called against. Pinned so a Meta
    # version bump can't silently change behaviour; raise deliberately.
    WHATSAPP_API_VERSION: str = "v21.0"


@lru_cache
def get_settings() -> Settings:
    return Settings()
