"""
Settings read from environment variables.

backend/.env is loaded if it exists (see .env.example). Importing this module
fails with a clear message when the required Supabase variables are missing.
"""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent
RUNS_DIR = PROJECT_ROOT / "ai-model" / "outputs" / "training-runs"

load_dotenv(BACKEND_DIR / ".env")

REQUIRED = ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY")

# Trained PPE (vest) weights, newest first. Only used when PPE_MODEL_PATH is unset.
# Never includes the COCO yolov8n.pt weights: those have no PPE classes.
PPE_MODEL_CANDIDATES = [
    RUNS_DIR / "safevision_yolov8n_5class_v5d_50epochs" / "weights" / "best.pt",
    RUNS_DIR / "safevision_yolov8n_5class_v2" / "weights" / "best.pt",
]


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
    video_cooldown_seconds: float
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

    default_ppe = next((p for p in PPE_MODEL_CANDIDATES if p.exists()), PPE_MODEL_CANDIDATES[0])

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
        video_cooldown_seconds=float(os.getenv("VIDEO_COOLDOWN_SECONDS", "5")),
        ppe_model_path=_path("PPE_MODEL_PATH", default_ppe),
        ppe_model_sha256=os.getenv("PPE_MODEL_SHA256", "").strip().lower(),
        helmet_model_path=_path(
            "HELMET_MODEL_PATH", RUNS_DIR / "safevision_yolov8n_v1" / "weights" / "best.pt"
        ),
        helmet_model_sha256=os.getenv("HELMET_MODEL_SHA256", "").strip().lower(),
        person_model_path=_path("PERSON_MODEL_PATH", PROJECT_ROOT / "yolov8n.pt"),
        person_model_sha256=os.getenv("PERSON_MODEL_SHA256", "").strip().lower(),
        upload_dir=_path("UPLOAD_DIR", BACKEND_DIR / "uploads"),
    )


settings = load_settings()
