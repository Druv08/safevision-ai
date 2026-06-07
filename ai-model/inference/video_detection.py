"""
SafeVision AI - Day 5
Local video / webcam PPE detection using TWO YOLOv8 models in parallel:

  1. SafeVision PPE model  (trained, 5 classes: person/helmet/no_helmet/vest/no_vest)
     -> used for vest / no_vest / helmet / no_helmet boxes + counts

  2. COCO yolov8n.pt person detector
     -> used ONLY for the worker (human) count, because the SafeVision model's
        own `person` class is data-starved and rarely fires. Counting workers
        from a held-up vest gives wrong results, so we do it from a real,
        general-purpose person detector instead.

Usage:
    # Webcam (default)
    python ai-model/inference/video_detection.py

    # Video file with saved output
    python ai-model/inference/video_detection.py --source path/to/video.mp4 --save

    # Custom thresholds
    python ai-model/inference/video_detection.py --conf 0.4 --person-conf 0.4

Press 'q' in the video window to quit.

SafeVision PPE classes (v2 model):
    0 = person      (weak - NOT used for worker count)
    1 = helmet
    2 = no_helmet
    3 = vest
    4 = no_vest
"""

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

import cv2
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
OUTPUT_DIR = PROJECT_ROOT / "ai-model" / "outputs" / "video-detections"


def _find_default_person_model() -> str:
    """Locate a local copy of yolov8n.pt; fall back to the bare name.

    Ultralytics will auto-download `yolov8n.pt` on first use if no file is
    found, so returning the bare name is always a safe fallback.
    """
    candidates = [
        PROJECT_ROOT / "yolov8n.pt",            # repo root
        PROJECT_ROOT.parent / "yolov8n.pt",     # parent (existing copy)
        Path.cwd() / "yolov8n.pt",
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    return "yolov8n.pt"


DEFAULT_PERSON_MODEL = _find_default_person_model()

# COCO class id for a person (yolov8n.pt was trained on COCO)
COCO_PERSON_CLASS_ID = 0

# Color used to draw COCO person/worker boxes (BGR). Distinct from PPE colors.
WORKER_BOX_COLOR = (255, 200, 0)   # cyan-ish blue

# Class id -> human-readable name (must match v2 model training order)
CLASS_NAMES = {
    0: "person",
    1: "helmet",
    2: "no_helmet",
    3: "vest",
    4: "no_vest",
}

# BGR colors per class (OpenCV uses BGR, not RGB)
CLASS_COLORS = {
    0: (255, 200, 0),    # person       -> cyan-ish (rarely used now)
    1: (0, 200, 0),      # helmet       -> green (good)
    2: (0, 0, 255),      # no_helmet    -> red   (violation)
    3: (0, 200, 0),      # vest         -> green (good)
    4: (0, 0, 255),      # no_vest      -> red   (violation)
}


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
        default=0.25,
        help="PPE-model confidence threshold (default: 0.25)",
    )
    parser.add_argument(
        "--person-conf",
        type=float,
        default=0.4,
        help="COCO person-detector confidence threshold (default: 0.4)",
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help="If set, save annotated output video to ai-model/outputs/video-detections/",
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
# Drawing helpers
# ---------------------------------------------------------------------------
def draw_detections(frame, result, counts: dict) -> None:
    """Draw boxes + labels for one YOLO result onto `frame` in-place.

    Also increments `counts` for every detection seen in this frame.
    """
    if result.boxes is None or len(result.boxes) == 0:
        return

    # .xyxy gives [x1, y1, x2, y2] as a torch tensor, move to CPU + numpy
    boxes = result.boxes.xyxy.cpu().numpy()
    confs = result.boxes.conf.cpu().numpy()
    cls_ids = result.boxes.cls.cpu().numpy().astype(int)

    for (x1, y1, x2, y2), conf, cls_id in zip(boxes, confs, cls_ids):
        name = CLASS_NAMES.get(int(cls_id), f"id_{cls_id}")
        color = CLASS_COLORS.get(int(cls_id), (255, 255, 255))

        # Bounding box
        cv2.rectangle(
            frame,
            (int(x1), int(y1)),
            (int(x2), int(y2)),
            color,
            2,
        )

        # Label background + text
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
            frame,
            label,
            (int(x1) + 2, int(y1) - 4),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 0, 0),
            1,
            cv2.LINE_AA,
        )

        # Track running totals (so we can print a summary at the end)
        counts[name] = counts.get(name, 0) + 1


def draw_person_detections(frame, result) -> int:
    """Draw 'worker' boxes for COCO person detections and return the count.

    Only keeps boxes whose class id is COCO_PERSON_CLASS_ID (0). The label
    drawn on each box is 'worker' (not 'person') to match the overlay row.
    """
    if result.boxes is None or len(result.boxes) == 0:
        return 0

    boxes = result.boxes.xyxy.cpu().numpy()
    confs = result.boxes.conf.cpu().numpy()
    cls_ids = result.boxes.cls.cpu().numpy().astype(int)

    n_workers = 0
    for (x1, y1, x2, y2), conf, cls_id in zip(boxes, confs, cls_ids):
        if int(cls_id) != COCO_PERSON_CLASS_ID:
            continue
        n_workers += 1

        cv2.rectangle(
            frame,
            (int(x1), int(y1)),
            (int(x2), int(y2)),
            WORKER_BOX_COLOR,
            2,
        )

        label = f"worker {conf:.2f}"
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        cv2.rectangle(
            frame,
            (int(x1), int(y1) - th - 6),
            (int(x1) + tw + 4, int(y1)),
            WORKER_BOX_COLOR,
            -1,
        )
        cv2.putText(
            frame,
            label,
            (int(x1) + 2, int(y1) - 4),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 0, 0),
            1,
            cv2.LINE_AA,
        )

    return n_workers


def draw_hud(frame, fps: float, frame_counts: dict, event_counts: dict, workers_n: int) -> None:
    """Draw a compact VERTICAL HUD in the top-left corner.

    Layout (one row per line):
        FPS: <value>          (yellow)
        workers: <count>      (white)   <- from the COCO person detector
        vest: <count>         (green if >0 else white)
        no_vest: <count>      (red   if >0 else white)
        helmet: <count>       (green if >0 else white)
        no_helmet: <count>    (red   if >0 else white)
        events: <total>       (white)   <- sum of all rising-edge events so far

    `workers_n` is supplied by the caller from the COCO person detector
    (NOT from vest + no_vest), because the SafeVision model's own `person`
    class is too weak. If only a vest is shown to the camera with no person
    visible, `workers` will correctly stay at 0.

    The counts on rows 3-6 are CURRENT-FRAME counts (they reset every frame).
    The `events` row is the cumulative rising-edge total across the run.
    """
    # ---- Build the lines + their colors ------------------------------------
    vest_n      = frame_counts.get("vest",      0)
    no_vest_n   = frame_counts.get("no_vest",   0)
    helmet_n    = frame_counts.get("helmet",    0)
    no_helmet_n = frame_counts.get("no_helmet", 0)
    total_events = sum(event_counts.values())

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
        (f"events: {total_events}",  WHITE),
    ]

    # ---- Layout constants --------------------------------------------------
    x0, y0      = 20, 30        # top-left anchor (y0 = baseline of first text line)
    font        = cv2.FONT_HERSHEY_SIMPLEX
    font_scale  = 0.7
    thickness   = 2
    line_h      = 30            # vertical spacing between baselines
    pad         = 12            # padding inside the dark panel

    # ---- Dynamic background panel sized to longest line --------------------
    max_text_w = max(
        cv2.getTextSize(text, font, font_scale, thickness)[0][0]
        for text, _ in lines
    )
    # Approximate text height (top line baseline at y0 -> top of panel above it)
    panel_left   = x0 - pad
    panel_top    = y0 - line_h + (line_h - pad) // 2 - pad  # extra pad above first line
    panel_top    = max(panel_top, 0)
    panel_right  = x0 + max_text_w + pad
    panel_bottom = y0 + line_h * (len(lines) - 1) + pad

    overlay = frame.copy()
    cv2.rectangle(
        overlay,
        (panel_left, panel_top),
        (panel_right, panel_bottom),
        (0, 0, 0),
        -1,
    )
    cv2.addWeighted(overlay, 0.55, frame, 0.45, 0, frame)

    # ---- Draw each text line ----------------------------------------------
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
    # We load TWO YOLO models:
    #   ppe_model    -> the SafeVision-trained 5-class model. Used for the
    #                   actual PPE classes (vest / no_vest / helmet / no_helmet).
    #   person_model -> stock COCO-trained yolov8n.pt. Used ONLY to count
    #                   workers, because the SafeVision model's own `person`
    #                   class has near-zero recall on real footage.
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

    print(f"[INFO] Loading person detector: {args.person_model}")
    try:
        # If `args.person_model` is just the bare name 'yolov8n.pt' and
        # nothing local matches, Ultralytics will auto-download it (~6 MB).
        person_model = YOLO(args.person_model)
    except Exception as exc:
        print(f"[ERROR] Failed to load person detector: {exc}")
        return 1
    print("[INFO] Person detector loaded.")

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

        # Use 'mp4v' codec (broadly available on Windows with OpenCV)
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        # Use a sensible fps if the source didn't report one (webcams often don't)
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

    # We keep TWO separate counters:
    #   frame_counts -> reset to 0 at the start of every frame. Reflects ONLY
    #                   what is visible in the current frame. Used by the
    #                   "Current" row of the overlay.
    #   event_counts -> rising-edge counter. A class only adds +1 the moment it
    #                   APPEARS in the current frame after being absent in the
    #                   previous frame. This avoids the misleading behaviour of
    #                   a per-frame cumulative counter, which would inflate by
    #                   ~25 per second for any persistent detection.
    #
    # Example: if someone walks into frame wearing a vest and stays there for
    # 10 seconds, `frame_counts['vest']` is 1 the whole time and
    # `event_counts['vest']` increments by exactly 1 (one appearance).
    # If they leave and come back, `event_counts['vest']` becomes 2.
    # We only track events for the overlay classes (no `person`).
    event_classes = ["vest", "no_vest", "helmet", "no_helmet"]
    event_counts: dict = {name: 0 for name in event_classes}
    prev_present: dict = {name: False for name in event_classes}

    frames_processed = 0
    last_t = time.time()
    fps_smoothed = 0.0

    try:
        while True:
            ok, frame = cap.read()
            if not ok or frame is None:
                # End of video file, or webcam read failure
                print("[INFO] No more frames (end of stream).")
                break

            # Run YOLO on the single frame.
            # verbose=False keeps the terminal clean.
            # We run BOTH models on the same frame: PPE first, then person.
            try:
                ppe_results = model.predict(
                    source=frame,
                    conf=args.conf,
                    verbose=False,
                )
            except Exception as exc:
                print(f"[WARN] PPE inference failed on a frame: {exc}")
                continue

            try:
                person_results = person_model.predict(
                    source=frame,
                    conf=args.person_conf,
                    classes=[COCO_PERSON_CLASS_ID],   # only keep `person`
                    verbose=False,
                )
            except Exception as exc:
                print(f"[WARN] Person inference failed on a frame: {exc}")
                person_results = None

            # results is a list; for a single frame we just take the first item
            ppe_result = ppe_results[0]

            # Reset per-frame counts to zero, then let draw_detections fill them in
            # while it draws boxes. This guarantees "Current" reflects ONLY this frame.
            frame_counts: dict = {name: 0 for name in CLASS_NAMES.values()}
            draw_detections(frame, ppe_result, frame_counts)

            # Draw COCO person boxes (labelled 'worker') and get the count
            if person_results is not None:
                workers_n = draw_person_detections(frame, person_results[0])
            else:
                workers_n = 0

            # Rising-edge event tracking: a class scores +1 the FIRST frame it
            # becomes present after a frame in which it was absent.
            for name in event_classes:
                present_now = frame_counts.get(name, 0) > 0
                if present_now and not prev_present[name]:
                    event_counts[name] += 1
                prev_present[name] = present_now

            # FPS (exponential moving average for a smoother number)
            now = time.time()
            dt = now - last_t
            last_t = now
            if dt > 0:
                inst_fps = 1.0 / dt
                fps_smoothed = (
                    inst_fps if fps_smoothed == 0.0 else 0.9 * fps_smoothed + 0.1 * inst_fps
                )

            draw_hud(frame, fps_smoothed, frame_counts, event_counts, workers_n)

            # Show + (optionally) save
            cv2.imshow(win_name, frame)
            if writer is not None:
                writer.write(frame)

            frames_processed += 1

            # 'q' to quit. waitKey(1) is required to actually render the window.
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                print("[INFO] 'q' pressed, exiting.")
                break

            # Also exit if user closed the window via the X button
            if cv2.getWindowProperty(win_name, cv2.WND_PROP_VISIBLE) < 1:
                print("[INFO] Window closed, exiting.")
                break

    except KeyboardInterrupt:
        print("\n[INFO] Interrupted by user (Ctrl+C).")
    except Exception as exc:
        print(f"[ERROR] Unexpected error in main loop: {exc}")
    finally:
        # --- Cleanup --------------------------------------------------------
        cap.release()
        if writer is not None:
            writer.release()
        cv2.destroyAllWindows()

        # --- Summary --------------------------------------------------------
        print("\n" + "=" * 50)
        print("SafeVision AI - run summary")
        print("=" * 50)
        print(f"Frames processed  : {frames_processed}")
        print(f"Avg FPS (smoothed): {fps_smoothed:.2f}")
        print("")
        print("Event totals (one count per appearance, NOT per frame):")
        for name in ["vest", "no_vest", "helmet", "no_helmet"]:
            print(f"  {name:<10}: {event_counts.get(name, 0)}")
        print("")
        print("Note: an 'event' is a rising edge - the class went from absent")
        print("      in the previous frame to present in the current frame.")
        print("      Per-frame live counts are not summarised here.")
        if writer is not None and out_path is not None:
            print(f"Saved output      : {out_path}")
        print("=" * 50)

    return 0


if __name__ == "__main__":
    sys.exit(main())
