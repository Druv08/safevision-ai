"""
SafeVision AI - Day 6
Local PPE violation detection with screenshots + CSV logging.

This script runs the SAME live PPE + worker detection used in
video_detection.py, but adds:

  * Violation rules     -> turn raw detections (no_vest / no_helmet) into
                           human-readable violation events with severity.
  * Cooldown            -> stop the same violation from being saved every
                           single frame; only save once per cooldown window.
  * Screenshot evidence -> save the annotated frame (boxes + HUD already
                           drawn) when a violation fires.
  * CSV log             -> append one row per saved violation to a local
                           CSV file so the events can be audited later.

How the two models are used (beginner explanation):

  PPE model (SafeVision-trained, 5 classes):
      Detects safety equipment + violations directly. We trust:
        - vest      / no_vest      (very strong on the v2 model)
        - helmet    / no_helmet    (weaker; treated as experimental)

  Worker/person model (COCO yolov8n.pt):
      Counts real workers in the scene. We use the SAME box detector +
      sanity filter (size + aspect ratio) as the original Day 5 build,
      NOT the newer pose model. This is intentional: spec says "do not
      switch to pose model yet" for the violation script.

  Violation logic + cooldown:
      Every frame we look at what the PPE model just produced.
      If no_vest was seen        -> Safety Vest Missing  (Medium)
      If no_helmet was seen      -> Helmet Missing       (High, experimental)
      If BOTH in the same frame  -> Multiple PPE Missing (Critical)
      Each violation type has its own cooldown timer so we don't spam the
      screenshots/CSV with hundreds of near-identical events per second.

Usage:
    # Webcam (default)
    python ai-model/inference/violation_detection.py

    # Custom thresholds + cooldown + save annotated video
    python ai-model/inference/violation_detection.py --conf 0.4 --person-conf 0.7 --cooldown 5 --save-video

    # Video file
    python ai-model/inference/violation_detection.py --source path/to/video.mp4

Press 'q' in the window (or close the window) to quit.

SafeVision PPE classes (v2 model):
    0 = person      (weak - NOT used for worker count)
    1 = helmet
    2 = no_helmet
    3 = vest
    4 = no_vest
"""

import argparse
import csv
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_MODEL = (
    PROJECT_ROOT
    / "ai-model"
    / "outputs"
    / "training-runs"
    / "safevision_yolov8n_5class_v2"
    / "weights"
    / "best.pt"
)

# Where we drop violation evidence
VIOLATIONS_DIR  = PROJECT_ROOT / "ai-model" / "outputs" / "violations"
SCREENSHOTS_DIR = VIOLATIONS_DIR / "screenshots"
CSV_LOG_PATH    = VIOLATIONS_DIR / "violations_log.csv"

# Where annotated output videos go (same folder as Day 5)
VIDEO_OUT_DIR = PROJECT_ROOT / "ai-model" / "outputs" / "video-detections"


def _find_default_person_model() -> str:
    """Locate a local copy of yolov8n.pt; fall back to the bare name.

    Ultralytics will auto-download `yolov8n.pt` on first use if no file is
    found locally, so returning the bare name is always a safe fallback.
    """
    candidates = [
        PROJECT_ROOT / "yolov8n.pt",            # repo root
        PROJECT_ROOT.parent / "yolov8n.pt",     # parent folder
        Path.cwd() / "yolov8n.pt",
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    return "yolov8n.pt"


DEFAULT_PERSON_MODEL = _find_default_person_model()

# COCO class id for `person`
COCO_PERSON_CLASS_ID = 0

# Class names + colors for the PPE model (BGR, OpenCV convention)
CLASS_NAMES = {
    0: "person",
    1: "helmet",
    2: "no_helmet",
    3: "vest",
    4: "no_vest",
}
GREEN = (0, 200, 0)
RED   = (0, 0, 255)
CYAN  = (255, 200, 0)

CLASS_COLORS = {
    0: CYAN,    # person (rarely used here)
    1: GREEN,   # helmet
    2: RED,     # no_helmet
    3: GREEN,   # vest
    4: RED,     # no_vest
}

WORKER_BOX_COLOR = CYAN

# Violation type -> (severity, screenshot filename prefix)
# Keep the prefixes short and filesystem-safe.
VIOLATION_META = {
    "Safety Vest Missing":  ("Medium",   "no_vest"),
    "Helmet Missing":       ("High",     "no_helmet"),
    "Multiple PPE Missing": ("Critical", "multiple_ppe_missing"),
}

# Columns for the CSV log (order matters; written once as header).
CSV_COLUMNS = [
    "violation_id",
    "timestamp",
    "source",
    "frame_number",
    "violation_type",
    "severity",
    "confidence",
    "worker_detected",
    "screenshot_path",
]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="SafeVision AI - local PPE violation detection (Day 6)"
    )
    parser.add_argument(
        "--source",
        default="0",
        help="Video source: '0' for webcam (default) or path to a video file",
    )
    parser.add_argument(
        "--conf",
        type=float,
        default=0.4,
        help="PPE-model confidence threshold (default: 0.4)",
    )
    parser.add_argument(
        "--person-conf",
        type=float,
        default=0.7,
        help="Worker/person confidence threshold (default: 0.7)",
    )
    parser.add_argument(
        "--cooldown",
        type=float,
        default=5.0,
        help="Per-violation cooldown in seconds (default: 5)",
    )
    parser.add_argument(
        "--clear-after",
        type=float,
        default=2.0,
        help=(
            "Seconds a violation type must be absent before it can fire "
            "again as a NEW event (default: 2). Together with the cooldown, "
            "this is what stops a continuously-visible no_vest from being "
            "counted every 5 seconds."
        ),
    )
    parser.add_argument(
        "--worker-overlap",
        type=float,
        default=0.3,
        help=(
            "Minimum fraction of a PPE-violation box (no_vest / no_helmet) "
            "that must lie inside a worker box before the violation is "
            "saved (default: 0.3 = 30%%). Detections with no worker match "
            "are still drawn on screen, but are NOT screenshot/logged. "
            "This stops loose clothing or standalone vests from being "
            "counted as worker violations."
        ),
    )
    parser.add_argument(
        "--strict-vest-matching",
        action="store_true",
        help=(
            "OPT-IN: also flag a worker as no_vest when no vest is WORN on "
            "their torso (catches the 'held vest' case). Experimental and "
            "unstable on side views / face-area boxes, so it is OFF by "
            "default. When off, only the model's own no_vest class (gated by "
            "worker overlap) is used -- the stable Day 6.5 behaviour."
        ),
    )
    parser.add_argument(
        "--vest-overlap",
        type=float,
        default=0.40,
        help=(
            "Minimum overlap between a vest box and a worker's torso/chest "
            "region before the vest counts as WORN (default: 0.40). Only used "
            "when --strict-vest-matching is enabled. A worker with no vest "
            "worn on their torso is then treated as no_vest even if the model "
            "only emitted a `vest` box (the 'held vest' case)."
        ),
    )
    parser.add_argument(
        "--show-torso",
        action="store_true",
        help=(
            "Debug: draw the computed torso/chest region for each worker so "
            "the worn-vest matching can be tuned live. Off by default."
        ),
    )
    parser.add_argument(
        "--save-video",
        action="store_true",
        help="If set, also save the annotated output video to ai-model/outputs/video-detections/",
    )
    parser.add_argument(
        "--model",
        default=str(DEFAULT_MODEL),
        help="Path to SafeVision PPE YOLO weights (default: v2 best.pt)",
    )
    parser.add_argument(
        "--person-model",
        default=DEFAULT_PERSON_MODEL,
        help="Path to COCO YOLOv8 weights for person detection (default: yolov8n.pt)",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Duplicate-box filtering (per PPE class)
# ---------------------------------------------------------------------------
def calculate_iou(box_a, box_b) -> float:
    """Intersection-over-Union between two [x1, y1, x2, y2] boxes.

    IoU is just "how much do these two rectangles overlap?", expressed
    as a number between 0.0 (no overlap) and 1.0 (identical box).
    We use it to decide whether two boxes of the SAME class are really
    pointing at the same thing in the frame.
    """
    ax1, ay1, ax2, ay2 = box_a
    bx1, by1, bx2, by2 = box_b

    # Intersection rectangle
    ix1 = max(ax1, bx1)
    iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)

    iw = max(0.0, ix2 - ix1)
    ih = max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0.0:
        return 0.0

    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter
    if union <= 0.0:
        return 0.0
    return float(inter / union)


def filter_duplicate_boxes(detections, iou_threshold: float = 0.5):
    """Drop overlapping duplicate PPE boxes of the SAME class.

    Why this exists:
        Sometimes the PPE model fires more than one box for the same
        region of the same worker (e.g. three overlapping `no_vest`
        boxes on one chest). That makes the `no_vest` count look like 3
        and inflates violation logging. This is a per-class
        beginner-friendly NMS (non-max suppression):

          1. Group detections by class_name.
          2. Sort each group by confidence (highest first).
          3. Walk the sorted list: keep the top box, then drop any
             remaining box of the SAME class whose IoU with the kept
             box is > iou_threshold.
          4. Repeat with the next-highest box that survived.

    Input  : list of dicts, each with keys {class_name, confidence, bbox}.
             `bbox` is [x1, y1, x2, y2] in pixel coords.
    Output : a new list of dicts (same shape), with duplicates removed.

    Note: we ONLY filter within the same class_name. A `vest` and a
    `no_vest` box that overlap heavily are still both kept, because they
    are different decisions about the same region and that disagreement
    is information the violation logic can use.
    """
    if not detections:
        return []

    # 1. Group by class_name
    by_class: dict = {}
    for det in detections:
        by_class.setdefault(det["class_name"], []).append(det)

    kept_all = []

    # 2 + 3. Per-class greedy NMS
    for class_name, group in by_class.items():
        # Sort highest-confidence first
        group_sorted = sorted(
            group, key=lambda d: d["confidence"], reverse=True
        )

        kept: list = []
        for det in group_sorted:
            is_duplicate = False
            for k in kept:
                if calculate_iou(det["bbox"], k["bbox"]) > iou_threshold:
                    is_duplicate = True
                    break
            if not is_duplicate:
                kept.append(det)

        kept_all.extend(kept)

    return kept_all


# ---------------------------------------------------------------------------
# Detection helpers (PPE)
# ---------------------------------------------------------------------------
def extract_ppe_detections(result):
    """Turn an Ultralytics result into a flat list of detection dicts.

    Output shape: [{"class_name": str, "confidence": float,
                    "bbox": [x1, y1, x2, y2]}, ...]
    The list is what `filter_duplicate_boxes` and `draw_ppe_detections`
    both consume, so the dataflow is:

        result -> extract -> filter_duplicate_boxes -> draw + count
    """
    out = []
    if result.boxes is None or len(result.boxes) == 0:
        return out

    boxes   = result.boxes.xyxy.cpu().numpy()
    confs   = result.boxes.conf.cpu().numpy()
    cls_ids = result.boxes.cls.cpu().numpy().astype(int)

    for (x1, y1, x2, y2), conf, cls_id in zip(boxes, confs, cls_ids):
        name = CLASS_NAMES.get(int(cls_id), f"id_{cls_id}")
        out.append({
            "class_name": name,
            "confidence": float(conf),
            "bbox": [float(x1), float(y1), float(x2), float(y2)],
        })
    return out


def draw_ppe_detections(frame, detections, frame_counts: dict, max_confs: dict) -> None:
    """Draw PPE boxes + labels from an ALREADY-FILTERED detection list.

    `detections`         -> list of dicts produced by
                            `filter_duplicate_boxes(extract_ppe_detections(result))`.
    `frame_counts[name]` -> number of detections of class `name` left in
                            this frame AFTER duplicate filtering.
    `max_confs[name]`    -> highest confidence seen for class `name` this
                            frame (used when logging a violation so the
                            CSV carries a meaningful confidence number).
    """
    if not detections:
        return

    for det in detections:
        name = det["class_name"]
        conf = det["confidence"]
        x1, y1, x2, y2 = det["bbox"]
        color = CLASS_COLORS.get(
            next((cid for cid, n in CLASS_NAMES.items() if n == name), -1),
            (255, 255, 255),
        )

        cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), color, 2)

        label = f"{name} {conf:.2f}"
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        cv2.rectangle(
            frame,
            (int(x1), int(y1) - th - 6),
            (int(x1) + tw + 4, int(y1)),
            color,
            -1,
        )
        cv2.putText(
            frame, label, (int(x1) + 2, int(y1) - 4),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA,
        )

        frame_counts[name] = frame_counts.get(name, 0) + 1
        if conf > max_confs.get(name, 0.0):
            max_confs[name] = float(conf)


# ---------------------------------------------------------------------------
# Detection helpers (worker / COCO person box + filter)
# ---------------------------------------------------------------------------
def filter_worker_boxes(
    boxes, confs, frame_width, frame_height,
    min_conf: float,
    min_area_frac: float = 0.03,
    ar_min: float = 0.2,
    ar_max: float = 1.2,
):
    """Reject obviously-bad COCO person boxes before counting them.

    Same beginner-friendly filter used in Day 5 video_detection.py:
      1. confidence >= min_conf
      2. box area >= 3% of frame area (drop tiny boxes)
      3. aspect ratio (w/h) in [0.2, 1.2] (drop ultra-wide / ultra-thin)

    Returns two parallel numpy arrays (boxes, confs) that survived.
    """
    if len(boxes) == 0:
        return boxes, confs

    frame_area = float(frame_width * frame_height)
    min_area = min_area_frac * frame_area

    keep = []
    for i, ((x1, y1, x2, y2), c) in enumerate(zip(boxes, confs)):
        if c < min_conf:
            continue
        w = float(x2 - x1)
        h = float(y2 - y1)
        if w <= 0 or h <= 0:
            continue
        if (w * h) < min_area:
            continue
        ar = w / h
        if ar < ar_min or ar > ar_max:
            continue
        keep.append(i)

    if not keep:
        return (
            np.zeros((0, 4), dtype=boxes.dtype),
            np.zeros((0,),   dtype=confs.dtype),
        )

    idx = np.array(keep, dtype=int)
    return boxes[idx], confs[idx]


def draw_worker_boxes(frame, result, person_conf: float):
    """Draw 'worker' boxes for COCO person detections.

    Returns:
        (n_workers, worker_boxes) where:
          - n_workers is the count of worker boxes drawn
          - worker_boxes is a list of [x1, y1, x2, y2] floats for every
            drawn worker. This is what the violation logic consumes when
            deciding whether a no_vest / no_helmet box overlaps a real
            person.

    Worker boxes are cyan to stay distinct from the green/red PPE boxes.
    """
    if result.boxes is None or len(result.boxes) == 0:
        return 0, []

    boxes   = result.boxes.xyxy.cpu().numpy()
    confs   = result.boxes.conf.cpu().numpy()
    cls_ids = result.boxes.cls.cpu().numpy().astype(int)

    mask = cls_ids == COCO_PERSON_CLASS_ID
    boxes, confs = boxes[mask], confs[mask]
    if len(boxes) == 0:
        return 0, []

    h_img, w_img = frame.shape[:2]
    boxes, confs = filter_worker_boxes(
        boxes, confs, w_img, h_img, min_conf=person_conf
    )

    n_workers = 0
    worker_boxes = []
    for (x1, y1, x2, y2), conf in zip(boxes, confs):
        n_workers += 1
        worker_boxes.append([float(x1), float(y1), float(x2), float(y2)])

        cv2.rectangle(
            frame, (int(x1), int(y1)), (int(x2), int(y2)),
            WORKER_BOX_COLOR, 2,
        )
        label = f"worker {conf:.2f}"
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        cv2.rectangle(
            frame,
            (int(x1), int(y1) - th - 6),
            (int(x1) + tw + 4, int(y1)),
            WORKER_BOX_COLOR, -1,
        )
        cv2.putText(
            frame, label, (int(x1) + 2, int(y1) - 4),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA,
        )

    return n_workers, worker_boxes


# ---------------------------------------------------------------------------
# Worker <-> PPE matching (Day 6.5)
# ---------------------------------------------------------------------------
def calculate_overlap_ratio(inner_box, outer_box) -> float:
    """How much of `inner_box` lies inside `outer_box`?

    This is NOT IoU. It is intersection / area(inner_box), so it answers
    the very specific question: "what fraction of this PPE box is
    actually inside this worker box?"

    Returns a value in [0.0, 1.0]:
      0.0 -> the PPE box does not touch the worker box at all
      1.0 -> the PPE box is fully contained inside the worker box

    We use this (not IoU) on purpose: a `no_vest` box that sits on a
    worker's chest is small relative to the worker's full-body box, so
    their IoU is naturally low. Overlap-ratio captures the real signal
    we care about ("is this PPE box ON this worker?").
    """
    ax1, ay1, ax2, ay2 = inner_box
    bx1, by1, bx2, by2 = outer_box

    # Intersection rectangle
    ix1 = max(ax1, bx1)
    iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)

    iw = max(0.0, ix2 - ix1)
    ih = max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0.0:
        return 0.0

    inner_area = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    if inner_area <= 0.0:
        return 0.0
    return float(inter / inner_area)


def ppe_matches_worker(ppe_box, worker_boxes, overlap_threshold: float = 0.3) -> bool:
    """Return True if `ppe_box` overlaps ANY worker box by >= threshold.

    "Overlap" here is `calculate_overlap_ratio(ppe_box, worker_box)`,
    i.e. the fraction of the PPE box that lies inside the worker box.

    Why this exists (beginner explanation):
        A PPE-only detection (e.g. a `no_vest` box) is NOT a worker
        violation by itself. It might be a shirt on a hanger, a poster,
        or a piece of clothing on a chair. To call it a worker violation
        we also need a real worker (from the COCO person detector) AND
        we need the PPE box to actually be ON that worker. This
        helper is the second half of that check.

    Args:
        ppe_box: [x1, y1, x2, y2] for the PPE-violation detection.
        worker_boxes: list of [x1, y1, x2, y2] for all worker boxes
            in the current frame.
        overlap_threshold: minimum overlap-ratio (default 0.3 = 30%).

    Returns:
        True if any worker box has overlap-ratio >= threshold.
    """
    if not worker_boxes:
        return False
    for wb in worker_boxes:
        if calculate_overlap_ratio(ppe_box, wb) >= overlap_threshold:
            return True
    return False


# ---------------------------------------------------------------------------
# Torso-based worn-vest check (Day 8)
# ---------------------------------------------------------------------------
# The model's `no_vest` class does NOT cover the "worker is HOLDING a vest"
# case: it sees a vest-shaped object and stays quiet, so the worker looks
# compliant. These helpers decide whether a vest is actually being WORN by
# checking it against the worker's torso/chest region (not the whole body).
TORSO_X_INSET = 0.15   # drop 15% of width on each side
TORSO_Y_TOP   = 0.20   # torso starts 20% down from the top of the worker box
TORSO_Y_BOT   = 0.65   # torso ends 65% down (chest band, not legs)
TORSO_NEAR_MARGIN = 0.15  # sides/bottom tolerance only (never above chest top)
MIN_VEST_IN_WORKER = 0.60  # >=60% of vest area must lie inside the worker box


def get_worker_torso_box(worker_box):
    """Approximate the chest/upper-body region inside a worker box.

    Returns the torso box [x1, y1, x2, y2]:
        x1 = worker_x1 + 15% width      x2 = worker_x2 - 15% width
        y1 = worker_y1 + 20% height     y2 = worker_y1 + 65% height
    """
    x1, y1, x2, y2 = worker_box
    w = x2 - x1
    h = y2 - y1
    tx1 = x1 + TORSO_X_INSET * w
    tx2 = x2 - TORSO_X_INSET * w
    ty1 = y1 + TORSO_Y_TOP * h
    ty2 = y1 + TORSO_Y_BOT * h
    return [tx1, ty1, tx2, ty2]


def box_center_inside(box, region, margin: float = 0.0) -> bool:
    """Is the centre of `box` inside `region` (optionally expanded by margin)?"""
    cx = (box[0] + box[2]) / 2.0
    cy = (box[1] + box[3]) / 2.0
    rx1, ry1, rx2, ry2 = region
    if margin:
        rw = rx2 - rx1
        rh = ry2 - ry1
        rx1 -= rw * margin
        rx2 += rw * margin
        ry1 -= rh * margin
        ry2 += rh * margin
    return (rx1 <= cx <= rx2) and (ry1 <= cy <= ry2)


def vest_matches_worker_torso(
    vest_box, worker_box, torso_box, overlap_threshold: float = 0.40
) -> bool:
    """True only if a vest box is being WORN on a worker's torso.

    Strict rule -- ALL must pass:
      1. vest centre inside the worker box,
      2. vest centre inside/near the torso (sides + bottom margin only),
      3. vest overlaps the torso box by >= `overlap_threshold`,
      4. vest NOT too high (centre at/below the chest top -> kills face/head),
      5. vest NOT too low / too side-heavy (centre within the central column),
      6. >= MIN_VEST_IN_WORKER (60%) of the vest area inside the worker box.

    A vest held in the hand, by the side, low, or up near the face fails one
    of these gates and is treated as loose (not worn).
    """
    tx1, ty1, tx2, ty2 = torso_box
    vcx = (vest_box[0] + vest_box[2]) / 2.0
    vcy = (vest_box[1] + vest_box[3]) / 2.0

    # (1) vest centre inside the worker box
    if not box_center_inside(vest_box, worker_box):
        return False

    tw = tx2 - tx1
    th = ty2 - ty1
    mx = TORSO_NEAR_MARGIN * tw
    my = TORSO_NEAR_MARGIN * th

    # (4) reject too-high vests (face/head)
    if vcy < ty1:
        return False
    # (5) reject too-low / too-side vests
    if vcy > ty2 + my:
        return False
    if vcx < tx1 - mx or vcx > tx2 + mx:
        return False

    # (3) overlap with the torso region
    torso_cover = calculate_overlap_ratio(torso_box, vest_box)  # inter / torso_area
    vest_inside = calculate_overlap_ratio(vest_box, torso_box)  # inter / vest_area
    if max(torso_cover, vest_inside) < overlap_threshold:
        return False

    # (6) vest mostly inside the worker box
    if calculate_overlap_ratio(vest_box, worker_box) < MIN_VEST_IN_WORKER:
        return False

    return True


def count_workers_without_worn_vest(worker_boxes, vest_boxes, overlap_threshold: float = 0.40) -> int:
    """How many workers have NO vest worn on their torso?

    Each such worker is a no_vest violation -- including the 'held vest' case
    where a vest object exists in the frame but is not on the worker's chest.
    """
    if not worker_boxes:
        return 0
    n = 0
    for wb in worker_boxes:
        torso = get_worker_torso_box(wb)
        worn = any(
            vest_matches_worker_torso(vb, wb, torso, overlap_threshold)
            for vb in vest_boxes
        )
        if not worn:
            n += 1
    return n


# ---------------------------------------------------------------------------
# HUD
# ---------------------------------------------------------------------------
def draw_hud(frame, fps, frame_counts, workers_n, violations_saved) -> None:
    """Compact vertical HUD in the top-left corner.

    Lines:
        FPS, workers, vest, no_vest, helmet, no_helmet, violations
    The `violations` line is the cumulative number of SAVED violation
    events (after cooldown), not per-frame.
    """
    vest_n      = frame_counts.get("vest",      0)
    no_vest_n   = frame_counts.get("no_vest",   0)
    helmet_n    = frame_counts.get("helmet",    0)
    no_helmet_n = frame_counts.get("no_helmet", 0)

    WHITE  = (255, 255, 255)
    YELLOW = (0,   255, 255)
    G      = GREEN
    R      = RED

    lines = [
        (f"FPS: {fps:.1f}",            YELLOW),
        (f"workers: {workers_n}",       WHITE),
        (f"vest: {vest_n}",             G if vest_n      > 0 else WHITE),
        (f"no_vest: {no_vest_n}",       R if no_vest_n   > 0 else WHITE),
        (f"helmet: {helmet_n}",         G if helmet_n    > 0 else WHITE),
        (f"no_helmet: {no_helmet_n}",   R if no_helmet_n > 0 else WHITE),
        (f"violations: {violations_saved}", R if violations_saved > 0 else WHITE),
    ]

    x0, y0     = 20, 30
    font       = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.7
    thickness  = 2
    line_h     = 30
    pad        = 12

    max_text_w = max(
        cv2.getTextSize(text, font, font_scale, thickness)[0][0]
        for text, _ in lines
    )
    panel_left   = x0 - pad
    panel_top    = max(y0 - line_h + (line_h - pad) // 2 - pad, 0)
    panel_right  = x0 + max_text_w + pad
    panel_bottom = y0 + line_h * (len(lines) - 1) + pad

    overlay = frame.copy()
    cv2.rectangle(
        overlay, (panel_left, panel_top), (panel_right, panel_bottom),
        (0, 0, 0), -1,
    )
    cv2.addWeighted(overlay, 0.55, frame, 0.45, 0, frame)

    for i, (text, color) in enumerate(lines):
        y = y0 + i * line_h
        cv2.putText(
            frame, text, (x0, y), font, font_scale, color, thickness, cv2.LINE_AA
        )


# ---------------------------------------------------------------------------
# Violation logic
# ---------------------------------------------------------------------------
def detect_violations(frame_counts: dict, max_confs: dict):
    """Turn a frame's PPE counts into a list of violation dicts.

    A violation is only triggered when the matching class was actually
    detected in this frame. We pick the "best" (most informative) violation
    when multiple apply:
      * BOTH no_vest AND no_helmet present -> single "Multiple PPE Missing"
        (we DO NOT also emit the two individual violations, to avoid
         triple-logging the same frame).
      * Otherwise emit each individual violation that fired.
    """
    has_no_vest   = frame_counts.get("no_vest",   0) > 0
    has_no_helmet = frame_counts.get("no_helmet", 0) > 0

    events = []

    if has_no_vest and has_no_helmet:
        # Combined: use the LOWER of the two confidences so the row's
        # confidence is conservative ("the weakest link").
        conf = min(max_confs.get("no_vest", 0.0), max_confs.get("no_helmet", 0.0))
        events.append({
            "type":     "Multiple PPE Missing",
            "severity": VIOLATION_META["Multiple PPE Missing"][0],
            "confidence": conf,
        })
    else:
        if has_no_vest:
            events.append({
                "type":     "Safety Vest Missing",
                "severity": VIOLATION_META["Safety Vest Missing"][0],
                "confidence": max_confs.get("no_vest", 0.0),
            })
        if has_no_helmet:
            events.append({
                "type":     "Helmet Missing",
                "severity": VIOLATION_META["Helmet Missing"][0],
                "confidence": max_confs.get("no_helmet", 0.0),
            })

    return events


def ensure_csv_header(csv_path: Path) -> None:
    """Create the CSV with a header row the first time we use it."""
    if csv_path.exists() and csv_path.stat().st_size > 0:
        return
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()


def append_csv_row(csv_path: Path, row: dict) -> None:
    """Append one violation row to the CSV log."""
    with csv_path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writerow(row)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    args = parse_args()

    # Resolve source: "0" -> int 0 (webcam), otherwise treat as file path
    if args.source.isdigit():
        source = int(args.source)
        source_desc = f"webcam_index_{source}"
    else:
        source = args.source
        if not Path(source).exists():
            print(f"[ERROR] Video file not found: {source}")
            return 1
        source_desc = Path(source).name

    # --- Load models --------------------------------------------------------
    # We load TWO YOLO models:
    #   ppe_model    -> SafeVision-trained PPE model (vest / no_vest / helmet / no_helmet)
    #   person_model -> COCO yolov8n.pt, used to count real workers in the scene
    model_path = Path(args.model)
    if not model_path.exists():
        print(f"[ERROR] PPE model weights not found: {model_path}")
        return 1

    print(f"[INFO] Loading PPE model: {model_path}")
    try:
        ppe_model = YOLO(str(model_path))
    except Exception as exc:
        print(f"[ERROR] Failed to load PPE model: {exc}")
        return 1
    print("[INFO] PPE model loaded.")

    print(f"[INFO] Loading worker (person) model: {args.person_model}")
    try:
        person_model = YOLO(args.person_model)
    except Exception as exc:
        print(f"[ERROR] Failed to load worker model: {exc}")
        return 1
    print("[INFO] Worker model loaded.")
    print(
        f"[INFO] Thresholds  -> PPE conf: {args.conf:.2f}   "
        f"Person/worker conf: {args.person_conf:.2f}   "
        f"Cooldown: {args.cooldown:.1f}s   "
        f"Clear-after: {args.clear_after:.1f}s   "
        f"Worker-overlap: {args.worker_overlap:.2f}"
    )
    if args.strict_vest_matching:
        print(
            f"[INFO] Vest matching mode -> STRICT torso overlap (experimental, "
            f"vest-overlap={args.vest_overlap:.2f}); a worker holding a vest "
            f"(not worn on torso) is treated as no_vest."
        )
    else:
        print(
            "[INFO] Vest matching mode -> stable [default]: model no_vest "
            "class gated by worker overlap. (Enable --strict-vest-matching "
            "for experimental torso-based held-vest detection.)"
        )

    # --- Prep output paths --------------------------------------------------
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    ensure_csv_header(CSV_LOG_PATH)
    print(f"[INFO] Screenshots -> {SCREENSHOTS_DIR}")
    print(f"[INFO] CSV log     -> {CSV_LOG_PATH}")

    # --- Open video source --------------------------------------------------
    print(f"[INFO] Opening source: {source_desc}")
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        print(f"[ERROR] Could not open video source: {source_desc}")
        return 1

    in_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 640
    in_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 480
    in_fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
    print(f"[INFO] Source opened: {in_w}x{in_h} @ {in_fps:.1f} fps (reported)")

    # --- Optional annotated-video writer -----------------------------------
    writer = None
    out_path = None
    if args.save_video:
        VIDEO_OUT_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = VIDEO_OUT_DIR / f"safevision_violations_{ts}.mp4"
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        save_fps = in_fps if in_fps and in_fps > 1 else 20.0
        writer = cv2.VideoWriter(str(out_path), fourcc, save_fps, (in_w, in_h))
        if not writer.isOpened():
            print(f"[WARN] Could not open VideoWriter for {out_path}. Not saving.")
            writer = None
        else:
            print(f"[INFO] Saving annotated video to: {out_path}")

    # --- Inference loop -----------------------------------------------------
    win_name = "SafeVision AI - Violations - press 'q' to quit"
    cv2.namedWindow(win_name, cv2.WINDOW_NORMAL)

    # Cooldown tracking: violation_type -> last unix-time we saved it.
    # If (now - last_saved_at) < args.cooldown, we suppress the save for
    # that type. Cooldown alone is NOT enough to stop "same continuous
    # violation counted forever" -- see active_violations below.
    last_saved_at: dict = {name: 0.0 for name in VIOLATION_META}

    # Active-state tracking: a violation is "active" from the moment we
    # save it until it has been ABSENT for at least `args.clear_after`
    # seconds. While a violation is active, no new event is logged for
    # that type, even after the cooldown expires. This is what makes the
    # `violations` HUD/CSV count "one event per continuous appearance",
    # which is what users actually expect for an MVP dashboard.
    #
    #   Re-trigger rule for a NEW event of type T:
    #     1. Either active_violations[T] is False, AND
    #     2. The cooldown for T has elapsed, AND
    #     3. T is currently detected in this frame.
    #
    #   Clear rule (run every frame):
    #     If T is NOT in this frame AND (now - last_seen[T]) > clear_after
    #     -> active_violations[T] = False  (so the next appearance counts).
    active_violations: dict = {name: False for name in VIOLATION_META}
    last_seen_violation_time: dict = {name: 0.0 for name in VIOLATION_META}

    # Running counters for the final summary
    saved_counts: dict = {name: 0 for name in VIOLATION_META}
    violations_saved_total = 0

    # Duplicate-filter accounting (for the end-of-run summary only,
    # not the on-screen HUD). 'raw' is what the PPE model produced;
    # 'kept' is what survived per-class IoU deduplication.
    raw_ppe_total = 0
    kept_ppe_total = 0

    # Worker-match accounting (Day 6.5). These count PPE-violation boxes
    # that fired in a frame but had NO worker overlap and were therefore
    # NOT saved as worker violations. Surfaced in the final summary so
    # the operator can tell how often the worker-match gate intervened.
    unmatched_no_vest_count   = 0
    unmatched_no_helmet_count = 0

    frames_processed = 0
    last_t = time.time()
    fps_smoothed = 0.0

    try:
        while True:
            ok, frame = cap.read()
            if not ok or frame is None:
                print("[INFO] No more frames (end of stream).")
                break

            # ---- Run both models on the same frame -------------------------
            try:
                ppe_results = ppe_model.predict(
                    source=frame, conf=args.conf, verbose=False,
                )
            except Exception as exc:
                print(f"[WARN] PPE inference failed on a frame: {exc}")
                continue

            try:
                person_results = person_model.predict(
                    source=frame,
                    conf=args.person_conf,
                    classes=[COCO_PERSON_CLASS_ID],
                    verbose=False,
                )
            except Exception as exc:
                print(f"[WARN] Worker inference failed on a frame: {exc}")
                person_results = None

            ppe_result = ppe_results[0]

            # ---- Deduplicate PPE detections BEFORE counting / drawing -----
            # The PPE model can sometimes output multiple overlapping boxes
            # for the same region (e.g. three `no_vest` boxes on one chest).
            # We collapse those down to one box per class+region using a
            # simple per-class IoU>0.5 filter. Worker/person boxes are NOT
            # touched here -- they come from a different model entirely.
            raw_ppe_dets = extract_ppe_detections(ppe_result)
            ppe_dets     = filter_duplicate_boxes(raw_ppe_dets, iou_threshold=0.5)
            raw_ppe_total  += len(raw_ppe_dets)
            kept_ppe_total += len(ppe_dets)

            # ---- Draw boxes + collect per-frame stats ----------------------
            # frame_counts / max_confs reflect the FILTERED detections,
            # so the HUD, violation logic, screenshots, and CSV all see
            # the deduplicated picture.
            frame_counts: dict = {name: 0 for name in CLASS_NAMES.values()}
            max_confs:    dict = {name: 0.0 for name in CLASS_NAMES.values()}
            draw_ppe_detections(frame, ppe_dets, frame_counts, max_confs)

            workers_n = 0
            worker_boxes: list = []
            if person_results is not None:
                workers_n, worker_boxes = draw_worker_boxes(
                    frame, person_results[0], args.person_conf
                )

            # Debug: draw the torso/chest region used for worn-vest matching.
            if args.show_torso:
                for wb in worker_boxes:
                    tb = get_worker_torso_box(wb)
                    cv2.rectangle(
                        frame,
                        (int(tb[0]), int(tb[1])), (int(tb[2]), int(tb[3])),
                        (200, 200, 200), 1,
                    )

            # ---- Worker <-> PPE matching ----------------------------------
            # Before we let `detect_violations` produce events, decide which
            # no_vest / no_helmet boxes actually belong to a real worker.
            # A standalone no_vest box (e.g. a shirt on a chair) will NOT
            # produce a saved violation, even if active-state + cooldown
            # would otherwise allow it.
            matched_no_vest = False
            matched_no_helmet = False
            unmatched_nv_this_frame = 0
            unmatched_nh_this_frame = 0
            for det in ppe_dets:
                cname = det["class_name"]
                if cname not in ("no_vest", "no_helmet"):
                    continue
                is_match = ppe_matches_worker(
                    det["bbox"], worker_boxes,
                    overlap_threshold=args.worker_overlap,
                )
                if cname == "no_vest":
                    if is_match:
                        matched_no_vest = True
                    else:
                        unmatched_nv_this_frame += 1
                elif cname == "no_helmet":
                    if is_match:
                        matched_no_helmet = True
                    else:
                        unmatched_nh_this_frame += 1

            # Bump cumulative skip counters (for the final summary only).
            unmatched_no_vest_count   += unmatched_nv_this_frame
            unmatched_no_helmet_count += unmatched_nh_this_frame

            # ---- Torso-based worn-vest check (Day 8, OPT-IN) --------------
            # OFF by default (demo-safe). Only when --strict-vest-matching is
            # set do we also flag a worker as no_vest when no vest is WORN on
            # their torso (the 'held vest' case). This torso logic is unstable
            # on side views / face-area boxes, so it is opt-in. When off, the
            # script uses ONLY the model's own no_vest class gated by worker
            # overlap -- the stable Day 6.5 behaviour.
            if args.strict_vest_matching:
                vest_boxes = [d["bbox"] for d in ppe_dets if d["class_name"] == "vest"]
                workers_without_vest = count_workers_without_worn_vest(
                    worker_boxes, vest_boxes, overlap_threshold=args.vest_overlap
                )
                if workers_without_vest > 0:
                    frame_counts["no_vest"] = max(
                        frame_counts.get("no_vest", 0), workers_without_vest
                    )
                    matched_no_vest = True
                    # If the model emitted no no_vest box, we have no model
                    # confidence; record a nominal value so the CSV/HUD don't
                    # show 0.00 for a real (torso-derived) violation.
                    if max_confs.get("no_vest", 0.0) <= 0.0:
                        max_confs["no_vest"] = 0.50

            # Lookup: violation_type -> may-save?
            # 'Multiple PPE Missing' requires BOTH classes matched.
            allow_save = {
                "Safety Vest Missing":  matched_no_vest,
                "Helmet Missing":       matched_no_helmet,
                "Multiple PPE Missing": matched_no_vest and matched_no_helmet,
            }

            # ---- FPS (EMA for a smoother number) ---------------------------
            now = time.time()
            dt = now - last_t
            last_t = now
            if dt > 0:
                inst_fps = 1.0 / dt
                fps_smoothed = (
                    inst_fps if fps_smoothed == 0.0
                    else 0.9 * fps_smoothed + 0.1 * inst_fps
                )

            # ---- HUD (drawn BEFORE the screenshot so it's in the saved image)
            draw_hud(
                frame, fps_smoothed, frame_counts, workers_n,
                violations_saved_total,
            )

            # ---- Violation detection: active-state + cooldown gates -------
            # We do this AFTER drawing so the screenshot we save has the
            # boxes + HUD already burned into it.
            events = detect_violations(frame_counts, max_confs)

            # Build a quick lookup so we can also expire types that did NOT
            # fire this frame (see the "clear" pass below).
            fired_types = {ev["type"] for ev in events}

            for ev in events:
                vtype = ev["type"]
                severity = ev["severity"]
                conf = float(ev["confidence"])

                # Always refresh "last time this violation was visible".
                # We do this even when we suppress the save below, so the
                # clear-after timer doesn't trip mid-violation.
                last_seen_violation_time[vtype] = now

                # Worker-match gate (Day 6.5):
                # If the PPE-violation box(es) for this type don't overlap
                # any worker box by >= --worker-overlap, do NOT save. We
                # still drew the red PPE box on screen, so the operator
                # can see the detection, but it is not logged as a worker
                # violation.
                if not allow_save[vtype]:
                    continue

                # Active-state gate: if this type is already an open event,
                # don't count it again until it has been absent long enough.
                if active_violations[vtype]:
                    continue

                # Cooldown gate: a safety net so two rapid appearances of
                # the same type can't both save within `args.cooldown`s.
                if (now - last_saved_at[vtype]) < args.cooldown:
                    continue

                # Build a filesystem-safe screenshot filename.
                prefix = VIOLATION_META[vtype][1]
                ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
                shot_name = f"{prefix}_{ts_str}_frame{frames_processed}.jpg"
                shot_path = SCREENSHOTS_DIR / shot_name

                # Save the ANNOTATED frame (boxes + HUD already drawn).
                try:
                    ok_write = cv2.imwrite(str(shot_path), frame)
                except Exception as exc:
                    print(f"[WARN] Failed to write screenshot {shot_path}: {exc}")
                    ok_write = False
                if not ok_write:
                    continue

                # Append the CSV row.
                row = {
                    "violation_id":    uuid.uuid4().hex[:12],
                    "timestamp":       datetime.now().isoformat(timespec="seconds"),
                    "source":          source_desc,
                    "frame_number":    frames_processed,
                    "violation_type":  vtype,
                    "severity":        severity,
                    "confidence":      f"{conf:.3f}",
                    "worker_detected": "yes" if workers_n > 0 else "no",
                    "screenshot_path": str(shot_path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
                }
                try:
                    append_csv_row(CSV_LOG_PATH, row)
                except Exception as exc:
                    print(f"[WARN] Failed to write CSV row: {exc}")
                    # don't update counters if the log failed
                    continue

                last_saved_at[vtype] = now
                active_violations[vtype] = True   # event is now "open"
                saved_counts[vtype] += 1
                violations_saved_total += 1
                print(
                    f"[VIOLATION] {vtype} (sev={severity}, conf={conf:.2f}) "
                    f"-> {shot_path.name}"
                )

            # ---- Clear pass: expire active types that have been absent ---
            # For each violation type that did NOT fire this frame, check
            # how long it has been since we last saw it. If that gap is
            # bigger than `clear_after`, mark it inactive so the next
            # appearance can produce a NEW event.
            for vtype in VIOLATION_META:
                if vtype in fired_types:
                    continue
                if active_violations[vtype] and \
                   (now - last_seen_violation_time[vtype]) > args.clear_after:
                    active_violations[vtype] = False

                # Re-draw the HUD so the LIVE counter reflects the new total
                # for the next imshow (not strictly needed; it'll update next frame too).
                # We intentionally do NOT re-draw here to keep cost low.

            # ---- Show / save -----------------------------------------------
            cv2.imshow(win_name, frame)
            if writer is not None:
                writer.write(frame)

            frames_processed += 1

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                print("[INFO] 'q' pressed, exiting.")
                break
            if cv2.getWindowProperty(win_name, cv2.WND_PROP_VISIBLE) < 1:
                print("[INFO] Window closed, exiting.")
                break

    except KeyboardInterrupt:
        print("\n[INFO] Interrupted by user (Ctrl+C).")
    except Exception as exc:
        print(f"[ERROR] Unexpected error in main loop: {exc}")
    finally:
        cap.release()
        if writer is not None:
            writer.release()
        cv2.destroyAllWindows()

        # --- Summary --------------------------------------------------------
        print("\n" + "=" * 60)
        print("SafeVision AI - violation run summary")
        print("=" * 60)
        print(f"Frames processed       : {frames_processed}")
        print(f"Avg FPS (smoothed)     : {fps_smoothed:.2f}")
        print(f"Total violations saved : {violations_saved_total}")
        print("")
        print("By violation type:")
        print(f"  Safety Vest Missing  : {saved_counts['Safety Vest Missing']}")
        print(f"  Helmet Missing       : {saved_counts['Helmet Missing']}")
        print(f"  Multiple PPE Missing : {saved_counts['Multiple PPE Missing']}")
        print("")
        print(f"Screenshots folder     : {SCREENSHOTS_DIR}")
        print(f"CSV log                : {CSV_LOG_PATH}")
        if writer is not None and out_path is not None:
            print(f"Saved annotated video  : {out_path}")
        print("")
        # Duplicate-filter accounting -- gives a sense of how often the PPE
        # model fired multiple overlapping boxes for the same region.
        if raw_ppe_total > 0:
            removed = raw_ppe_total - kept_ppe_total
            pct = (removed / raw_ppe_total) * 100.0
            print(
                f"PPE duplicate filter   : raw={raw_ppe_total}  "
                f"kept={kept_ppe_total}  removed={removed} ({pct:.1f}%)"
            )
        else:
            print("PPE duplicate filter   : raw=0  kept=0  removed=0")
        print("")
        print(
            f"Counting mode          : active-state + cooldown "
            f"(clear_after={args.clear_after:.1f}s, cooldown={args.cooldown:.1f}s)"
        )
        print(
            "                         A continuous violation is counted ONCE."
        )
        print(
            "                         A new event is only logged after the"
        )
        print(
            "                         violation disappears for >clear_after seconds."
        )
        print("")
        print(
            f"Worker-match gate      : overlap_threshold={args.worker_overlap:.2f}"
        )
        print(
            f"  Unmatched no_vest    : {unmatched_no_vest_count}  "
            "(PPE boxes that fired without a worker overlap, NOT saved)"
        )
        print(
            f"  Unmatched no_helmet  : {unmatched_no_helmet_count}  "
            "(PPE boxes that fired without a worker overlap, NOT saved)"
        )
        print("")
        print("Note: helmet / no_helmet detection in the v2 PPE model is")
        print("      currently LESS RELIABLE than vest / no_vest.")
        print("      Treat 'Helmet Missing' and 'Multiple PPE Missing'")
        print("      counts as experimental until the helmet class is")
        print("      retrained with more data.")
        print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
