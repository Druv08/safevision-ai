from pathlib import Path
import shutil
from collections import Counter

from fastapi import APIRouter, UploadFile, File

from services.detection_service import detect_image
from services.violations_service import get_violations
from services.video_detection_service import detect_video

router = APIRouter()

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


# -----------------------------
# IMAGE DETECTION
# -----------------------------
@router.post("/detect-image")
async def detect_image_route(
    image: UploadFile = File(...)
):
    file_path = UPLOAD_DIR / image.filename

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(image.file, buffer)

    detections = detect_image(str(file_path))

    return {
        "filename": image.filename,
        "detections": detections
    }


# -----------------------------
# VIDEO DETECTION
# -----------------------------
@router.post("/detect-video")
async def detect_video_route(
    video: UploadFile = File(...)
):
    file_path = UPLOAD_DIR / video.filename

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(video.file, buffer)

    result = detect_video(str(file_path))

    return result


# -----------------------------
# VIOLATIONS LIST
# -----------------------------
@router.get("/violations")
def get_violations_route():

    violations = get_violations()

    return {
        "count": len(violations),
        "violations": violations
    }


# -----------------------------
# DASHBOARD STATS
# -----------------------------
@router.get("/dashboard-stats")
def dashboard_stats():

    violations = get_violations()

    total_violations = len(violations)

    violation_types = [
        v["violation_type"]
        for v in violations
    ]

    counter = Counter(violation_types)

    no_vest_cases = counter.get(
        "Safety Vest Missing",
        0
    )

    no_helmet_cases = counter.get(
        "Helmet Missing",
        0
    )

    return {
        "total_violations": total_violations,
        "no_vest_cases": no_vest_cases,
        "no_helmet_cases": no_helmet_cases,
        "system_status": "Active"
    }