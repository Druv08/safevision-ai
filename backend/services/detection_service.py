"""
services/detection_service.py
-----------------------------
SafeVision AI - detection helpers used by the HTTP routes.

This module is the thin bridge between the FastAPI endpoints and the
YOLO model. It does NOT know about HTTP. Each function takes a local
file path (already saved by the route) and returns plain Python dicts
that FastAPI can serialize to JSON.

Functions:
    run_image_detection(image_path, conf)
    run_video_detection(video_path, conf, frame_skip)
    read_violations_csv()

Violation rule mapping (mirrors the local violation_detection.py tool):
    no_vest               -> Safety Vest Missing    (Medium)
    no_helmet             -> Helmet Missing         (High)
    no_vest AND no_helmet -> Multiple PPE Missing   (Critical)

For Day 7 we do NOT save annotated videos from the backend; the video
endpoint just samples frames and returns counts so the endpoint stays
lightweight.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from services.model_service import (
    CLASS_NAMES,
    PROJECT_ROOT,
    get_model,
    get_model_status,
)


# ---------------------------------------------------------------------------
# Violation rule table
# ---------------------------------------------------------------------------
# Per-class metadata for "single PPE violation" detections.
_VIOLATION_META = {
    "no_vest":   {"violation_type": "Safety Vest Missing", "severity": "Medium"},
    "no_helmet": {"violation_type": "Helmet Missing",      "severity": "High"},
}

VIOLATIONS_CSV = (
    PROJECT_ROOT / "ai-model" / "outputs" / "violations" / "violations_log.csv"
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
def _model_not_available_response(extra: dict | None = None) -> dict:
    """Build a uniform "model missing" payload for endpoints to return."""
    status = get_model_status()
    payload = {
        "ok": False,
        "error": "model_not_available",
        "message": status.get("message", "Model not loaded"),
        "model_path": status.get("model_path"),
    }
    if extra:
        payload.update(extra)
    return payload


def _ultralytics_result_to_detections(result: Any) -> list[dict]:
    """Convert one ultralytics Results object to a list of dicts.

    Each dict has: class_id, class_name, confidence, bbox [x1,y1,x2,y2],
    and (only for no_vest / no_helmet) violation_type + severity.
    """
    detections: list[dict] = []
    if result is None or result.boxes is None or len(result.boxes) == 0:
        return detections

    xyxy   = result.boxes.xyxy.cpu().numpy()
    confs  = result.boxes.conf.cpu().numpy()
    clsids = result.boxes.cls.cpu().numpy().astype(int)

    for (x1, y1, x2, y2), conf, cls_id in zip(xyxy, confs, clsids):
        name = CLASS_NAMES.get(int(cls_id), f"class_{int(cls_id)}")
        det: dict = {
            "class_id":   int(cls_id),
            "class_name": name,
            "confidence": float(conf),
            "bbox": [float(x1), float(y1), float(x2), float(y2)],
        }
        meta = _VIOLATION_META.get(name)
        if meta is not None:
            det["violation_type"] = meta["violation_type"]
            det["severity"]       = meta["severity"]
        detections.append(det)

    return detections


def _summarize_violations(detections: list[dict]) -> tuple[list[dict], int]:
    """Build the violations list for an image-level response.

    Rule:
        - If both `no_vest` and `no_helmet` are present anywhere in the
          frame, emit ONE 'Multiple PPE Missing' event (Critical) using
          the higher of the two top confidences.
        - Otherwise, emit per-class events for whichever of no_vest /
          no_helmet are present, using each class's top confidence.
    """
    no_vest = [d for d in detections if d["class_name"] == "no_vest"]
    no_hel  = [d for d in detections if d["class_name"] == "no_helmet"]

    events: list[dict] = []
    if no_vest and no_hel:
        top = max(
            max(d["confidence"] for d in no_vest),
            max(d["confidence"] for d in no_hel),
        )
        events.append({
            "violation_type": "Multiple PPE Missing",
            "severity":       "Critical",
            "confidence":     float(top),
        })
    else:
        if no_vest:
            events.append({
                "violation_type": "Safety Vest Missing",
                "severity":       "Medium",
                "confidence":     float(max(d["confidence"] for d in no_vest)),
            })
        if no_hel:
            events.append({
                "violation_type": "Helmet Missing",
                "severity":       "High",
                "confidence":     float(max(d["confidence"] for d in no_hel)),
            })

    return events, len(events)


# ---------------------------------------------------------------------------
# 1. Image detection
# ---------------------------------------------------------------------------
def run_image_detection(image_path: str | Path, conf: float = 0.4) -> dict:
    """Run YOLO on a single image and return a JSON-friendly result dict.

    Args:
        image_path: Local path to a .jpg / .jpeg / .png file already
            saved by the route.
        conf: Per-detection confidence threshold (default 0.4).

    Returns dict keys:
        ok            -> True / False
        detections    -> list of detection dicts (see above)
        violation_count -> int
        violations    -> list of violation event dicts
        error / message -> only on failure
    """
    model = get_model()
    if model is None:
        return _model_not_available_response()

    image_path = Path(image_path)
    if not image_path.exists():
        return {
            "ok": False,
            "error": "file_not_found",
            "message": f"Image not found: {image_path}",
        }

    try:
        results = model.predict(
            source=str(image_path),
            conf=float(conf),
            verbose=False,
        )
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "error": "inference_failed",
            "message": f"YOLO prediction failed: {exc}",
        }

    if not results:
        return {
            "ok": True,
            "detections": [],
            "violation_count": 0,
            "violations": [],
        }

    detections = _ultralytics_result_to_detections(results[0])
    violations, count = _summarize_violations(detections)
    return {
        "ok": True,
        "detections": detections,
        "violation_count": count,
        "violations": violations,
    }


# ---------------------------------------------------------------------------
# 2. Video detection (sampled, lightweight)
# ---------------------------------------------------------------------------
def run_video_detection(
    video_path: str | Path,
    conf: float = 0.4,
    frame_skip: int = 10,
) -> dict:
    """Run YOLO on a sampled subset of frames from a local video file.

    For Day 7 we keep this endpoint lightweight: we process every
    Nth frame (default every 10th) and return aggregate counts only.
    No annotated video is written.

    Args:
        video_path: Local path to .mp4 / .avi / .mov / .mkv.
        conf:       Per-detection confidence threshold (default 0.4).
        frame_skip: Process 1 frame out of every `frame_skip` frames.
                    Must be >= 1. Higher value = faster, fewer samples.

    Returns dict keys:
        ok                  -> True / False
        total_frames        -> int  (as reported by OpenCV; may be 0
                                     for some webcams / streams)
        processed_frames    -> int
        detections_by_class -> { class_name: count_across_sampled_frames }
        violations_by_type  -> { violation_type: count_across_sampled_frames }
        status              -> short human-readable status string
        error / message     -> only on failure
    """
    # Validate frame_skip up-front.
    try:
        frame_skip = int(frame_skip)
    except (TypeError, ValueError):
        frame_skip = 10
    if frame_skip < 1:
        frame_skip = 1

    model = get_model()
    if model is None:
        return _model_not_available_response({
            "total_frames": 0,
            "processed_frames": 0,
            "detections_by_class": {},
            "violations_by_type": {},
            "status": "model_not_available",
        })

    video_path = Path(video_path)
    if not video_path.exists():
        return {
            "ok": False,
            "error": "file_not_found",
            "message": f"Video not found: {video_path}",
            "status": "file_not_found",
        }

    # Import cv2 lazily so simply importing this module does not require it.
    try:
        import cv2  # type: ignore
    except ImportError as exc:
        return {
            "ok": False,
            "error": "opencv_missing",
            "message": f"opencv-python is required but failed to import: {exc}",
            "status": "opencv_missing",
        }

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return {
            "ok": False,
            "error": "video_open_failed",
            "message": f"OpenCV could not open video: {video_path}",
            "status": "video_open_failed",
        }

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)

    detections_by_class: dict[str, int] = {name: 0 for name in CLASS_NAMES.values()}
    violations_by_type: dict[str, int] = {
        "Safety Vest Missing":  0,
        "Helmet Missing":       0,
        "Multiple PPE Missing": 0,
    }

    processed = 0
    frame_idx = 0
    status_msg = "ok"

    try:
        while True:
            ok, frame = cap.read()
            if not ok or frame is None:
                break

            if frame_idx % frame_skip == 0:
                processed += 1
                try:
                    results = model.predict(
                        source=frame,
                        conf=float(conf),
                        verbose=False,
                    )
                    dets = _ultralytics_result_to_detections(results[0]) if results else []
                except Exception as exc:  # noqa: BLE001
                    # Don't crash the whole loop on a single bad frame.
                    status_msg = f"warning: inference failed on frame {frame_idx}: {exc}"
                    dets = []

                # Per-class counts (each detection counts once).
                for d in dets:
                    cname = d["class_name"]
                    if cname in detections_by_class:
                        detections_by_class[cname] += 1

                # Per-frame violation summary (consistent with image rule).
                events, _ = _summarize_violations(dets)
                for ev in events:
                    vtype = ev["violation_type"]
                    if vtype in violations_by_type:
                        violations_by_type[vtype] += 1

            frame_idx += 1
    finally:
        cap.release()

    return {
        "ok": True,
        "total_frames": total_frames,
        "processed_frames": processed,
        "detections_by_class": detections_by_class,
        "violations_by_type": violations_by_type,
        "status": status_msg,
    }


# ---------------------------------------------------------------------------
# 3. Read local violations CSV
# ---------------------------------------------------------------------------
def read_violations_csv() -> dict:
    """Read the local violations CSV produced by violation_detection.py.

    Returns dict keys:
        ok        -> True
        records   -> list of dicts (one per CSV row), [] if file missing
        count     -> int
        csv_path  -> absolute path string
        message   -> short human-readable status string
    """
    if not VIOLATIONS_CSV.exists():
        return {
            "ok": True,
            "records": [],
            "count": 0,
            "csv_path": str(VIOLATIONS_CSV),
            "message": (
                "Violations CSV does not exist yet. Run "
                "ai-model/inference/violation_detection.py locally to "
                "produce it."
            ),
        }

    records: list[dict] = []
    try:
        with VIOLATIONS_CSV.open("r", encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                records.append(dict(row))
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "error": "csv_read_failed",
            "message": f"Failed to read CSV: {exc}",
            "csv_path": str(VIOLATIONS_CSV),
            "records": [],
            "count": 0,
        }

    return {
        "ok": True,
        "records": records,
        "count": len(records),
        "csv_path": str(VIOLATIONS_CSV),
        "message": f"Loaded {len(records)} violation row(s).",
    }
