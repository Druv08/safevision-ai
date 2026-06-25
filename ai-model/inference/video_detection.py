"""
SafeVision AI - Day 5 / Day 8 update
Local video / webcam PPE detection using TWO YOLOv8 models in parallel:

  1. SafeVision PPE model  (trained, 5 classes: person/helmet/no_helmet/vest/no_vest)
     -> Detects PPE objects: vest / no_vest / helmet / no_helmet boxes.

  2. YOLOv8 POSE model  (yolov8n-pose.pt, COCO pretrained)
     -> Detects real humans/workers by predicting body keypoints (nose,
        shoulders, hips, etc.). A worker is only counted when the model
        finds enough body keypoints, so a shirt hanging on a chair or a
        person-shaped poster will NOT inflate the workers count.

Day 8 inference fix - "is the vest actually WORN?"
--------------------------------------------------
Before this change the overlay counted a `vest` the moment the PPE model saw
a vest-shaped object ANYWHERE in the frame. That produced two bugs:

  * False vest count  -> a vest object lying around / held up counted as 1.
  * Loose vest        -> a worker HOLDING a vest (not wearing it) was treated
                         as compliant, when they should be `no_vest`.

The fix changes the rule from "vest object detected anywhere" to:

    A worker is WEARING a vest only if a vest box overlaps that worker's
    torso/chest region enough AND the vest is centred in (or near) that region.

So compliance is now decided PER WORKER:
  * worker with a vest matched to their torso  -> counts as `vest`
  * worker with no vest matched to their torso -> counts as `no_vest`
A vest that matches no worker torso is a "loose" vest and is NOT counted as
worn (optionally drawn in amber with --show-loose-vests).

Events are now real violation events (not per-frame): a continuous `no_vest`
worker is counted ONCE, using a small stateful tracker (cooldown + clear_after).

Usage:
    # Webcam (default)
    python ai-model/inference/video_detection.py

    # Video file with saved output
    python ai-model/inference/video_detection.py --source path/to/video.mp4 --save

    # Tune the worn-vest / event logic
    python ai-model/inference/video_detection.py --vest-overlap 0.25 \
        --event-cooldown 5 --clear-after 2 --show-loose-vests

Press 'q' in the video window to quit.

SafeVision PPE classes (v2 model):
    0 = person      (weak - NOT used for worker count)
    1 = helmet
    2 = no_helmet
    3 = vest
    4 = no_vest

COCO pose keypoint indices (used by yolov8n-pose.pt):
    0  = nose
    5  = left_shoulder    6  = right_shoulder
    11 = left_hip         12 = right_hip
"""

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[2]

MODEL_CANDIDATES = [
    PROJECT_ROOT / "ai-model" / "outputs" / "training-runs" / "safevision_yolov8n_5class_v5d_50epochs" / "weights" / "best.pt",
    PROJECT_ROOT / "ai-model" / "outputs" / "training-runs" / "safevision_yolov8n_5class_v2" / "weights" / "best.pt",
    PROJECT_ROOT / "ai-model" / "outputs" / "training-runs" / "safevision_yolov8n_5class_smoke" / "weights" / "best.pt",
    PROJECT_ROOT / "yolov8n.pt",
]

DEFAULT_MODEL = next((c for c in MODEL_CANDIDATES if c.exists()), MODEL_CANDIDATES[0])
OUTPUT_DIR = PROJECT_ROOT / "ai-model" / "outputs" / "video-detections"


def _find_default_pose_model() -> str:
    """Locate a local copy of yolov8n-pose.pt; fall back to the bare name.

    Ultralytics will auto-download `yolov8n-pose.pt` on first use if no file
    is found locally, so returning the bare name is always a safe fallback.
    """
    candidates = [
        PROJECT_ROOT / "yolov8n-pose.pt",            # repo root
        PROJECT_ROOT.parent / "yolov8n-pose.pt",     # parent
        Path.cwd() / "yolov8n-pose.pt",
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    return "yolov8n-pose.pt"


DEFAULT_POSE_MODEL = _find_default_pose_model()

# ---- Colors (OpenCV uses BGR, not RGB) ------------------------------------
WORKER_BOX_COLOR = (255, 200, 0)    # cyan-ish blue  -> every valid worker
WORN_VEST_COLOR  = (0, 200, 0)      # green          -> vest matched to torso
NO_VEST_COLOR    = (0, 0, 255)      # red            -> worker torso w/o vest
LOOSE_VEST_COLOR = (0, 215, 255)    # amber/yellow   -> vest matched to nobody
HELMET_COLOR     = (0, 200, 0)      # green
NO_HELMET_COLOR  = (0, 0, 255)      # red

# Default per-keypoint confidence threshold. A keypoint is counted as
# "reliably visible" only when its confidence is >= this value.
KEYPOINT_CONF_THRESHOLD = 0.4

# Important COCO keypoint indices used to decide "is this really a person?".
IMPORTANT_KEYPOINTS = {
    0:  "nose",
    5:  "left_shoulder",
    6:  "right_shoulder",
    11: "left_hip",
    12: "right_hip",
}

# Need at least this many of the important keypoints above to be visible
# before we accept the detection as a real worker.
MIN_IMPORTANT_KEYPOINTS = 3

# COCO head/shoulder keypoint indices, used to anchor worn-helmet validation to
# the actual face/head position (not just worker-box proportions).
KP_NOSE, KP_LEYE, KP_REYE, KP_LEAR, KP_REAR, KP_LSHO, KP_RSHO = 0, 1, 2, 3, 4, 5, 6

# Class id -> human-readable name (must match v2 model training order)
CLASS_NAMES = {
    0: "person",
    1: "helmet",
    2: "no_helmet",
    3: "vest",
    4: "no_vest",
}

# ---- Torso region geometry (fractions of the worker box) ------------------
# The chest/upper-body area where a safety vest is actually worn. A vest must
# overlap THIS region (not just the full-body box) to count as worn.
#   x: middle 70% of the worker width  (drop 15% on each side)
#   y: from 20% down to 65% of the worker height (chest band, not the legs)
TORSO_X_INSET = 0.15
TORSO_Y_TOP   = 0.20
TORSO_Y_BOT   = 0.65

# When checking "is the vest centred in the torso?", allow the centre to fall
# slightly outside the torso box on the SIDES and BOTTOM only (never above the
# chest start -- that is hard-rejected to kill face/head false positives).
TORSO_NEAR_MARGIN = 0.15

# At least this fraction of the vest box AREA must lie inside the worker box
# for the vest to be considered "on" that worker. Rejects a vest held out to
# the side / mostly outside the body.
MIN_VEST_IN_WORKER = 0.60

# ---- Head region geometry (for helmet / no_helmet) ------------------------
# A hard hat sits at the TOP of the worker box, not on the torso. So helmet /
# no_helmet are matched against the head region (top fraction of the worker
# box), NOT the torso. This is what was wrongly filtering helmets out before.
HEAD_REGION_FRAC = 0.35      # head = top 35% of the worker box height
HEAD_NEAR_MARGIN = 0.25      # allow the helmet centre slightly outside the head box

LOOSE_HELMET_COLOR = (0, 215, 255)   # amber -> helmet on a worker but NOT on head
UNCERTAIN_COLOR    = (180, 180, 180) # grey  -> uncertain helmet candidate (debug only)

# ---- Raw helmet debug box colors (--show-helmet-debug-boxes) ---------------
# These draw the RAW model helmet detections even when they are filtered out,
# so we can verify whether the model detects head PPE at all.
RAW_HELMET_COLOR    = (0, 255, 255)   # yellow -> raw helmet box (filtered or not)
RAW_NO_HELMET_COLOR = (0, 165, 255)   # orange -> raw no_helmet box (filtered or not)

# ---- Helmet colour-assist (HSV yellow-hardhat fallback) -------------------
# OPT-IN (--helmet-color-assist). When the PPE model misses a clearly-WORN
# yellow hard hat (close-up, large shell, near the top edge / cropped), this
# fallback finds the shell by HSV colour in/above each worker's head region and
# counts it as a worn helmet. Same yellow range as the training labels. It runs
# PER WORKER, so with no workers it never fires, and a yellow blob that is not
# aligned over a worker's head (held in hand / off to the side) is rejected.
COLOR_YELLOW_LOW   = np.array([18, 80, 80])
COLOR_YELLOW_HIGH  = np.array([38, 255, 255])
COLOR_ASSIST_CONF  = 0.55      # synthetic confidence shown for colour helmets


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="SafeVision AI - local video/webcam PPE detection"
    )
    parser.add_argument(
        "--source",
        default="0",
        help="Video source: '0' for webcam (default) or path to a video file",
    )
    parser.add_argument(
        "--conf",
        type=float,
        default=0.50,
        help=(
            "PPE-model confidence threshold (default: 0.50). Raised from 0.25 "
            "to drop low-confidence false vest/no_vest boxes. Override as "
            "needed, e.g. --conf 0.55."
        ),
    )
    parser.add_argument(
        "--pose-conf",
        type=float,
        default=0.5,
        help="YOLO pose person-box confidence threshold (default: 0.5)",
    )
    parser.add_argument(
        "--ppe-worker-overlap",
        type=float,
        default=0.10,
        help=(
            "In default mode, a vest/no_vest box is only shown/counted if at "
            "least this fraction of it overlaps a worker box (default: 0.10). "
            "Kept low because PPE boxes are smaller than the worker box. If no "
            "worker is detected, all PPE counts are 0."
        ),
    )
    parser.add_argument(
        "--helmet-worker-overlap",
        type=float,
        default=0.03,
        help=(
            "Overlap threshold for helmet/no_helmet vs the worker box "
            "(default: 0.03, lower than --ppe-worker-overlap because a hard "
            "hat sits at the top edge and barely overlaps the body). Helmets "
            "are primarily matched by the worker HEAD region, not the torso."
        ),
    )
    parser.add_argument(
        "--helmet-hold-frames",
        type=int,
        default=8,
        help=(
            "Temporal smoothing for the WORN-helmet signal (default: 8, ~0.3s "
            "at 25fps). If a helmet was detected on a worker's head, that "
            "worker keeps a 'helmet' status for up to this many frames after "
            "the box briefly drops out (head tilt / motion blur), so the count "
            "does not flicker 1->0->1. The hold only opens AFTER a real on-head "
            "helmet detection on that worker, so it never invents a helmet on a "
            "bare/headphone head, and held helmets (not on the head) never feed "
            "it. Set 0 to disable smoothing (raw per-frame helmet)."
        ),
    )
    parser.add_argument(
        "--infer-no-helmet",
        dest="infer_no_helmet",
        action="store_true",
        default=True,
        help=(
            "ON by default. Make helmet compliance WORKER-based: every visible "
            "worker without a valid (detected or smoothed) on-head helmet is "
            "counted as no_helmet, even if the raw no_helmet box never fires "
            "(phone / mirror / partial face occlusion). A held helmet is not "
            "on the head, so its worker is still no_helmet."
        ),
    )
    parser.add_argument(
        "--no-infer-no-helmet",
        dest="infer_no_helmet",
        action="store_false",
        help=(
            "Disable worker-based inference: count no_helmet only from raw "
            "on-head no_helmet detections (old behaviour)."
        ),
    )
    parser.add_argument(
        "--helmet-color-assist",
        dest="helmet_color_assist",
        action="store_true",
        help=(
            "OPT-IN fallback. When the PPE model misses a clearly-WORN yellow "
            "hard hat (close-up, large shell, near the top edge / cropped), "
            "detect the shell by HSV colour in/above each worker's head region "
            "and count it as a worn helmet. Runs per worker (never fires with "
            "no workers); a held / off-head / side yellow blob is rejected."
        ),
    )
    parser.add_argument(
        "--show-helmet-debug",
        "--show-helmet-color-debug",
        dest="show_helmet_color_debug",
        action="store_true",
        help=(
            "Helmet worn-validation debug, DEBUG-ONLY visuals (alias: "
            "--show-helmet-color-debug). Draws the tight head region (cyan) + "
            "face/head anchor dot + source text, and rejected candidates "
            "(orange); prints per-candidate lines: source=<pose_face/fallback/"
            "none> candidate=<yolo/color> decision=<ACCEPT/REJECT> reason=<...>. "
            "Reasons: accepted_yolo_on_head / accepted_color_on_head / "
            "accepted_closeup_on_head / accepted_far_view_on_head / "
            "accepted_worker_fallback; rejected_held_side / rejected_too_low / "
            "rejected_far_from_head_center / rejected_far_view_not_top_aligned / "
            "rejected_no_worker / rejected_no_face_anchor / "
            "rejected_not_head_aligned / rejected_huge_foreground_not_on_head. "
            "In NORMAL/demo mode NONE of these debug visuals (pose_face box, "
            "nose dot, head region, rejected boxes, labels) appear. Throttled."
        ),
    )
    parser.add_argument(
        "--helmet-worker-fallback",
        dest="helmet_worker_fallback",
        action="store_true",
        default=True,
        help=(
            "ON by default. Worker-drop fallback: if a worker who was just "
            "accepted as wearing a helmet briefly loses its pose box (bend "
            "down, very close/far, side profile), keep the helmet for the "
            "remaining --helmet-hold-frames window AS LONG AS a strong helmet "
            "detection still sits at that head position. A helmet held alone in "
            "an empty frame (no prior worn worker) is never sustained."
        ),
    )
    parser.add_argument(
        "--no-helmet-worker-fallback",
        dest="helmet_worker_fallback",
        action="store_false",
        help="Disable the worker-drop helmet fallback (helmet -> 0 the instant the worker box drops).",
    )
    parser.add_argument(
        "--helmet-fallback-conf",
        type=float,
        default=0.50,
        help=(
            "Minimum PPE-model helmet confidence for a detection to SUPPORT a "
            "worker-drop ghost hold (default: 0.50). Higher = more conservative "
            "fallback."
        ),
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help="If set, save annotated output video to ai-model/outputs/video-detections/",
    )
    parser.add_argument(
        "--model",
        default=str(DEFAULT_MODEL),
        help="Path to SafeVision PPE YOLO weights (default: v5d_50epochs best.pt)",
    )
    parser.add_argument(
        "--pose-model",
        default=DEFAULT_POSE_MODEL,
        help="Path to YOLOv8 pose weights for worker detection (default: yolov8n-pose.pt)",
    )
    # ---- Day 8: worn-vest + event-debounce knobs --------------------------
    parser.add_argument(
        "--strict-vest-matching",
        action="store_true",
        help=(
            "OPT-IN: decide vest/no_vest per worker by matching a vest to the "
            "worker's torso/chest region. Experimental and unstable on side "
            "views / face-area boxes, so it is OFF by default. When off, the "
            "stable raw-object detection (original behaviour) is used."
        ),
    )
    parser.add_argument(
        "--vest-overlap",
        type=float,
        default=0.40,
        help=(
            "Minimum overlap between a vest box and a worker's torso region "
            "before the vest is counted as WORN (default: 0.40)."
        ),
    )
    parser.add_argument(
        "--event-cooldown",
        type=float,
        default=5.0,
        help=(
            "Minimum seconds between two counted no_vest violation events "
            "(default: 5). Stops the events counter inflating every frame."
        ),
    )
    parser.add_argument(
        "--clear-after",
        type=float,
        default=2.0,
        help=(
            "Seconds a no_vest violation must be ABSENT before it can be "
            "counted again as a NEW event (default: 2)."
        ),
    )
    parser.add_argument(
        "--show-negative-boxes",
        action="store_true",
        help=(
            "Debug only: draw the no_vest / no_helmet boxes (red). Off by "
            "default so the demo overlay stays clean -- negative status shows "
            "only in the HUD counts. (Default-mode only.)"
        ),
    )
    parser.add_argument(
        "--show-helmet-debug-boxes",
        action="store_true",
        help=(
            "Debug only: draw the RAW helmet boxes in yellow (raw_helmet) and "
            "RAW no_helmet boxes in orange (raw_no_helmet), even when they were "
            "filtered out. Use with --debug-ppe to verify the model detects "
            "head PPE at all. (Default-mode only.)"
        ),
    )
    parser.add_argument(
        "--show-loose-helmets",
        action="store_true",
        help=(
            "If set, draw helmet boxes that are on a worker but NOT on the head "
            "(e.g. a helmet held in the hand) in amber. These are never counted "
            "as a worn helmet. Off by default."
        ),
    )
    parser.add_argument(
        "--debug-ppe",
        action="store_true",
        help=(
            "If set, print RAW PPE detections (before filtering) with class, "
            "confidence, bbox, the keep/drop verdict and the filter reason "
            "(no worker / failed worker overlap / failed head-region check / "
            "loose helmet). Helmet + no_helmet raw boxes are always printed so "
            "you can see whether the model detects head PPE at all. Throttled "
            "to ~every 15 frames (every 5 when a helmet appears)."
        ),
    )
    parser.add_argument(
        "--show-loose-vests",
        action="store_true",
        help=(
            "If set, draw vest boxes that did NOT match any worker torso "
            "(loose / held vests) in amber. Off by default to avoid clutter."
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
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Geometry helpers (worn-vest matching)
# ---------------------------------------------------------------------------
def calculate_iou(box_a, box_b) -> float:
    """Intersection-over-Union between two [x1, y1, x2, y2] boxes.

    IoU is "how much do these two rectangles overlap?", as a number from
    0.0 (no overlap) to 1.0 (identical box).
    """
    ax1, ay1, ax2, ay2 = box_a
    bx1, by1, bx2, by2 = box_b

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


def calculate_overlap_ratio(box_a, box_b) -> float:
    """Fraction of `box_a`'s area that lies inside `box_b`.

    This is NOT IoU. It answers "how much of box_a is covered by box_b?"
    (intersection / area(box_a)), which is the signal we want when asking
    whether a vest covers a (much larger or smaller) torso region.

    Returns a value in [0.0, 1.0].
    """
    ax1, ay1, ax2, ay2 = box_a
    bx1, by1, bx2, by2 = box_b

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
    if area_a <= 0.0:
        return 0.0
    return float(inter / area_a)


def ppe_overlaps_any_worker(ppe_box, worker_boxes, threshold: float = 0.10) -> bool:
    """True if at least `threshold` of the PPE box lies inside ANY worker box.

    Uses fraction-of-PPE-inside-worker (calculate_overlap_ratio(ppe, worker)),
    so the threshold can stay low: a small vest box on a chest covers only a
    little of the full-body worker box. This is what rejects background /
    floating false PPE detections that don't sit on a person.
    """
    for wb in worker_boxes:
        if calculate_overlap_ratio(ppe_box, wb) >= threshold:
            return True
    return False


def filter_ppe_by_workers(dets, worker_boxes, threshold: float = 0.10):
    """Keep only (box, conf) PPE detections that overlap a worker box.

    If there are NO workers, returns [] -> all PPE counts become 0.
    """
    if not worker_boxes:
        return []
    return [
        (box, conf) for (box, conf) in dets
        if ppe_overlaps_any_worker(box, worker_boxes, threshold)
    ]


def get_worker_head_box(worker_box):
    """Head region = the TOP `HEAD_REGION_FRAC` of the worker box.

    A hard hat sits here, not on the torso, so helmet / no_helmet are matched
    against this region instead of the chest.
    """
    x1, y1, x2, y2 = worker_box
    return (x1, y1, x2, y1 + HEAD_REGION_FRAC * (y2 - y1))


def box_on_worker_head(box, worker_box, margin: float = HEAD_NEAR_MARGIN) -> bool:
    """True if `box`'s centre is inside (or near) this worker's head region."""
    return box_center_inside(box, get_worker_head_box(worker_box), margin=margin)


def box_on_any_worker_head(box, worker_boxes, margin: float = HEAD_NEAR_MARGIN) -> bool:
    """True if `box`'s centre is in/near ANY worker's head region."""
    for wb in worker_boxes:
        if box_on_worker_head(box, wb, margin):
            return True
    return False


def classify_head_ppe(dets, worker_boxes, overlap_threshold: float = 0.03):
    """Split helmet / no_helmet detections by where they sit on a worker.

    Returns (on_head, loose, dropped):
      on_head : centre in/near a worker head region  -> WORN / valid, counted.
      loose   : overlaps a worker (>= overlap_threshold) but NOT on the head
                -> e.g. a helmet held in the hand. Displayed only on request,
                never counted as worn.
      dropped : touches no worker at all -> ignored.
    """
    on_head, loose, dropped = [], [], []
    for box, conf in dets:
        if box_on_any_worker_head(box, worker_boxes):
            on_head.append((box, conf))
        elif ppe_overlaps_any_worker(box, worker_boxes, overlap_threshold):
            loose.append((box, conf))
        else:
            dropped.append((box, conf))
    return on_head, loose, dropped


def _kp_visible(kcf, idx, thr) -> bool:
    """True if keypoint `idx` has confidence >= thr."""
    return kcf is not None and idx < len(kcf) and float(kcf[idx]) >= thr


def get_face_anchor(worker_box, kxy, kcf, kp_thr: float = KEYPOINT_CONF_THRESHOLD):
    """Build a TIGHT face/head anchor, centred on the actual face -- not the
    full top width of the worker box.

    Returns {cx, cy, half_w, nose_y, reliable, source, head_region}:
      source 'pose_face' (reliable=True)  -> >=2 visible nose/eye/ear keypoints;
            centre = their mean, head width from ear (best) or eye spread.
      source 'fallback'  (reliable=False) -> NARROW, centred top-of-worker band
            used only when face keypoints are weak. Narrow on purpose so a
            helmet held to the SIDE inside the (large) worker box is still off
            the head column and gets rejected.

    `head_region` is a tight rectangle around the head that extends above for
    the shell (close-ups) and down to ~the brow/eye band.
    """
    wx1, wy1, wx2, wy2 = worker_box
    w = wx2 - wx1
    h = wy2 - wy1
    cxw = (wx1 + wx2) / 2.0

    face_idx = []
    if kxy is not None and kcf is not None:
        face_idx = [i for i in (KP_NOSE, KP_LEYE, KP_REYE, KP_LEAR, KP_REAR)
                    if _kp_visible(kcf, i, kp_thr)]

    if len(face_idx) >= 2:
        cx = sum(float(kxy[i][0]) for i in face_idx) / len(face_idx)
        cy = sum(float(kxy[i][1]) for i in face_idx) / len(face_idx)
        if _kp_visible(kcf, KP_LEAR, kp_thr) and _kp_visible(kcf, KP_REAR, kp_thr):
            half_w = abs(float(kxy[KP_LEAR][0]) - float(kxy[KP_REAR][0])) * 0.60
        elif _kp_visible(kcf, KP_LEYE, kp_thr) and _kp_visible(kcf, KP_REYE, kp_thr):
            half_w = abs(float(kxy[KP_LEYE][0]) - float(kxy[KP_REYE][0])) * 1.00
        else:
            half_w = 0.13 * w
        half_w = max(half_w, 10.0)
        if w > 1 and half_w < 0.05 * w:
            half_w = 0.13 * w
        nose_y = float(kxy[KP_NOSE][1]) if _kp_visible(kcf, KP_NOSE, kp_thr) else None
        reliable, source = True, "pose_face"
    else:
        cx = cxw
        cy = wy1 + 0.15 * h
        half_w = max(0.14 * w, 10.0)     # narrow column, NOT the full top width
        nose_y = None
        reliable, source = False, "fallback"

    head_region = (cx - 1.3 * half_w, cy - 2.2 * half_w,   # extends above the head
                   cx + 1.3 * half_w, cy + 0.5 * half_w)   # down to ~brow/eye band
    return {"cx": cx, "cy": cy, "half_w": half_w, "nose_y": nose_y,
            "reliable": reliable, "source": source, "head_region": head_region}


def _accept_reason(source: str, core: str) -> str:
    """Map an accepted `core` + candidate source to the debug accept label."""
    if core == "side_on_head":
        return "accepted_side_on_head"
    if core == "far_view_on_head":
        return "accepted_far_view_on_head"
    if core == "closeup_on_head":
        return "accepted_closeup_on_head"
    return f"accepted_{source}_on_head"      # accepted_yolo_on_head / accepted_color_on_head


def validate_worn_helmet(candidate_box, worker_box, face, frame_shape):
    """THREE-WAY worn-helmet decision shared by YOLO + colour candidates.

    Returns (verdict, core) where verdict is one of:
      'accept'    -> clearly worn. Counts now and opens/refreshes a smoother
                     track. core: on_head / closeup_on_head / side_on_head /
                     far_view_on_head.
      'uncertain' -> plausibly worn but not crisply aligned (side profile, weak
                     pose, brief dropout). NOT a held loose helmet: it is never
                     drawn as rejected and never STARTS a new helmet, but it lets
                     an EXISTING smoother hold survive. core: uncertain_*.
      'reject'    -> clearly held / not worn (far to the side, deep in torso,
                     huge foreground). Debug-only orange. core: rejected_*.

    Two anchor modes:
      * reliable face (front-ish): strict alignment to the tight face anchor,
        but borderline misses fall to 'uncertain' (not 'reject') so a real worn
        helmet is never flashed as rejected.
      * weak/side/occluded face: tolerant TOP-OF-PERSON band -- vertical position
        over the head + rough centring + adjacency, NO centred-nose requirement
        (this is what makes side-profile worn helmets work). Only clearly side /
        low candidates are rejected; ambiguous ones are 'uncertain'.
    """
    if face is None:
        return "uncertain", "uncertain_no_anchor"

    cx, cy, hw = face["cx"], face["cy"], face["half_w"]
    nose_y = face["nose_y"]
    reliable = face["reliable"]
    hx1, hy1, hx2, hy2 = face["head_region"]
    head_region = (hx1, hy1, hx2, hy2)

    wx1, wy1, wx2, wy2 = worker_box
    w = wx2 - wx1
    h = wy2 - wy1
    worker_cx = (wx1 + wx2) / 2.0
    worker_area = max(1.0, w * h)
    fh, fw = (frame_shape[0], frame_shape[1]) if frame_shape is not None else (0, 0)
    frame_area = max(1.0, fw * fh)

    bx1, by1, bx2, by2 = candidate_box
    bcx = (bx1 + bx2) / 2.0
    bcy = (by1 + by2) / 2.0
    bw = bx2 - bx1
    bh = by2 - by1
    area = bw * bh

    # Huge foreground covering face/chest -> clearly not a worn hat.
    if (area > 0.55 * worker_area and bh > 0.55 * h) or \
       (not reliable and area > 0.35 * frame_area and bh > 0.45 * h):
        return "reject", "rejected_huge_foreground_not_on_head"

    # ---- Reliable front-ish face: strict alignment, borderline -> uncertain --
    if reliable:
        dx = abs(bcx - cx)
        far_tol  = max(1.4 * hw, 0.12 * w)
        side_tol = max(1.0 * hw, 0.10 * w)
        inside_w = min(bx2, hx2) - max(bx1, hx1)

        # Clear HELD signals -> reject.
        if dx > max(2.2 * hw, 0.32 * w):
            return "reject", "rejected_far_from_head_center"
        if dx > side_tol and inside_w < 0.4 * bw:
            return "reject", "rejected_held_side"
        if bcy > cy + 1.2 * hw:
            return "reject", "rejected_too_low"
        if nose_y is not None and by2 > nose_y + 1.0 * hw:
            return "reject", "rejected_too_low"   # helmet covers the nose -> held in front

        # Crisp alignment -> accept.
        overlap    = calculate_overlap_ratio(candidate_box, head_region)
        region_cov = calculate_overlap_ratio(head_region, candidate_box)
        sits_above = (by2 <= cy) and (by2 >= hy1 - 0.5 * hw)
        aligned = (dx <= far_tol and bcy <= cy + 0.6 * hw
                   and (max(overlap, region_cov) >= 0.12 or sits_above))
        if aligned:
            hr_area = max(1.0, (hx2 - hx1) * (hy2 - hy1))
            if area > 0.45 * hr_area or by1 < wy1:
                return "accept", "closeup_on_head"
            return "accept", "on_head"
        # Near the head but not crisp (tilt / motion / partial) -> uncertain.
        return "uncertain", "uncertain_not_aligned"

    # ---- Weak / side / occluded face: tolerant TOP-OF-PERSON band ----------
    head_cx = worker_cx
    band_y1 = wy1 - 0.05 * h
    band_y2 = wy1 + 0.35 * h
    band = (head_cx - 0.35 * w, band_y1, head_cx + 0.35 * w, band_y2)
    ddx = abs(bcx - head_cx)

    # Clear HELD signals -> reject.
    if ddx > 0.45 * w:
        return "reject", "rejected_held_side"
    if bcy > wy1 + 0.60 * h:
        return "reject", "rejected_too_low"

    overlap    = calculate_overlap_ratio(candidate_box, band)
    band_cov   = calculate_overlap_ratio(band, candidate_box)
    sits_above = by2 <= band_y1 + 0.12 * h
    centered   = ddx <= 0.30 * w
    near_top   = bcy <= wy1 + 0.45 * h
    touches    = (max(overlap, band_cov) >= 0.08) or sits_above

    if centered and near_top and touches:
        # Worn on the head from a side / far / occluded view.
        if bw <= 0.20 * w or by1 < wy1:
            return "accept", "far_view_on_head"
        return "accept", "side_on_head"
    # Plausible but not confident -> uncertain (smoother may hold; not rejected).
    return "uncertain", "uncertain_top_borderline"


def helmet_belongs_to_worker(helmet_box, worker_box):
    """Loose association: is this helmet box plausibly this worker's at all?

    Only used to pick which worker a candidate is tested against; the strict
    worn/held decision is made by validate_worn_helmet. Accepts a box that
    overlaps the worker or whose centre is in/near the worker box (margin covers
    a close-up shell poking above the worker top).
    """
    return (calculate_overlap_ratio(helmet_box, worker_box) >= 0.05
            or box_center_inside(helmet_box, worker_box, margin=0.20))


def find_yellow_blob_for_worker(frame, worker_box, img_w, img_h):
    """Largest yellow hard-hat blob in/above the worker head region, or None.

    Pure colour detection (HSV) with only an area floor -- the worn-vs-held
    decision is made afterwards by validate_worn_helmet, so this and the YOLO
    path share the SAME validation. The search ROI may extend above the worker
    box (close-up) but stays above the torso so a yellow vest is not scanned.
    """
    x1, y1, x2, y2 = worker_box
    w = x2 - x1
    h = y2 - y1
    if w <= 1 or h <= 1:
        return None

    rx1 = int(max(0, x1 - 0.10 * w))
    rx2 = int(min(img_w, x2 + 0.10 * w))
    ry1 = int(max(0, y1 - 0.35 * h))
    ry2 = int(min(img_h, y1 + 0.50 * h))
    roi = frame[ry1:ry2, rx1:rx2]
    if roi.size == 0:
        return None

    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, COLOR_YELLOW_LOW, COLOR_YELLOW_HIGH)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        return None
    c = max(cnts, key=cv2.contourArea)
    head_region_area = max(1.0, w * HEAD_REGION_FRAC * h)
    min_area = max(500.0, 0.05 * head_region_area)   # no upper cap
    if cv2.contourArea(c) < min_area:
        return None
    bx, by, bw, bh = cv2.boundingRect(c)
    return [float(rx1 + bx), float(ry1 + by),
            float(rx1 + bx + bw), float(ry1 + by + bh)]


def get_worker_torso_box(worker_box):
    """Approximate the chest/upper-body region inside a worker box.

    Given a full-body worker box [x1, y1, x2, y2], return the torso region:
        x1 = worker_x1 + 15% of width
        x2 = worker_x2 - 15% of width
        y1 = worker_y1 + 20% of height
        y2 = worker_y1 + 65% of height

    This is the band where a safety vest should actually sit. Matching a vest
    against THIS (instead of the whole body) is what rejects a vest held low
    in the hands or down by the legs.
    """
    x1, y1, x2, y2 = worker_box
    w = x2 - x1
    h = y2 - y1
    tx1 = x1 + TORSO_X_INSET * w
    tx2 = x2 - TORSO_X_INSET * w
    ty1 = y1 + TORSO_Y_TOP * h
    ty2 = y1 + TORSO_Y_BOT * h
    return (tx1, ty1, tx2, ty2)


def box_center_inside(box, region, margin: float = 0.0) -> bool:
    """Is the centre of `box` inside `region` (optionally expanded by margin)?

    `margin` grows the region by that fraction on each side, so a centre that
    sits just outside still counts as "near" (the spec's "inside or near").
    """
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
    """Decide whether a vest box is being WORN on a worker's torso.

    Strict rule -- a vest counts as worn ONLY if ALL of these pass:

      1. The vest centre is inside the worker bounding box.
      2. The vest centre is inside the torso box, or very close to it (a small
         margin on the SIDES and BOTTOM only).
      3. The vest overlaps the torso box by at least `overlap_threshold`.
      4. The vest is NOT too high: its centre must be at/below the chest-start
         (torso top). This kills face/head false-positive vests.
      5. The vest is NOT too low or too side-heavy: its centre must stay within
         the central torso column (+ small margin) and not drop below the
         torso bottom (+ small margin).
      6. The vest is mostly ON the worker: at least `MIN_VEST_IN_WORKER`
         (60%) of the vest box area lies inside the worker box.

    A vest held in the hand, by the side, low, or up near the face fails one
    of these gates and is therefore treated as a loose (not worn) vest.
    """
    tx1, ty1, tx2, ty2 = torso_box
    vcx = (vest_box[0] + vest_box[2]) / 2.0
    vcy = (vest_box[1] + vest_box[3]) / 2.0

    # (1) vest centre inside the worker box
    if not box_center_inside(vest_box, worker_box):
        return False

    # Small tolerance for "near torso" -- sides + bottom only (never the top).
    tw = tx2 - tx1
    th = ty2 - ty1
    mx = TORSO_NEAR_MARGIN * tw
    my = TORSO_NEAR_MARGIN * th

    # (4) reject too-high vests (face/head): centre must not be above chest top
    if vcy < ty1:
        return False

    # (5) reject too-low / too-side vests
    if vcy > ty2 + my:
        return False
    if vcx < tx1 - mx or vcx > tx2 + mx:
        return False

    # (2) by reaching here the centre is within
    #     [tx1 - mx, tx2 + mx] x [ty1, ty2 + my]  -> inside/near the torso.

    # (3) vest must overlap the torso region by at least the threshold
    torso_cover = calculate_overlap_ratio(torso_box, vest_box)  # inter / torso_area
    vest_inside = calculate_overlap_ratio(vest_box, torso_box)  # inter / vest_area
    if max(torso_cover, vest_inside) < overlap_threshold:
        return False

    # (6) at least 60% of the vest area must lie inside the worker box
    if calculate_overlap_ratio(vest_box, worker_box) < MIN_VEST_IN_WORKER:
        return False

    return True


def assign_vests_to_workers(worker_boxes, vest_boxes, overlap_threshold: float = 0.40):
    """Match vest boxes to worker torsos and decide each worker's vest status.

    Returns:
        worker_status : list (parallel to `worker_boxes`) of dicts:
            {
              "worker_box": (x1,y1,x2,y2),
              "torso_box":  (x1,y1,x2,y2),
              "vest_status": "vest" | "no_vest",
              "vest_box":    (x1,y1,x2,y2) | None,   # the matched vest, if any
            }
        matched_vest_idx : set of indices into `vest_boxes` that got matched
            to at least one worker. Any vest index NOT in this set is a
            "loose" vest (matched nobody).
    """
    worker_status = []
    matched_vest_idx: set = set()

    for wb in worker_boxes:
        torso = get_worker_torso_box(wb)
        best_idx = None
        best_score = 0.0
        for vi, vb in enumerate(vest_boxes):
            if not vest_matches_worker_torso(vb, wb, torso, overlap_threshold):
                continue
            # Among all matching vests, keep the one that covers the chest most.
            score = calculate_overlap_ratio(torso, vb)
            if score > best_score:
                best_score = score
                best_idx = vi

        if best_idx is not None:
            matched_vest_idx.add(best_idx)
            worker_status.append({
                "worker_box": wb,
                "torso_box": torso,
                "vest_status": "vest",
                "vest_box": vest_boxes[best_idx],
            })
        else:
            worker_status.append({
                "worker_box": wb,
                "torso_box": torso,
                "vest_status": "no_vest",
                "vest_box": None,
            })

    return worker_status, matched_vest_idx


# ---------------------------------------------------------------------------
# Stateful no_vest violation tracker (real events, not per-frame)
# ---------------------------------------------------------------------------
class ViolationTracker:
    """Count no_vest violations as discrete EVENTS, not per frame.

    The webcam runs ~25-30 frames/sec. A naive counter that bumps every frame
    a violation is visible would race up by ~30/second for one standing
    worker. Instead we treat a continuously-visible no_vest as a SINGLE event:

      * While at least one no_vest worker is visible, the violation is
        "active" and we do not count it again.
      * The violation only "clears" after no_vest has been ABSENT for
        `clear_after` seconds (this debounces a worker who flickers out of
        detection for a frame or two).
      * After it clears and reappears, a NEW event is counted -- but only if
        at least `cooldown` seconds have passed since the last counted event
        (a safety net against rapid re-triggering).
    """

    def __init__(self, cooldown: float = 5.0, clear_after: float = 2.0):
        self.cooldown = cooldown
        self.clear_after = clear_after
        self.active_no_vest = False     # is a no_vest violation currently open?
        self.last_seen_time = 0.0       # last time a no_vest worker was visible
        self.last_event_time = -1e9     # last time we counted an event
        self.total_events = 0

    def update(self, no_vest_count: int, now: float) -> bool:
        """Feed the current frame's no_vest worker count. Returns True if a
        NEW event was counted this frame."""
        new_event = False
        if no_vest_count > 0:
            self.last_seen_time = now
            if not self.active_no_vest:
                # Rising edge of a violation. Count it if cooldown allows.
                if (now - self.last_event_time) >= self.cooldown:
                    self.total_events += 1
                    self.last_event_time = now
                    new_event = True
                # Mark active either way, so we don't retry every frame.
                self.active_no_vest = True
        else:
            # No violation visible this frame. Clear it once it has been gone
            # long enough, so the next appearance can count again.
            if self.active_no_vest and (now - self.last_seen_time) >= self.clear_after:
                self.active_no_vest = False
        return new_event


# ---------------------------------------------------------------------------
# Per-worker WORN-helmet temporal smoothing (anti-flicker)
# ---------------------------------------------------------------------------
class HelmetSmoother:
    """Keep a worn-helmet status alive for a short grace window per worker.

    Problem: during head tilt / turn / motion blur the helmet box drops out for
    1-2 frames, so the helmet count flickers 1 -> 0 -> 1 even though the helmet
    is still worn.

    Fix: per worker, once a REAL on-head helmet is detected, open a countdown of
    `hold_frames`. If the helmet box is missing on the next frames but the same
    worker is still visible, we keep the helmet status active (re-anchored to the
    worker's current head) until the countdown runs out, then drop it.

    The smoother respects every rule that protects against false helmets:
      * It is fed ONLY helmets already classified as on-head (worn). Held
        helmets (classify_head_ppe -> loose) never reach it, so a held helmet is
        never promoted to worn.
      * A worker that never had a real on-head helmet has no open countdown, so
        a bare head / headphones can never become a helmet.
      * A track is dropped the moment its worker is no longer visible (no
        floating helmet left behind).
      * With hold_frames <= 0 the smoother is a pure pass-through (raw helmet).

    Workers are not globally ID-tracked, so tracks are matched to the current
    frame's workers by head-box IoU (works for the realistic 1-few worker case).
    """

    def __init__(self, hold_frames: int = 8, iou_match: float = 0.3):
        self.hold_frames = max(0, int(hold_frames))
        self.iou_match = iou_match
        # Each track: {head_box, frames_left, helmet_box, conf}
        self.tracks: list = []

    def update(self, worker_boxes, worker_real, support_boxes=None,
               allow_ghost=False):
        """Smooth the worn-helmet status. Returns (per_worker, ghosts):

          per_worker : list PARALLEL to `worker_boxes`; each entry is
              (helmet_box, conf, is_held) for a worker counted as wearing a
              helmet THIS frame, else None.
          ghosts     : list of (helmet_box, conf) for helmets HELD OVER while
              their worker's pose box has briefly dropped (worker-drop
              fallback). Only produced when `allow_ghost` is set AND a strong
              helmet detection (`support_boxes`) still sits at the last known
              head position -- so a helmet held alone in an empty frame is never
              sustained.

        `worker_real` is a per-worker list: (box, conf) for a worker with a worn
        helmet THIS frame (model and/or colour), or None. `is_held` marks a
        smoothed hold-over (not a fresh detection) -- overlay only.

        A ghost track only ever originates from a previously ACCEPTED worn
        helmet, so loose / held helmets cannot start one.
        """
        support_boxes = support_boxes or []
        head_boxes = [get_worker_head_box(wb) for wb in worker_boxes]

        # Smoothing disabled -> only real on-head detections, no hold-over.
        if self.hold_frames <= 0:
            self.tracks = []
            per_worker = [
                (wr[0], wr[1], False) if wr is not None else None
                for wr in worker_real
            ]
            return per_worker, []

        new_tracks: list = []
        per_worker: list = [None] * len(worker_boxes)
        used = set()

        # ---- 1) Tracks tied to a CURRENTLY-visible worker --------------------
        for i in range(len(worker_boxes)):
            hbx = head_boxes[i]
            # Match this worker to the best unused existing track by head IoU.
            t_idx, t_iou = None, 0.0
            for ti, t in enumerate(self.tracks):
                if ti in used:
                    continue
                iou = calculate_iou(hbx, t["head_box"])
                if iou > t_iou:
                    t_iou, t_idx = iou, ti
            track = (
                self.tracks[t_idx]
                if t_idx is not None and t_iou >= self.iou_match
                else None
            )
            if track is not None:
                used.add(t_idx)

            if worker_real[i] is not None:
                # Fresh on-head helmet -> (re)open the full hold.
                box, conf = worker_real[i]
                new_tracks.append({
                    "head_box": hbx, "frames_left": self.hold_frames,
                    "helmet_box": box, "conf": conf,
                })
                per_worker[i] = (box, conf, False)
            elif track is not None and track["frames_left"] > 0:
                # No detection this frame but worker visible + hold still open:
                # keep helmet, re-anchored to the worker's current head.
                ohx = track["head_box"]
                dx = ((hbx[0] + hbx[2]) - (ohx[0] + ohx[2])) / 2.0
                dy = ((hbx[1] + hbx[3]) - (ohx[1] + ohx[3])) / 2.0
                ob = track["helmet_box"]
                box = (ob[0] + dx, ob[1] + dy, ob[2] + dx, ob[3] + dy)
                new_tracks.append({
                    "head_box": hbx, "frames_left": track["frames_left"] - 1,
                    "helmet_box": box, "conf": track["conf"],
                })
                per_worker[i] = (box, track["conf"], True)
            # else: worker visible but no helmet + no open hold -> stays None.

        # ---- 2) Ghost hold: tracks whose worker dropped this frame -----------
        # Keep a previously-accepted worn helmet alive for the remaining hold
        # window, but ONLY while a strong helmet detection still sits at that
        # head position. This bridges brief pose/worker drops (bend down, close-
        # up, side profile) without sustaining a helmet on an empty frame.
        ghosts: list = []
        if allow_ghost:
            for ti, t in enumerate(self.tracks):
                if ti in used or t["frames_left"] <= 0:
                    continue
                supported = any(
                    calculate_iou(sb, t["head_box"]) >= 0.20
                    or box_center_inside(sb, t["head_box"], margin=0.6)
                    for sb in support_boxes
                )
                if not supported:
                    continue
                new_tracks.append({
                    "head_box": t["head_box"],
                    "frames_left": t["frames_left"] - 1,
                    "helmet_box": t["helmet_box"], "conf": t["conf"],
                })
                ghosts.append((t["helmet_box"], t["conf"]))

        self.tracks = new_tracks
        return per_worker, ghosts


# ---------------------------------------------------------------------------
# Detection extraction
# ---------------------------------------------------------------------------
def get_ppe_boxes(ppe_result) -> dict:
    """Turn one PPE YOLO result into class-keyed lists of (box, conf).

    Returns: {class_name: [((x1,y1,x2,y2), conf), ...], ...}
    """
    out: dict = {name: [] for name in CLASS_NAMES.values()}
    if ppe_result.boxes is None or len(ppe_result.boxes) == 0:
        return out

    boxes = ppe_result.boxes.xyxy.cpu().numpy()
    confs = ppe_result.boxes.conf.cpu().numpy()
    cls_ids = ppe_result.boxes.cls.cpu().numpy().astype(int)

    for (x1, y1, x2, y2), conf, cls_id in zip(boxes, confs, cls_ids):
        name = CLASS_NAMES.get(int(cls_id))
        if name is None:
            continue
        out[name].append(((float(x1), float(y1), float(x2), float(y2)), float(conf)))
    return out


def is_valid_worker_pose(
    keypoints_conf,
    keypoint_conf_threshold: float = KEYPOINT_CONF_THRESHOLD,
    min_important: int = MIN_IMPORTANT_KEYPOINTS,
) -> bool:
    """Decide whether a single pose detection looks like a real human.

    We look at five "important" COCO keypoints (nose, left/right shoulder,
    left/right hip). If at least `min_important` of those have per-keypoint
    confidence >= `keypoint_conf_threshold`, we accept it as a real worker.
    This rejects hanging shirts / posters that fool a plain box detector.
    """
    if keypoints_conf is None:
        return False
    arr = np.asarray(keypoints_conf).flatten()
    if arr.size < max(IMPORTANT_KEYPOINTS) + 1:
        return False

    visible = 0
    for idx in IMPORTANT_KEYPOINTS:
        if arr[idx] >= keypoint_conf_threshold:
            visible += 1
    return visible >= min_important


def get_valid_worker_boxes(
    pose_result,
    pose_conf: float,
    keypoint_conf_threshold: float = KEYPOINT_CONF_THRESHOLD,
):
    """Return [((x1,y1,x2,y2), conf, kp_xy, kp_conf), ...] for pose detections
    that pass BOTH the box-confidence gate and the keypoint sanity check.

    kp_xy / kp_conf are the per-detection COCO keypoint arrays (xy = Nx2,
    conf = N), kept so worn-helmet validation can anchor to the real head/face.
    """
    workers = []
    if pose_result is None or pose_result.boxes is None or len(pose_result.boxes) == 0:
        return workers
    if pose_result.keypoints is None:
        return workers

    boxes = pose_result.boxes.xyxy.cpu().numpy()
    confs = pose_result.boxes.conf.cpu().numpy()
    kp_conf_all = pose_result.keypoints.conf
    kp_xy_all = pose_result.keypoints.xy
    if kp_conf_all is None or kp_xy_all is None:
        return workers
    kp_conf_all = kp_conf_all.cpu().numpy()
    kp_xy_all = kp_xy_all.cpu().numpy()

    for i, ((x1, y1, x2, y2), conf) in enumerate(zip(boxes, confs)):
        if conf < pose_conf:
            continue
        if i >= len(kp_conf_all):
            continue
        if not is_valid_worker_pose(kp_conf_all[i], keypoint_conf_threshold):
            continue
        workers.append((
            (float(x1), float(y1), float(x2), float(y2)), float(conf),
            kp_xy_all[i], kp_conf_all[i],
        ))
    return workers


def get_person_regions(pose_result, pose_conf: float):
    """Return ALL pose person detections >= pose_conf (NO keypoint gate), with
    keypoints: [((x1,y1,x2,y2), conf, kp_xy, kp_conf), ...].

    This is a WEAKER signal than get_valid_worker_boxes -- it does not require
    the 3-keypoint sanity check -- and is used ONLY as a head/body anchor for
    worn-helmet validation. A side-profile / partially-posed person who fails
    the strict worker gate can still anchor a worn helmet here, so a clearly
    worn hard hat is detected even when the HUD worker count is briefly 0.
    A helmet held alone with no person present matches no region, so it is never
    promoted to worn.
    """
    out = []
    if pose_result is None or pose_result.boxes is None or len(pose_result.boxes) == 0:
        return out
    boxes = pose_result.boxes.xyxy.cpu().numpy()
    confs = pose_result.boxes.conf.cpu().numpy()
    kp_xy_all = kp_conf_all = None
    if pose_result.keypoints is not None:
        if pose_result.keypoints.xy is not None:
            kp_xy_all = pose_result.keypoints.xy.cpu().numpy()
        if pose_result.keypoints.conf is not None:
            kp_conf_all = pose_result.keypoints.conf.cpu().numpy()
    for i, ((x1, y1, x2, y2), conf) in enumerate(zip(boxes, confs)):
        if conf < pose_conf:
            continue
        kxy = kp_xy_all[i] if (kp_xy_all is not None and i < len(kp_xy_all)) else None
        kcf = kp_conf_all[i] if (kp_conf_all is not None and i < len(kp_conf_all)) else None
        out.append((
            (float(x1), float(y1), float(x2), float(y2)), float(conf), kxy, kcf,
        ))
    return out


# ---------------------------------------------------------------------------
# Drawing helpers
# ---------------------------------------------------------------------------
def _draw_labeled_box(frame, box, text, color, thickness: int = 2) -> None:
    """Draw a rectangle + filled label tag for one box."""
    x1, y1, x2, y2 = (int(v) for v in box)
    cv2.rectangle(frame, (x1, y1), (x2, y2), color, thickness)
    (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
    cv2.rectangle(frame, (x1, y1 - th - 6), (x1 + tw + 4, y1), color, -1)
    cv2.putText(
        frame, text, (x1 + 2, y1 - 4),
        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA,
    )


def _fmt_box(box) -> str:
    """Compact 'x1,y1,x2,y2' string for one box (debug printing)."""
    return f"({box[0]:.0f},{box[1]:.0f},{box[2]:.0f},{box[3]:.0f})"


def debug_print_ppe_raw(frame_no, ppe_boxes, worker_boxes, ppe_overlap, helmet_overlap):
    """Print every RAW PPE detection (before filtering) with its filter verdict.

    For each detection we print class name, confidence, bbox, whether it passed
    filtering, and -- if not -- WHY it was filtered. helmet / no_helmet raw
    detections are ALWAYS printed (even when filtered) so we can tell whether
    the model is detecting head PPE at all.

    Note: detections below --conf never reach this function (the model drops
    them), so "low confidence" is surfaced by lowering --conf, not here.
    """
    n_workers = len(worker_boxes)
    print(f"[DEBUG-PPE] frame {frame_no}: workers={n_workers}")

    # ---- vest / no_vest : gated purely by worker-box overlap --------------
    for cname in ("vest", "no_vest"):
        for box, conf in ppe_boxes.get(cname, []):
            if n_workers == 0:
                passed, reason = False, "no worker in frame"
            elif ppe_overlaps_any_worker(box, worker_boxes, ppe_overlap):
                passed, reason = True, "counted"
            else:
                passed, reason = False, "failed worker overlap"
            print(f"    {'KEEP' if passed else 'DROP'} {cname:9s} "
                  f"conf={conf:.2f} bbox={_fmt_box(box)} -> {reason}")

    # ---- helmet / no_helmet : gated by the worker HEAD region -------------
    for cname in ("helmet", "no_helmet"):
        for box, conf in ppe_boxes.get(cname, []):
            if n_workers == 0:
                passed, reason = False, "no worker in frame"
            elif box_on_any_worker_head(box, worker_boxes):
                passed, reason = True, "counted (on head)"
            elif ppe_overlaps_any_worker(box, worker_boxes, helmet_overlap):
                passed, reason = (
                    False,
                    "failed head-region check (loose helmet: on worker, not on head)",
                )
            else:
                passed, reason = False, "no worker overlap"
            print(f"    {'KEEP' if passed else 'DROP'} {cname:9s} "
                  f"conf={conf:.2f} bbox={_fmt_box(box)} -> {reason}")


def draw_hud(frame, fps: float, display: dict, workers_n: int) -> None:
    """Draw a compact VERTICAL HUD in the top-left corner.

    `display` carries COMPLIANCE counts (not raw object counts):
        vest      -> number of workers WEARING a vest (matched to torso)
        no_vest   -> number of workers NOT wearing a vest
        helmet    -> raw helmet object count (kept as-is for now)
        no_helmet -> raw no_helmet object count (kept as-is for now)
        events    -> cumulative real no_vest violation events
    """
    vest_n      = display.get("vest",      0)
    no_vest_n   = display.get("no_vest",   0)
    helmet_n    = display.get("helmet",    0)
    no_helmet_n = display.get("no_helmet", 0)
    total_events = display.get("events",   0)

    WHITE  = (255, 255, 255)
    YELLOW = (0,   255, 255)
    GREEN  = (0,   220, 0)
    RED    = (0,   0,   255)

    lines = [
        (f"FPS: {fps:.1f}",          YELLOW),
        (f"workers: {workers_n}",    WHITE),
        (f"vest: {vest_n}",          GREEN if vest_n      > 0 else WHITE),
        (f"no_vest: {no_vest_n}",    RED   if no_vest_n   > 0 else WHITE),
        (f"helmet: {helmet_n}",      GREEN if helmet_n    > 0 else WHITE),
        (f"no_helmet: {no_helmet_n}",RED   if no_helmet_n > 0 else WHITE),
        (f"events: {total_events}",  RED   if total_events > 0 else WHITE),
    ]

    x0, y0      = 20, 30
    font        = cv2.FONT_HERSHEY_SIMPLEX
    font_scale  = 0.7
    thickness   = 2
    line_h      = 30
    pad         = 12

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
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    args = parse_args()

    # Resolve source: "0" -> int 0 (webcam), otherwise treat as file path
    if args.source.isdigit():
        source = int(args.source)
        source_desc = f"webcam index {source}"
    else:
        source = args.source
        if not Path(source).exists():
            print(f"[ERROR] Video file not found: {source}")
            return 1
        source_desc = f"file '{source}'"

    # --- Load models --------------------------------------------------------
    model_path = Path(args.model)
    if not model_path.exists():
        print(f"[ERROR] PPE model weights not found: {model_path}")
        return 1

    print(f"[INFO] Loading PPE model: {model_path}")
    try:
        model = YOLO(str(model_path))
    except Exception as exc:
        print(f"[ERROR] Failed to load PPE model: {exc}")
        return 1
    print("[INFO] PPE model loaded.")
    print(f"[INFO] PPE model path        : {model_path}")

    print(f"[INFO] Loading pose model: {args.pose_model}")
    try:
        pose_model = YOLO(args.pose_model)
    except Exception as exc:
        print(f"[ERROR] Failed to load pose model: {exc}")
        return 1
    print("[INFO] Pose model loaded.")
    print(
        f"[INFO] Thresholds  -> PPE conf: {args.conf:.2f}   "
        f"Pose conf: {args.pose_conf:.2f}   "
        f"Keypoint conf: {KEYPOINT_CONF_THRESHOLD:.2f} "
        f"(need {MIN_IMPORTANT_KEYPOINTS}/{len(IMPORTANT_KEYPOINTS)} important keypoints)"
    )
    # ---- Day 8 worn-vest / event-logic startup summary --------------------
    if args.strict_vest_matching:
        print("[INFO] Vest matching mode    : STRICT torso overlap (experimental)")
        print(f"[INFO] Vest overlap threshold: {args.vest_overlap:.2f}")
        print(f"[INFO] Show loose vests      : {args.show_loose_vests}")
        print(f"[INFO] Show torso (debug)    : {args.show_torso}")
    else:
        print("[INFO] Vest matching mode    : stable (raw PPE objects) [default]")
        print(f"[INFO] PPE-worker overlap    : {args.ppe_worker_overlap:.2f} "
              f"(vest/no_vest; 0 if no workers)")
        print(f"[INFO] Helmet-worker overlap : {args.helmet_worker_overlap:.2f} "
              f"(helmet matched by HEAD region, top {int(HEAD_REGION_FRAC*100)}% of worker)")
        print("[INFO] Negative boxes        : "
              + ("shown (red boxes, debug)" if args.show_negative_boxes
                 else "hidden [default, clean overlay]"))
        print(f"[INFO] Show loose helmets    : {args.show_loose_helmets}")
        print(f"[INFO] Show helmet dbg boxes : {args.show_helmet_debug_boxes}")
        print("[INFO] Helmet hold (frames)  : "
              + (f"{args.helmet_hold_frames} (worn-helmet anti-flicker smoothing)"
                 if args.helmet_hold_frames > 0 else "0 (disabled, raw per-frame)"))
        print("[INFO] No-helmet inference   : "
              + ("ON (worker-based: visible worker w/o on-head helmet = no_helmet)"
                 if args.infer_no_helmet else "OFF (raw no_helmet detections only)"))
        print("[INFO] Helmet colour-assist  : "
              + ("ON (HSV yellow-shell fallback for missed worn helmets)"
                 if args.helmet_color_assist else "OFF [default]"))
        print("[INFO] Worker-drop fallback  : "
              + (f"ON (ghost-hold worn helmet through brief pose drop, "
                 f"support conf >= {args.helmet_fallback_conf:.2f})"
                 if args.helmet_worker_fallback else "OFF"))
        print("[INFO] Helmet debug visuals  : "
              + ("ON (--show-helmet-debug)" if args.show_helmet_color_debug
                 else "OFF [clean demo overlay]"))
        print(f"[INFO] Debug PPE             : {args.debug_ppe}")
    print(f"[INFO] Event cooldown (s)    : {args.event_cooldown:.1f}")
    print(f"[INFO] Clear-after (s)       : {args.clear_after:.1f}")

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

    # --- Optional video writer ---------------------------------------------
    writer = None
    out_path = None
    if args.save:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = OUTPUT_DIR / f"safevision_output_{ts}.mp4"
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        save_fps = in_fps if in_fps and in_fps > 1 else 20.0
        writer = cv2.VideoWriter(str(out_path), fourcc, save_fps, (in_w, in_h))
        if not writer.isOpened():
            print(f"[WARN] Could not open VideoWriter for {out_path}. Not saving.")
            writer = None
        else:
            print(f"[INFO] Saving annotated video to: {out_path}")

    # --- Inference loop -----------------------------------------------------
    win_name = "SafeVision AI - press 'q' to quit"
    cv2.namedWindow(win_name, cv2.WINDOW_NORMAL)

    # Stateful no_vest event tracker (real events, not per-frame).
    tracker = ViolationTracker(
        cooldown=args.event_cooldown,
        clear_after=args.clear_after,
    )

    # Per-worker worn-helmet temporal smoother (anti-flicker). hold=0 disables.
    helmet_smoother = HelmetSmoother(hold_frames=args.helmet_hold_frames)

    frames_processed = 0
    last_t = time.time()
    fps_smoothed = 0.0
    last_debug_frame = -999   # throttle for --debug-ppe raw-detection prints
    last_color_debug_frame = -999   # throttle for --show-helmet-color-debug

    try:
        while True:
            ok, frame = cap.read()
            if not ok or frame is None:
                print("[INFO] No more frames (end of stream).")
                break

            # Run BOTH models on the same frame: PPE first, then pose.
            try:
                ppe_results = model.predict(
                    source=frame, conf=args.conf, verbose=False,
                )
            except Exception as exc:
                print(f"[WARN] PPE inference failed on a frame: {exc}")
                continue

            try:
                pose_results = pose_model.predict(
                    source=frame, conf=args.pose_conf, verbose=False,
                )
            except Exception as exc:
                print(f"[WARN] Pose inference failed on a frame: {exc}")
                pose_results = None

            ppe_result = ppe_results[0]

            # ---- 1) Collect raw PPE objects (still detected as before) -----
            ppe_boxes = get_ppe_boxes(ppe_result)
            vest_boxes    = [b for b, _ in ppe_boxes["vest"]]
            helmet_dets   = ppe_boxes["helmet"]      # (box, conf) list
            no_helmet_dets = ppe_boxes["no_helmet"]  # (box, conf) list

            # ---- 2) Valid workers from the pose model ----------------------
            # STRICT workers (3-keypoint gate) drive the HUD worker count, the
            # cyan boxes, and no_helmet inference.
            workers = (
                get_valid_worker_boxes(pose_results[0], args.pose_conf)
                if pose_results is not None else []
            )
            worker_boxes = [w[0] for w in workers]
            workers_n = len(worker_boxes)

            # PERSON REGIONS (weaker: no keypoint gate) are the anchors for
            # worn-helmet validation. A side-profile / partially-posed person
            # who fails the strict gate can still anchor a worn helmet here, so
            # a clearly worn hard hat is detected even when workers_n is 0. Each
            # region gets a tight face/head anchor (face if reliable, else a
            # narrow centred top-of-person fallback) for validate_worn_helmet.
            person_regions = (
                get_person_regions(pose_results[0], args.pose_conf)
                if pose_results is not None else []
            )
            person_boxes   = [p[0] for p in person_regions]
            person_anchors = [
                get_face_anchor(p[0], p[2], p[3]) for p in person_regions
            ]

            # ---- 3) Vest / PPE handling: stable (default) or strict mode ---
            if args.strict_vest_matching:
                # STRICT (optional, may be unstable): decide vest/no_vest PER
                # WORKER by matching a vest to the worker's torso/chest region.
                # Known instability on side views / face-area false boxes, so
                # this is OFF by default. Enable with --strict-vest-matching.
                # helmet / no_helmet stay raw here (experimental mode).
                helmet_n    = len(helmet_dets)
                no_helmet_n = len(no_helmet_dets)
                for box, conf in helmet_dets:
                    _draw_labeled_box(frame, box, f"helmet {conf:.2f}", HELMET_COLOR)
                for box, conf in no_helmet_dets:
                    _draw_labeled_box(frame, box, f"no_helmet {conf:.2f}", NO_HELMET_COLOR)

                worker_status, matched_vest_idx = assign_vests_to_workers(
                    worker_boxes, vest_boxes, overlap_threshold=args.vest_overlap
                )
                vest_worn_n = sum(1 for w in worker_status if w["vest_status"] == "vest")
                no_vest_n   = sum(1 for w in worker_status if w["vest_status"] == "no_vest")

                for w, status in zip(workers, worker_status):
                    wb, wconf = w[0], w[1]
                    _draw_labeled_box(frame, wb, f"worker {wconf:.2f}", WORKER_BOX_COLOR)
                    # Debug: draw the torso/chest region used for vest matching.
                    if args.show_torso:
                        tb = status["torso_box"]
                        cv2.rectangle(
                            frame,
                            (int(tb[0]), int(tb[1])), (int(tb[2]), int(tb[3])),
                            (200, 200, 200), 1,
                        )
                    if status["vest_status"] == "vest":
                        _draw_labeled_box(
                            frame, status["vest_box"], "vest (worn)", WORN_VEST_COLOR
                        )
                    else:
                        _draw_labeled_box(
                            frame, status["torso_box"], "NO VEST", NO_VEST_COLOR
                        )

                # Loose / unmatched vests (optional).
                if args.show_loose_vests:
                    for vi, vb in enumerate(vest_boxes):
                        if vi not in matched_vest_idx:
                            _draw_labeled_box(frame, vb, "loose vest", LOOSE_VEST_COLOR)
            else:
                # STABLE DEFAULT (demo-safe). PPE is only kept if it sits on a
                # real worker; with no workers every PPE count is 0.
                #   * vest / no_vest -> worker-box overlap (--ppe-worker-overlap)
                #   * helmet / no_helmet -> worker HEAD region (top of the box),
                #     NOT the torso, because a hard hat barely overlaps the body
                #     (this is what was wrongly filtering helmets out before).
                # A helmet whose centre is NOT on the head (e.g. held in hand) is
                # "loose": never counted as worn, shown only with --show-loose-helmets.
                # Clean overlay: only the cyan worker box + positive PPE boxes
                # (vest / helmet) are drawn. The no_vest / no_helmet boxes are
                # hidden and there is NO "Missing ..." warning text -- negative
                # status shows only in the HUD counts (--show-negative-boxes
                # brings the red boxes back for debugging).
                ov  = args.ppe_worker_overlap
                hov = args.helmet_worker_overlap

                vest_keep    = filter_ppe_by_workers(ppe_boxes["vest"],    worker_boxes, ov)
                no_vest_keep = filter_ppe_by_workers(ppe_boxes["no_vest"], worker_boxes, ov)

                # no_helmet (raw on-head) is kept only for the --no-infer-no-
                # helmet path and debug; helmet compliance below is worker-based.
                no_helmet_head, _nh_loose, _nh_dropped = classify_head_ppe(
                    no_helmet_dets, worker_boxes, overlap_threshold=hov
                )

                # ----- Worn-helmet decision (anchored to PERSON REGIONS) ------
                # Each helmet candidate (YOLO box OR colour blob) is validated
                # against the person region it sits on. validate_worn_helmet
                # returns a 3-WAY verdict:
                #   accept    -> worn now; feeds the smoother (worker_real).
                #   uncertain -> plausibly worn but not crisp (side profile /
                #                tilt / brief dropout). NOT drawn as rejected and
                #                NOT a new helmet, but lets an existing smoother
                #                hold survive (no flicker to rejected/0).
                #   reject    -> clearly held / not worn; debug-only orange.
                # Anchoring to PERSON regions (not strict workers) is what makes
                # side-profile / pose-weak worn helmets detect even at workers=0.
                fh, fw = frame.shape[:2]
                worker_real = [None] * len(person_boxes)   # per person-region
                helmet_dbg = []        # (region_i, src, cand, box, verdict, reason)
                helmet_rejected = []   # reject-verdict boxes  (debug only)
                helmet_uncertain = []  # uncertain-verdict boxes (debug only)

                for i, pb in enumerate(person_boxes):
                    face = person_anchors[i]
                    src = face["source"] if face else "none"
                    chosen = None      # (box, conf) accepted for this region
                    for hb, hc in helmet_dets:
                        if not helmet_belongs_to_worker(hb, pb):
                            continue
                        verdict, core = validate_worn_helmet(hb, pb, face, frame.shape)
                        reason = _accept_reason("yolo", core) if verdict == "accept" else core
                        helmet_dbg.append((i, src, "yolo", hb, verdict, reason))
                        if verdict == "accept":
                            if chosen is None or hc > chosen[1]:
                                chosen = (tuple(hb), hc)
                        elif verdict == "reject":
                            helmet_rejected.append(hb)
                        else:
                            helmet_uncertain.append(hb)
                    # Colour fallback only where the model accepted nothing here.
                    if args.helmet_color_assist and chosen is None:
                        cbox = find_yellow_blob_for_worker(frame, pb, fw, fh)
                        if cbox is not None:
                            verdict, core = validate_worn_helmet(cbox, pb, face, frame.shape)
                            reason = _accept_reason("color", core) if verdict == "accept" else core
                            helmet_dbg.append((i, src, "color", cbox, verdict, reason))
                            if verdict == "accept":
                                chosen = (tuple(cbox), COLOR_ASSIST_CONF)
                            elif verdict == "reject":
                                helmet_rejected.append(cbox)
                            else:
                                helmet_uncertain.append(cbox)
                    if chosen is not None:
                        worker_real[i] = chosen

                # Strong helmet detections that may SUPPORT a worker-drop ghost
                # hold (only those at/above the fallback confidence).
                support_boxes = [hb for hb, hc in helmet_dets
                                 if hc >= args.helmet_fallback_conf]

                # Temporal smoothing over PERSON regions -> per-region helmet
                # status + ghost holds. An uncertain region (worker_real None but
                # person still visible) keeps its hold; accept refreshes it; a
                # worker/person drop is bridged by a ghost while still detected.
                helmet_status, helmet_ghosts = helmet_smoother.update(
                    person_boxes, worker_real,
                    support_boxes=support_boxes,
                    allow_ghost=args.helmet_worker_fallback,
                )

                # Active worn helmets this frame (accepted/held + ghost).
                active_helmets = [(e[0], e[1]) for e in helmet_status if e is not None]
                active_helmets += list(helmet_ghosts)

                # Positive PPE -> always drawn green (demo-safe). Held-over gets
                # '*', ghost gets '~'; both read as a normal "helmet" box.
                for entry in helmet_status:
                    if entry is None:
                        continue
                    box, conf, is_held = entry
                    label = f"helmet {conf:.2f}{'*' if is_held else ''}"
                    _draw_labeled_box(frame, box, label, HELMET_COLOR)
                for box, conf in helmet_ghosts:
                    _draw_labeled_box(frame, box, f"helmet {conf:.2f}~", HELMET_COLOR)
                for box, conf in vest_keep:
                    _draw_labeled_box(frame, box, f"vest {conf:.2f}", WORN_VEST_COLOR)

                # Which STRICT workers have an active worn helmet near the head
                # (drives no_helmet). Ghost / non-worker helmets never CREATE
                # no_helmet.
                active_boxes = [b for b, _ in active_helmets]
                worker_has_helmet = [
                    any(box_on_worker_head(ab, wb)
                        or calculate_overlap_ratio(ab, wb) >= 0.05
                        for ab in active_boxes)
                    for wb in worker_boxes
                ]

                # ---- Helmet DEBUG visuals (ONLY with --show-helmet-debug) -----
                # Nothing below draws in normal/demo mode: no pose_face box, no
                # anchor dot, no head region, no rejected / uncertain boxes.
                if args.show_helmet_color_debug:
                    for face in person_anchors:
                        if face is None:
                            continue
                        hx1, hy1, hx2, hy2 = face["head_region"]
                        cv2.rectangle(frame, (int(hx1), int(hy1)),
                                      (int(hx2), int(hy2)), (255, 255, 0), 1)
                        cv2.circle(frame, (int(face["cx"]), int(face["cy"])),
                                   4, (255, 255, 0), -1)
                        cv2.putText(frame, face["source"],
                                    (int(hx1), max(12, int(hy1) - 4)),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.45,
                                    (255, 255, 0), 1, cv2.LINE_AA)
                    for box in helmet_uncertain:
                        _draw_labeled_box(frame, box, "uncertain", UNCERTAIN_COLOR)
                    for box in helmet_rejected:
                        _draw_labeled_box(frame, box, "rejected", RAW_NO_HELMET_COLOR)
                    gap = frames_processed - last_color_debug_frame
                    if gap >= 10 and (helmet_dbg or helmet_ghosts
                                      or (not person_boxes and helmet_dets)):
                        print(f"[HELMET-DBG] frame {frames_processed}: "
                              f"workers={workers_n} persons={len(person_boxes)} "
                              f"ghosts={len(helmet_ghosts)}")
                        for gbox, gconf in helmet_ghosts:
                            print(f"    source=ghost candidate=hold decision=ACCEPT "
                                  f"reason=accepted_worker_fallback "
                                  f"person_box=none helmet_box={_fmt_box(gbox)}")
                        if not person_boxes and helmet_dets and not helmet_ghosts:
                            for hb, _hc in helmet_dets:
                                print(f"    source=none candidate=yolo decision=REJECT "
                                      f"reason=rejected_no_worker "
                                      f"person_box=none helmet_box={_fmt_box(hb)}")
                        for ri, src, cand, box, verdict, reason in helmet_dbg:
                            print(f"    source={src} candidate={cand} "
                                  f"decision={verdict.upper()} reason={reason} "
                                  f"person_box={_fmt_box(person_boxes[ri])} "
                                  f"helmet_box={_fmt_box(box)}")
                        last_color_debug_frame = frames_processed

                # Negative PPE boxes -> hidden by default; drawn only on request.
                if args.show_negative_boxes:
                    if args.infer_no_helmet:
                        # Worker-based: mark every STRICT worker WITHOUT an
                        # active worn helmet as no_helmet on the head region.
                        for i, wb in enumerate(worker_boxes):
                            if not worker_has_helmet[i]:
                                _draw_labeled_box(
                                    frame, get_worker_head_box(wb),
                                    "no_helmet", NO_HELMET_COLOR,
                                )
                    else:
                        for box, conf in no_helmet_head:
                            _draw_labeled_box(frame, box, f"no_helmet {conf:.2f}", NO_HELMET_COLOR)
                    for box, conf in no_vest_keep:
                        _draw_labeled_box(frame, box, f"no_vest {conf:.2f}", NO_VEST_COLOR)

                # RAW helmet debug boxes (--show-helmet-debug-boxes): draw EVERY
                # raw helmet (yellow) / no_helmet (orange) the model produced,
                # even the ones filtering threw away, to confirm whether the
                # model detects head PPE at all.
                if args.show_helmet_debug_boxes:
                    for box, conf in helmet_dets:
                        _draw_labeled_box(frame, box, f"raw_helmet {conf:.2f}", RAW_HELMET_COLOR)
                    for box, conf in no_helmet_dets:
                        _draw_labeled_box(frame, box, f"raw_no_helmet {conf:.2f}", RAW_NO_HELMET_COLOR)

                vest_worn_n = len(vest_keep)
                no_vest_n   = len(no_vest_keep)
                # helmet = total active worn helmets across person regions
                # (accepted + held-over + worker-drop ghost). Can exceed the HUD
                # worker count when a helmet is worn on a person the strict gate
                # missed (e.g. side profile -> workers 0, helmet 1).
                helmet_n = len(active_helmets)
                worker_helmet_n = sum(1 for x in worker_has_helmet if x)
                if args.infer_no_helmet:
                    # STRICT workers without an active worn helmet are no_helmet.
                    # With no strict worker this is 0 (no false no_helmet).
                    no_helmet_n = workers_n - worker_helmet_n
                else:
                    no_helmet_n = len(no_helmet_head)

                # --debug-ppe: print RAW detections (before filtering) with the
                # filter verdict + reason. Throttled so it doesn't spam: at most
                # every 15 frames, but as soon as every 5 frames when a
                # helmet/no_helmet appears (to catch flickery head detections).
                if args.debug_ppe:
                    helmet_present = bool(helmet_dets or no_helmet_dets)
                    gap = frames_processed - last_debug_frame
                    if gap >= 15 or (helmet_present and gap >= 5):
                        debug_print_ppe_raw(
                            frames_processed, ppe_boxes, worker_boxes, ov, hov
                        )
                        last_debug_frame = frames_processed

                # Worker boxes (cyan). Clean overlay: NO "Missing Vest" /
                # "Missing Helmet" warning text. Negative status is reflected
                # only in the HUD counts (and as red boxes with
                # --show-negative-boxes).
                for w in workers:
                    _draw_labeled_box(frame, w[0], f"worker {w[1]:.2f}", WORKER_BOX_COLOR)

            # ---- 5) Events: debounced no_vest counter (kept in BOTH modes) -
            # The cooldown/clear-after tracker only changes the `events`
            # number, never the boxes, so it is demo-safe in default mode too.
            # In default mode it is driven by raw no_vest object presence; in
            # strict mode by the per-worker no_vest count.
            now = time.time()
            tracker.update(no_vest_n, now)

            # ---- FPS (exponential moving average) --------------------------
            dt = now - last_t
            last_t = now
            if dt > 0:
                inst_fps = 1.0 / dt
                fps_smoothed = (
                    inst_fps if fps_smoothed == 0.0
                    else 0.9 * fps_smoothed + 0.1 * inst_fps
                )

            # ---- HUD (compliance counts, not raw object counts) ------------
            display = {
                "vest": vest_worn_n,
                "no_vest": no_vest_n,
                "helmet": helmet_n,
                "no_helmet": no_helmet_n,
                "events": tracker.total_events,
            }
            draw_hud(frame, fps_smoothed, display, workers_n)

            # Show + (optionally) save
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
        print("\n" + "=" * 50)
        print("SafeVision AI - run summary")
        print("=" * 50)
        print(f"Frames processed     : {frames_processed}")
        print(f"Avg FPS (smoothed)   : {fps_smoothed:.2f}")
        print("")
        print(f"no_vest violation events : {tracker.total_events}")
        print("")
        if args.strict_vest_matching:
            print("Mode: STRICT torso overlap (experimental). Vest counts as")
            print("WORN only when a vest box overlaps a worker's torso/chest")
            print(f"region (overlap >= {args.vest_overlap:.2f}) and is centred there.")
        else:
            print("Mode: stable raw-object detection [default]. Vest/no_vest")
            print("counts are raw PPE detections (demo-safe). Strict per-worker")
            print("torso matching is available via --strict-vest-matching.")
        print(f"Events are debounced (clear_after={args.clear_after:.1f}s, "
              f"cooldown={args.event_cooldown:.1f}s).")
        if writer is not None and out_path is not None:
            print(f"Saved output         : {out_path}")
        print("=" * 50)

    return 0


if __name__ == "__main__":
    sys.exit(main())
