"""
SafeVision AI - Webcam frame capture for building a domain-matched dataset.

Why this exists
---------------
The trained PPE model detects helmets well on construction-site images but
struggles on the live webcam (close-up, indoor, headset, different helmet).
That is a DOMAIN-SHIFT problem: the fix is to give the model training images
that look like YOUR webcam. This tool just grabs raw frames from the webcam so
you can label them (e.g. in Roboflow) and fold them into a new dataset.

It does NOT run any model, label anything, or train. It only saves images.

What to capture (aim ~200-300 frames total, with variety):
    helmet     : helmet worn - front/left/right/tilted, near/far,
                 WITH and WITHOUT the headset, different lighting
    no_helmet  : bare head - same angles/distances, with/without headset
    held       : helmet held in hand or on the desk (not worn)
    empty      : empty room (hard negatives)

Usage
-----
    # Manual: press SPACE to grab a frame, 'q' to quit.
    python ai-model/inference/capture_webcam_frames.py --label helmet

    # Auto: grab one frame every 0.7s (move around slowly while it runs).
    python ai-model/inference/capture_webcam_frames.py --label no_helmet --every 0.7

    # Pick a different camera or output root.
    python ai-model/inference/capture_webcam_frames.py --label helmet --source 1

Frames are saved to:
    ai-model/datasets/raw/webcam-capture/<label>/<label>_<timestamp>_<n>.jpg

Then upload that folder to Roboflow, label helmet / no_helmet, export YOLOv8,
and tell me to merge it into a v5 build.
"""

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

import cv2


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_ROOT = PROJECT_ROOT / "ai-model" / "datasets" / "raw" / "webcam-capture"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Capture raw webcam frames for dataset building (no model)."
    )
    p.add_argument("--label", default="helmet",
                   help="Category for these frames (e.g. helmet, no_helmet, "
                        "held, empty). Used as the subfolder + filename prefix.")
    p.add_argument("--source", default="0",
                   help="Webcam index ('0' default) or a video file path.")
    p.add_argument("--out", default=str(DEFAULT_OUT_ROOT),
                   help="Output root folder (a <label> subfolder is created).")
    p.add_argument("--every", type=float, default=0.0,
                   help="Auto-capture interval in seconds. 0 (default) = manual "
                        "mode: press SPACE to grab each frame.")
    p.add_argument("--max", type=int, default=0,
                   help="Stop after this many frames (0 = unlimited).")
    return p.parse_args()


def main() -> int:
    args = parse_args()

    source = int(args.source) if args.source.isdigit() else args.source
    out_dir = Path(args.out) / args.label
    out_dir.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        print(f"[ERROR] Could not open webcam/source: {args.source}")
        return 1

    auto = args.every > 0.0
    win = "SafeVision capture - SPACE=grab  q=quit"
    cv2.namedWindow(win, cv2.WINDOW_NORMAL)

    print("=" * 64)
    print("SafeVision AI - webcam capture")
    print("=" * 64)
    print(f"Label / folder : {args.label}  ->  {out_dir}")
    print(f"Mode           : {'AUTO every %.2fs' % args.every if auto else 'MANUAL (press SPACE)'}")
    print(f"Max frames     : {args.max if args.max else 'unlimited'}")
    print("Press 'q' (or close the window) to stop.")
    print("=" * 64)

    saved = 0
    last_grab = 0.0
    ts_run = datetime.now().strftime("%Y%m%d_%H%M%S")

    try:
        while True:
            ok, frame = cap.read()
            if not ok or frame is None:
                print("[INFO] No more frames / camera read failed.")
                break

            now = time.time()
            do_grab = False

            # Live overlay so you can see the count + mode while moving.
            view = frame.copy()
            txt = f"{args.label}  saved={saved}  {'AUTO' if auto else 'SPACE to grab'}"
            cv2.rectangle(view, (8, 8), (8 + 9 * len(txt), 40), (0, 0, 0), -1)
            cv2.putText(view, txt, (14, 32), cv2.FONT_HERSHEY_SIMPLEX,
                        0.7, (0, 255, 255), 2, cv2.LINE_AA)
            cv2.imshow(win, view)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                print("[INFO] 'q' pressed, stopping.")
                break
            if cv2.getWindowProperty(win, cv2.WND_PROP_VISIBLE) < 1:
                print("[INFO] Window closed, stopping.")
                break

            if auto:
                if (now - last_grab) >= args.every:
                    do_grab = True
            elif key == ord(" "):
                do_grab = True

            if do_grab:
                fname = f"{args.label}_{ts_run}_{saved:04d}.jpg"
                # Save the CLEAN frame (no overlay) for labeling.
                if cv2.imwrite(str(out_dir / fname), frame):
                    saved += 1
                    last_grab = now
                    print(f"  saved {saved:4d}: {fname}")
                else:
                    print(f"  [WARN] failed to save {fname}")

            if args.max and saved >= args.max:
                print(f"[INFO] Reached --max {args.max} frames.")
                break

    except KeyboardInterrupt:
        print("\n[INFO] Interrupted (Ctrl+C).")
    finally:
        cap.release()
        cv2.destroyAllWindows()

    print("=" * 64)
    print(f"Done. {saved} frames saved to: {out_dir}")
    print("Next: upload this folder to Roboflow, label helmet / no_helmet,")
    print("      export as YOLOv8, then ask me to merge it into a v5 build.")
    print("=" * 64)
    return 0


if __name__ == "__main__":
    sys.exit(main())
