"""
Settings read from environment variables.

backend/.env is loaded if it exists (see .env.example). Importing this module
fails with a clear message when the required Supabase variables are missing.
"""

import os
import re
from dataclasses import dataclass
from datetime import time
from pathlib import Path
from zoneinfo import ZoneInfo

import weights  # loads backend/.env; shared weights defaults
from weights import BACKEND_DIR, PROJECT_ROOT  # noqa: F401  (re-exported for other modules)

REQUIRED = ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY")


def _path(name: str, default: Path) -> Path:
    value = os.getenv(name)
    if not value:
        return default
    p = Path(value)
    return p if p.is_absolute() else (BACKEND_DIR / p).resolve()


@dataclass(frozen=True)
class Settings:
    env: str
    auth_disabled: bool
    db_disabled: bool
    supabase_url: str
    supabase_service_role_key: str
    supabase_bucket: str
    cors_origins: list[str]
    max_upload_mb: int
    rate_limit_per_minute: int
    signed_url_ttl_seconds: int
    ppe_confidence: float
    person_confidence: float
    violation_window_seconds: float
    violation_clear_seconds: float
    tracker: str
    camera_secret_key: str
    stream_allowed_schemes: tuple[str, ...]
    stream_default_fps: float
    stream_autostart: bool
    site_timezone: ZoneInfo
    shifts: tuple[tuple[str, time, time], ...]
    app_base_url: str
    alert_sources: tuple[str, ...]
    privacy_blur: bool
    evidence_secret_key: str
    original_retention_hours: float
    retention_days: float
    retention_interval_minutes: float
    ppe_model_path: Path
    ppe_model_sha256: str
    helmet_model_path: Path
    helmet_model_sha256: str
    person_model_path: Path
    person_model_sha256: str
    upload_dir: Path

    @property
    def is_production(self) -> bool:
        return self.env == "production"


def parse_shifts(spec: str) -> tuple[tuple[str, time, time], ...]:
    """"Morning=06:00-14:00,Night=22:00-06:00" -> ((name, start, end), ...). A shift may wrap past midnight."""
    shifts = []
    for part in filter(None, (x.strip() for x in spec.split(","))):
        m = re.fullmatch(r"([^=]{1,40})=(\d{1,2}):(\d{2})-(\d{1,2}):(\d{2})", part)
        if not m:
            raise RuntimeError(f"SHIFTS: cannot read {part!r}; expected Name=HH:MM-HH:MM")
        name, h1, m1, h2, m2 = m.groups()
        shifts.append((name.strip(), time(int(h1), int(m1)), time(int(h2), int(m2))))
    return tuple(shifts)


def load_settings() -> Settings:
    env = os.getenv("ENV", "development").lower()
    auth_disabled = os.getenv("AUTH_DISABLED", "false").lower() == "true"
    db_disabled = os.getenv("DB_DISABLED", "false").lower() == "true"
    if (auth_disabled or db_disabled) and env == "production":
        raise RuntimeError("AUTH_DISABLED / DB_DISABLED are not allowed when ENV=production.")
    if db_disabled and not auth_disabled:
        raise RuntimeError("DB_DISABLED=true needs AUTH_DISABLED=true (sign-in uses Supabase).")

    missing = [] if db_disabled else [name for name in REQUIRED if not os.getenv(name)]
    if missing:
        raise RuntimeError(
            f"Missing required environment variables: {', '.join(missing)}. "
            "Copy backend/.env.example to backend/.env and fill in the values "
            "from Supabase -> Project Settings -> API (see supabase/README.md)."
        )

    return Settings(
        env=env,
        auth_disabled=auth_disabled,
        db_disabled=db_disabled,
        supabase_url=os.getenv("SUPABASE_URL", ""),
        supabase_service_role_key=os.getenv("SUPABASE_SERVICE_ROLE_KEY", ""),
        supabase_bucket=os.getenv("SUPABASE_BUCKET", "violation-screenshots"),
        cors_origins=[
            o.strip()
            for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
            if o.strip()
        ],
        max_upload_mb=int(os.getenv("MAX_UPLOAD_MB", "50")),
        rate_limit_per_minute=int(os.getenv("RATE_LIMIT_PER_MINUTE", "30")),
        signed_url_ttl_seconds=int(os.getenv("SIGNED_URL_TTL_SECONDS", "300")),
        ppe_confidence=float(os.getenv("PPE_CONFIDENCE", "0.4")),
        person_confidence=float(os.getenv("PERSON_CONFIDENCE", "0.4")),
        violation_window_seconds=float(os.getenv("VIOLATION_WINDOW_SECONDS", "2")),
        violation_clear_seconds=float(os.getenv("VIOLATION_CLEAR_SECONDS", "1")),
        tracker=os.getenv("TRACKER", "bytetrack").lower(),
        camera_secret_key=os.getenv("CAMERA_SECRET_KEY", "").strip(),
        stream_allowed_schemes=tuple(
            x.strip().lower() for x in os.getenv("STREAM_ALLOWED_SCHEMES", "rtsp,rtsps").split(",") if x.strip()
        ),
        stream_default_fps=float(os.getenv("STREAM_SAMPLE_FPS", "5")),
        stream_autostart=os.getenv("STREAM_AUTOSTART", "true").lower() == "true",
        site_timezone=ZoneInfo(os.getenv("SITE_TIMEZONE", "Asia/Kolkata")),
        shifts=parse_shifts(os.getenv("SHIFTS", "A=06:00-14:00,B=14:00-22:00,C=22:00-06:00")),
        app_base_url=os.getenv("APP_BASE_URL", "http://localhost:5173").rstrip("/"),
        alert_sources=tuple(x.strip() for x in os.getenv("ALERT_SOURCES", "camera").split(",") if x.strip()),
        privacy_blur=os.getenv("PRIVACY_BLUR", "true").lower() == "true",
        evidence_secret_key=os.getenv("EVIDENCE_SECRET_KEY", "").strip(),
        original_retention_hours=float(os.getenv("ORIGINAL_RETENTION_HOURS", "72")),
        retention_days=float(os.getenv("RETENTION_DAYS", "30")),
        retention_interval_minutes=float(os.getenv("RETENTION_INTERVAL_MINUTES", "60")),
        ppe_model_path=weights.resolve("PPE_MODEL_PATH"),
        ppe_model_sha256=os.getenv("PPE_MODEL_SHA256", "").strip().lower(),
        helmet_model_path=weights.resolve("HELMET_MODEL_PATH"),
        helmet_model_sha256=os.getenv("HELMET_MODEL_SHA256", "").strip().lower(),
        person_model_path=weights.resolve("PERSON_MODEL_PATH"),
        person_model_sha256=os.getenv("PERSON_MODEL_SHA256", "").strip().lower(),
        upload_dir=_path("UPLOAD_DIR", BACKEND_DIR / "uploads"),
    )


settings = load_settings()
