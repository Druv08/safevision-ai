from pathlib import Path
import cv2
import csv
import uuid
import time
from datetime import datetime

from services.model_service import get_model, get_helmet_model

PROJECT_ROOT = Path(__file__).resolve().parents[2]

OUTPUT_DIR = (
    PROJECT_ROOT
    / "ai-model"
    / "outputs"
    / "violations"
)

SCREENSHOT_DIR = OUTPUT_DIR / "screenshots"

CSV_PATH = OUTPUT_DIR / "violations_log.csv"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

COOLDOWN_SECONDS = 5

# v1 model (17-class construction-safety) class IDs
V1_HARDHAT_CLS = 4
V1_NO_HARDHAT_CLS = 6

# 5-class model class IDs for vest
VEST_CLS = 3
NO_VEST_CLS = 4


def save_violation(
    frame,
    source_name,
    frame_number,
    violation_type,
    severity,
    confidence
):
    timestamp = datetime.now().strftime(
        "%Y-%m-%d_%H-%M-%S"
    )

    violation_id = str(uuid.uuid4())[:8]

    screenshot_name = (
        f"{timestamp}_{violation_id}_{violation_type.replace(' ','_')}.jpg"
    )

    screenshot_path = (
        SCREENSHOT_DIR / screenshot_name
    )

    cv2.imwrite(
        str(screenshot_path),
        frame
    )

    with open(
        CSV_PATH,
        "a",
        newline=""
    ) as f:

        writer = csv.writer(f)

        writer.writerow([
            violation_id,
            timestamp,
            source_name,
            frame_number,
            violation_type,
            severity,
            round(confidence, 3),
            str(screenshot_path)
        ])


def detect_video(video_path):

    vest_model = get_model()
    h_model = get_helmet_model()

    cap = cv2.VideoCapture(video_path)

    total_violations = 0
    helmet_violations = 0
    vest_violations = 0

    frame_number = 0

    last_save = {
        "helmet": 0,
        "vest": 0
    }

    while True:

        success, frame = cap.read()

        if not success:
            break

        frame_number += 1

        vest_results = vest_model.predict(frame, conf=0.25, verbose=False)
        helmet_results = h_model.predict(frame, conf=0.25, verbose=False)

        current_time = time.time()

        no_helmet_boxes = []
        no_vest_boxes = []

        if helmet_results and helmet_results[0].boxes is not None:
            for box in helmet_results[0].boxes:
                cls_id = int(box.cls[0])
                conf = float(box.conf[0])
                if cls_id == V1_NO_HARDHAT_CLS:
                    no_helmet_boxes.append(conf)

        if vest_results and vest_results[0].boxes is not None:
            for box in vest_results[0].boxes:
                cls_id = int(box.cls[0])
                conf = float(box.conf[0])
                if cls_id == NO_VEST_CLS:
                    no_vest_boxes.append(conf)

        for conf in no_helmet_boxes:
            if current_time - last_save["helmet"] > COOLDOWN_SECONDS:
                helmet_violations += 1
                total_violations += 1
                save_violation(
                    frame,
                    Path(video_path).name,
                    frame_number,
                    "Helmet Missing",
                    "High",
                    conf
                )
                last_save["helmet"] = current_time

        for conf in no_vest_boxes:
            if current_time - last_save["vest"] > COOLDOWN_SECONDS:
                vest_violations += 1
                total_violations += 1
                save_violation(
                    frame,
                    Path(video_path).name,
                    frame_number,
                    "Safety Vest Missing",
                    "Medium",
                    conf
                )
                last_save["vest"] = current_time

    cap.release()

    return {
        "filename": Path(video_path).name,
        "status": "processed",
        "message": "Video analyzed successfully",
        "total_violations": total_violations,
        "helmet_violations": helmet_violations,
        "vest_violations": vest_violations
    }
