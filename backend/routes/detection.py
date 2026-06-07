"""
routes/detection.py
-------------------
SafeVision AI - FastAPI routes for AI detection.

All endpoints live under the `/api` prefix and are mounted by
`backend/main.py`. The routes are intentionally thin: they handle
HTTP concerns (file upload, validation, status codes) and delegate
all the model work to `services.detection_service`.

Endpoints:
    GET  /api/model-status
    POST /api/detect-image      (multipart file upload)
    POST /api/detect-video      (multipart file upload)
    GET  /api/violations
"""

from __future__ import annotations

import shutil
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import (
    APIRouter,
    File,
    HTTPException,
    Query,
    UploadFile,
    status,
)

from services.detection_service import (
    read_violations_csv,
    run_image_detection,
    run_video_detection,
)
from services.model_service import (
    CLASS_NAMES,
    DEFAULT_MODEL_PATH,
    PROJECT_ROOT,
    get_model_status,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
ALLOWED_IMAGE_EXTS = {".jpg", ".jpeg", ".png"}
ALLOWED_VIDEO_EXTS = {".mp4", ".avi", ".mov", ".mkv"}

# Uploads land in backend/uploads/, which is gitignored.
UPLOADS_DIR = Path(__file__).resolve().parent.parent / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


router = APIRouter(prefix="/api", tags=["detection"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _ext_of(filename: str | None) -> str:
    """Return lower-case file extension including the dot, or empty string."""
    if not filename:
        return ""
    return Path(filename).suffix.lower()


def _safe_save_upload(upload: UploadFile, dest_dir: Path, allowed_exts: set[str]) -> Path:
    """Validate extension and persist an UploadFile to `dest_dir`.

    Filename is rewritten as `<utc-timestamp>_<uuid4-hex>_<ext>` so the
    original (untrusted) filename never lands on disk.

    Raises:
        HTTPException(400) on bad / missing extension.
        HTTPException(500) if writing the file fails.
    """
    ext = _ext_of(upload.filename)
    if ext not in allowed_exts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Unsupported file extension '{ext or '(none)'}'. "
                f"Allowed: {sorted(allowed_exts)}"
            ),
        )

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    safe_name = f"{ts}_{uuid.uuid4().hex}{ext}"
    dest = dest_dir / safe_name

    try:
        with dest.open("wb") as out:
            shutil.copyfileobj(upload.file, out)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save uploaded file: {exc}",
        ) from exc
    finally:
        upload.file.close()

    return dest


# ---------------------------------------------------------------------------
# 1. GET /api/model-status
# ---------------------------------------------------------------------------
@router.get("/model-status")
def model_status() -> dict:
    """Report whether the YOLO model is loaded and where it lives."""
    s = get_model_status()
    return {
        "model_loaded": s["model_loaded"],
        "model_path": s["model_path"],
        "class_names": CLASS_NAMES,
        "message": s["message"],
    }


# ---------------------------------------------------------------------------
# 2. POST /api/detect-image
# ---------------------------------------------------------------------------
@router.post("/detect-image")
def detect_image(
    file: UploadFile = File(...),
    conf: float = Query(0.4, ge=0.0, le=1.0, description="Confidence threshold"),
) -> dict:
    """Run YOLO PPE detection on a single uploaded image.

    Form field name: `file`.
    Accepted extensions: .jpg, .jpeg, .png.
    """
    saved_path = _safe_save_upload(file, UPLOADS_DIR, ALLOWED_IMAGE_EXTS)

    result = run_image_detection(saved_path, conf=conf)
    if not result.get("ok", False):
        # Surface model / inference errors as 503 so the client knows it's
        # a server-side dependency problem, not bad input.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=result,
        )

    return {
        "filename": file.filename,
        "saved_as": saved_path.name,
        "conf": conf,
        "detections": result.get("detections", []),
        "violation_count": result.get("violation_count", 0),
        "violations": result.get("violations", []),
    }


# ---------------------------------------------------------------------------
# 3. POST /api/detect-video
# ---------------------------------------------------------------------------
@router.post("/detect-video")
def detect_video(
    file: UploadFile = File(...),
    conf: float = Query(0.4, ge=0.0, le=1.0, description="Confidence threshold"),
    frame_skip: int = Query(
        10, ge=1, le=300,
        description="Process 1 out of every N frames (default 10)",
    ),
) -> dict:
    """Run sampled YOLO PPE detection on an uploaded video.

    Form field name: `file`.
    Accepted extensions: .mp4, .avi, .mov, .mkv.

    For Day 7 we do NOT save an annotated video; this endpoint just
    samples frames and returns aggregate counts.
    """
    saved_path = _safe_save_upload(file, UPLOADS_DIR, ALLOWED_VIDEO_EXTS)

    result = run_video_detection(
        saved_path, conf=conf, frame_skip=frame_skip
    )
    if not result.get("ok", False):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=result,
        )

    return {
        "filename": file.filename,
        "saved_as": saved_path.name,
        "conf": conf,
        "frame_skip": frame_skip,
        "total_frames": result.get("total_frames", 0),
        "processed_frames": result.get("processed_frames", 0),
        "detections_by_class": result.get("detections_by_class", {}),
        "violations_by_type": result.get("violations_by_type", {}),
        "status": result.get("status", "ok"),
    }


# ---------------------------------------------------------------------------
# 4. GET /api/violations
# ---------------------------------------------------------------------------
@router.get("/violations")
def violations() -> dict:
    """Return rows from the local violations CSV (if it exists)."""
    return read_violations_csv()
