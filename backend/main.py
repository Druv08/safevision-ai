"""
SafeVision AI - FastAPI backend.

Run from inside the backend/ folder:

    python -m uvicorn main:app --reload

Every route except /health requires a Supabase access token
(Authorization: Bearer <token>). /docs and /redoc are disabled when ENV=production.
"""

import logging
import shutil
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from auth import require_viewer
from config import settings  # raises a clear RuntimeError if Supabase env vars are missing
from routes.alerts import router as alerts_router
from routes.cameras import router as cameras_router
from routes.detection import router as detection_router
from routes.evidence import router as evidence_router
from routes.reports import router as reports_router
from services.model_service import ModelUnavailableError, model_status
from services.privacy import start_retention_job, stop_retention_job
from services.stream_service import manager as stream_manager
from services.stream_service import start_enabled_cameras
from supabase_client import get_supabase

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("safevision")

MIN_FREE_DISK_MB = 500


@asynccontextmanager
async def lifespan(app: FastAPI):
    status = model_status()  # warm the models so the first request doesn't pay for it
    if status["loaded"]:
        log.info("Models loaded: %s", status["version"])
    else:
        log.warning("Models NOT loaded, detection endpoints will return 503: %s", status["error"])
    if settings.stream_autostart:
        try:
            start_enabled_cameras()
        except Exception:  # cameras table missing (migration 0003 not applied), DB down, ...
            log.exception("Could not start cameras")
    start_retention_job()  # deletes expired screenshots, originals and uploads (privacy.py)
    yield
    stop_retention_job()
    stream_manager.stop_all()  # closes open episodes and saves the final observations


docs_enabled = not settings.is_production
app = FastAPI(
    title="SafeVision AI Backend",
    version="1.1.0",
    lifespan=lifespan,
    docs_url="/docs" if docs_enabled else None,
    redoc_url="/redoc" if docs_enabled else None,
    openapi_url="/openapi.json" if docs_enabled else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,  # auth is a Bearer header, not cookies
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(detection_router)
app.include_router(evidence_router)
app.include_router(cameras_router)
app.include_router(alerts_router)
app.include_router(reports_router)


@app.exception_handler(ModelUnavailableError)
async def model_unavailable_handler(request: Request, exc: ModelUnavailableError):
    return JSONResponse(status_code=503, content={"detail": f"Detection model unavailable: {exc}"})


@app.get("/", dependencies=[Depends(require_viewer)])
def root():
    return {"message": "SafeVision AI backend is running", "status": "success"}


@app.get("/health")
def health():
    model = model_status()

    if settings.db_disabled:
        database = {"connected": True, "mode": "local"}
    else:
        try:
            get_supabase().table("violations").select("id").limit(1).execute()
            database = {"connected": True}
        except Exception as e:
            log.warning("Supabase health check failed: %s", e)
            database = {"connected": False, "error": type(e).__name__}

    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    free_mb = shutil.disk_usage(settings.upload_dir).free // (1024 * 1024)
    disk = {"free_mb": free_mb, "ok": free_mb >= MIN_FREE_DISK_MB}

    states = [stream_manager.status(cid)["state"] for cid in list(stream_manager.workers)]
    cameras = {"running": states.count("running"), "not_running": len(states) - states.count("running")}

    healthy = model["loaded"] and (database["connected"] or settings.db_disabled) and disk["ok"]
    return {
        "status": "ok" if healthy else "degraded",
        "backend": "active",
        "model": model,
        "database": database,
        "disk": disk,
        "cameras": cameras,  # started cameras that are streaming / connecting or failing
    }
