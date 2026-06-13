"""
SafeVision AI - Day 5
Local video / webcam PPE detection using the trained 5-class YOLOv8 model.

Usage:
    # Webcam (default)
    python ai-model/inference/video_detection.py

    # Video file with saved output
    python ai-model/inference/video_detection.py --source path/to/video.mp4 --save

    # Custom confidence
    python ai-model/inference/video_detection.py --conf 0.4

Press 'q' in the video window to quit.

Classes (v2 model):
    0 = person
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
    0: (255, 200, 0),    # person       -> cyan-ish
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
        help="Confidence threshold (default: 0.25)",
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help="If set, save annotated output video to ai-model/outputs/video-detections/",
    )
    parser.add_argument(
        "--model",
        default=str(DEFAULT_MODEL),
        help="Path to YOLO weights (default: v2 best.pt)",
    )
    parser.add_argument(
        "--webcam",
        action="store_true",
        help="Use webcam (shorthand for --source 0)",
    )

    args = parser.parse_args()
    # Backwards-friendly: if --webcam specified, treat as --source 0
    if getattr(args, "webcam", False):
        args.source = "0"
    return args


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


def draw_hud(frame, fps: float, frame_counts: dict) -> None:
    """Draw FPS + per-class counts for the CURRENT frame in the top-left corner."""
    h, w = frame.shape[:2]
    pad = 8
    line_h = 18

    # Build lines
    lines = [f"FPS: {fps:.1f}"]
    for cid in sorted(CLASS_NAMES):
        name = CLASS_NAMES[cid]
        lines.append(f"{name}: {frame_counts.get(name, 0)}")

    # Semi-transparent background panel
    panel_w = 160
    panel_h = pad * 2 + line_h * len(lines)
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (panel_w, panel_h), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.5, frame, 0.5, 0, frame)

    # Text
    for i, line in enumerate(lines):
        y = pad + line_h * (i + 1) - 4
        cv2.putText(
            frame,
            line,
            (pad, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
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

    # --- Load model ---------------------------------------------------------
    model_path = Path(args.model)
    if not model_path.exists():
        print(f"[ERROR] Model weights not found: {model_path}")
        return 1

    print(f"[INFO] Loading model: {model_path}")
    try:
        model = YOLO(str(model_path))
    except Exception as exc:
        print(f"[ERROR] Failed to load model: {exc}")
        return 1
    print("[INFO] Model loaded.")

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

    total_counts: dict = {}          # totals across the whole run
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
            try:
                results = model.predict(
                    source=frame,
                    conf=args.conf,
                    verbose=False,
                )
            except Exception as exc:
                print(f"[WARN] Inference failed on a frame: {exc}")
                continue

            # results is a list; for a single frame we just take the first item
            result = results[0]

            # Per-frame counts (for the HUD); totals updated inside draw_detections
            frame_counts: dict = {}
            # Temporarily swap counts dict so draw_detections fills frame_counts
            draw_detections(frame, result, frame_counts)
            # Merge frame counts into total
            for k, v in frame_counts.items():
                total_counts[k] = total_counts.get(k, 0) + v

            # FPS (exponential moving average for a smoother number)
            now = time.time()
            dt = now - last_t
            last_t = now
            if dt > 0:
                inst_fps = 1.0 / dt
                fps_smoothed = (
                    inst_fps if fps_smoothed == 0.0 else 0.9 * fps_smoothed + 0.1 * inst_fps
                )

            draw_hud(frame, fps_smoothed, frame_counts)

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
        print(f"Frames processed : {frames_processed}")
        print(f"Avg FPS (smoothed): {fps_smoothed:.2f}")
        print("Total detections per class (across all frames):")
        for cid in sorted(CLASS_NAMES):
            name = CLASS_NAMES[cid]
            print(f"  {name:<10}: {total_counts.get(name, 0)}")
        if writer is not None and out_path is not None:
            print(f"Saved output    : {out_path}")
        print("=" * 50)

    return 0


if __name__ == "__main__":
    sys.exit(main())