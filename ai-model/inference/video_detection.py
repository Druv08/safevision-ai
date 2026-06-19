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
DEFAULT_MODEL = (
    PROJECT_ROOT
    / "ai-model"
    / "outputs"
    / "training-runs"
    / "safevision_yolov8n_5class_v5c_fast"
    / "weights"
    / "best.pt"
)
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

# ---- Raw helmet debug box colors (--show-helmet-debug-boxes) ---------------
# These draw the RAW model helmet detections even when they are filtered out,
# so we can verify whether the model detects head PPE at all.
RAW_HELMET_COLOR    = (0, 255, 255)   # yellow -> raw helmet box (filtered or not)
RAW_NO_HELMET_COLOR = (0, 165, 255)   # orange -> raw no_helmet box (filtered or not)


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
        "--save",
        action="store_true",
        help="If set, save annotated output video to ai-model/outputs/video-detections/",
    )
    parser.add_argument(
        "--model",
        default=str(DEFAULT_MODEL),
        help="Path to SafeVision PPE YOLO weights (default: v5c_fast best.pt)",
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
    """Return [((x1,y1,x2,y2), conf), ...] for pose detections that pass BOTH
    the box-confidence gate and the keypoint sanity check."""
    workers = []
    if pose_result is None or pose_result.boxes is None or len(pose_result.boxes) == 0:
        return workers
    if pose_result.keypoints is None:
        return workers

    boxes = pose_result.boxes.xyxy.cpu().numpy()
    confs = pose_result.boxes.conf.cpu().numpy()
    kp_conf_all = pose_result.keypoints.conf
    if kp_conf_all is None:
        return workers
    kp_conf_all = kp_conf_all.cpu().numpy()

    for i, ((x1, y1, x2, y2), conf) in enumerate(zip(boxes, confs)):
        if conf < pose_conf:
            continue
        if i >= len(kp_conf_all):
            continue
        if not is_valid_worker_pose(kp_conf_all[i], keypoint_conf_threshold):
            continue
        workers.append(((float(x1), float(y1), float(x2), float(y2)), float(conf)))
    return workers


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

    frames_processed = 0
    last_t = time.time()
    fps_smoothed = 0.0
    last_debug_frame = -999   # throttle for --debug-ppe raw-detection prints

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
            workers = (
                get_valid_worker_boxes(pose_results[0], args.pose_conf)
                if pose_results is not None else []
            )
            worker_boxes = [wb for wb, _ in workers]
            workers_n = len(worker_boxes)

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

                for (wb, wconf), status in zip(workers, worker_status):
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

                helmet_worn, helmet_loose, _helmet_dropped = classify_head_ppe(
                    helmet_dets, worker_boxes, overlap_threshold=hov
                )
                no_helmet_head, _nh_loose, _nh_dropped = classify_head_ppe(
                    no_helmet_dets, worker_boxes, overlap_threshold=hov
                )

                # Positive PPE -> always drawn normally.
                for box, conf in helmet_worn:
                    _draw_labeled_box(frame, box, f"helmet {conf:.2f}", HELMET_COLOR)
                for box, conf in vest_keep:
                    _draw_labeled_box(frame, box, f"vest {conf:.2f}", WORN_VEST_COLOR)

                # Loose helmets (held in hand) -> never counted; amber on request.
                if args.show_loose_helmets:
                    for box, conf in helmet_loose:
                        _draw_labeled_box(frame, box, f"loose helmet {conf:.2f}", LOOSE_HELMET_COLOR)

                # Negative PPE boxes -> hidden by default; drawn only on request.
                if args.show_negative_boxes:
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
                helmet_n    = len(helmet_worn)
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
                for wb, wconf in workers:
                    _draw_labeled_box(frame, wb, f"worker {wconf:.2f}", WORKER_BOX_COLOR)

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
