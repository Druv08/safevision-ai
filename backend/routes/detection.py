import threading
import time
import uuid
from collections import defaultdict, deque
from datetime import datetime
from pathlib import Path
from typing import Literal
from uuid import UUID

import cv2
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, Field

from auth import User, require_admin, require_viewer
from config import settings
from services.detection_service import detect_image
from services.model_service import model_status
from services.video_detection_service import VideoDecodeError, detect_video
from services.violations_service import (
    compliance_stats,
    count_by_type,
    list_violations,
    log_audit,
    set_status,
    to_api,
)

router = APIRouter()

# Allowed extension -> the container format its magic bytes must show.
IMAGE_TYPES = {".jpg": "jpeg", ".jpeg": "jpeg", ".png": "png"}
VIDEO_TYPES = {".mp4": "isobmff", ".mov": "isobmff", ".avi": "avi", ".webm": "ebml"}


def sniff(head: bytes) -> str | None:
    """Identify a file's real format from its first bytes."""
    if head.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if head.startswith(b"\x1a\x45\xdf\xa3"):
        return "ebml"  # Matroska / WebM
    if head[:4] == b"RIFF" and head[8:12] == b"AVI ":
        return "avi"
    if head[4:8] in (b"ftyp", b"moov", b"mdat", b"wide", b"free"):
        return "isobmff"  # MP4 / QuickTime
    return None


def save_upload(upload: UploadFile, allowed: dict[str, str]) -> Path:
    """Validate type, magic bytes and size; save under a server-generated name."""
    ext = Path(upload.filename or "").suffix.lower()
    if ext not in allowed:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Unsupported file type. Allowed: {', '.join(sorted(allowed))}",
        )
    head = upload.file.read(16)
    if sniff(head) != allowed[ext]:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "File content does not match its extension.")

    limit = settings.max_upload_mb * 1024 * 1024
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    path = settings.upload_dir / f"{uuid.uuid4().hex}{ext}"
    size = len(head)
    try:
        with path.open("wb") as out:
            out.write(head)
            while chunk := upload.file.read(1024 * 1024):
                size += len(chunk)
                if size > limit:
                    raise HTTPException(
                        status.HTTP_413_CONTENT_TOO_LARGE,
                        f"File is larger than {settings.max_upload_mb} MB.",
                    )
                out.write(chunk)
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return path


# ponytail: in-process sliding window, per worker; move to Redis if running several workers.
_recent_requests: dict[str, deque] = defaultdict(deque)
_rate_lock = threading.Lock()


def rate_limit(user: User = Depends(require_viewer)) -> User:
    now = time.monotonic()
    with _rate_lock:
        q = _recent_requests[user.id]
        while q and now - q[0] > 60:
            q.popleft()
        if len(q) >= settings.rate_limit_per_minute:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                "Too many detection requests; try again shortly.",
                headers={"Retry-After": "60"},
            )
        q.append(now)
    return user


# Detection routes are plain `def`, so FastAPI runs them (and the model
# inference inside) in its threadpool instead of on the event loop.

@router.post("/detect-image")
def detect_image_route(
    image: UploadFile = File(...),
    source: Literal["image", "camera"] = Form("image"),
    user: User = Depends(rate_limit),
):
    path = save_upload(image, IMAGE_TYPES)
    try:
        frame = cv2.imread(str(path))
        if frame is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Could not decode the image.")
        detections, summary = detect_image(frame, source)
    finally:
        path.unlink(missing_ok=True)

    return {"filename": image.filename, "detections": detections, "summary": summary}


@router.post("/detect-video")
def detect_video_route(
    video: UploadFile = File(...),
    source: Literal["video", "camera"] = Form("video"),
    user: User = Depends(rate_limit),
):
    path = save_upload(video, VIDEO_TYPES)
    try:
        result = detect_video(path, source)
    except VideoDecodeError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e)) from None
    finally:
        path.unlink(missing_ok=True)

    return {"filename": video.filename, **result}


@router.get("/violations")
def get_violations_route(
    type: Literal["no_helmet", "no_vest", "zone_intrusion"] | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = Query(None, description="Exclusive upper bound"),
    q: str | None = Query(None, max_length=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    status: Literal["new", "acknowledged", "action_taken", "closed"] | None = None,
    source: Literal["image", "video", "camera"] | None = None,
    sort: Literal["newest", "oldest"] = "newest",
    camera_id: UUID | None = None,
    zone_id: UUID | None = None,
    user: User = Depends(require_viewer),
):
    rows, total = list_violations(
        type, date_from, date_to, q, page, page_size, status, source, oldest=sort == "oldest",
        camera_id=camera_id and str(camera_id), zone_id=zone_id and str(zone_id),
    )
    return {
        "count": total,
        "page": page,
        "page_size": page_size,
        "violations": [to_api(r) for r in rows],
    }


class StatusUpdate(BaseModel):
    status: Literal["acknowledged", "action_taken", "closed"]
    note: str | None = Field(None, max_length=1000, description="Required for action_taken: what was done")
    cause: Literal["ppe_not_issued", "ppe_not_worn", "ppe_damaged", "false_detection", "other"] | None = None


@router.patch("/violations/{violation_id}")
def update_violation_status(violation_id: UUID, body: StatusUpdate, user: User = Depends(require_admin)):
    try:
        row = set_status(str(violation_id), body.status, user.id, body.note, body.cause)
    except ValueError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e)) from None
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Violation not found")
    # The note is overwritten by the next change, so the trail keeps every version.
    log_audit(user.id, body.status, str(violation_id), {"note": body.note, "cause": body.cause})
    return to_api(row)


@router.get("/dashboard-stats")
def dashboard_stats(user: User = Depends(require_viewer)):
    counts = count_by_type()
    return {
        "total_violations": sum(counts.values()),
        "no_vest_cases": counts["no_vest"],
        "no_helmet_cases": counts["no_helmet"],
        "zone_intrusion_cases": counts["zone_intrusion"],
        "system_status": "Active" if model_status()["loaded"] else "Model unavailable",
        # Per item: compliant / violation / unknown people and rate = compliant / (compliant + violation)
        "compliance": compliance_stats(),
    }
