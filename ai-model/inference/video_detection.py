"""
SafeVision AI - local video / webcam PPE detection.

A thin front end for the shared pipeline in backend/services/pipeline.py, so
the CLI, the backend and evaluation all apply the same rules:

  * persons, helmets and vests are detected per frame,
  * each helmet / vest (or no_helmet / no_vest) box is given to one person using
    head and torso regions from pose keypoints (box geometry as fallback),
  * each person keeps a track ID (ByteTrack or BoT-SORT),
  * a violation is raised only after the same person has been missing an item
    for --window seconds (default 2), and each episode is reported once.

The window shows each person as "#<id> H:<helmet> V:<vest>" where the state is
ok (worn), NO (missing) or ? (not visible). Red = violating, green = compliant.

Usage:
    # Webcam (default)
    python ai-model/inference/video_detection.py

    # Video file, save the annotated output
    python ai-model/inference/video_detection.py --source path/to/video.mp4 --save

    # Other weights / rules
    python ai-model/inference/video_detection.py --helmet-model path/to/best.pt --window 3 --tracker botsort

Default weights are the same as the backend's (backend/weights.py, overridable
with PPE_MODEL_PATH / HELMET_MODEL_PATH / PERSON_MODEL_PATH). Press 'q' to quit.
To also log screenshots + CSV, use violation_detection.py.
"""

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

import cv2

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

import weights  # noqa: E402
from services.pipeline import (  # noqa: E402
    TYPE_LABELS,
    Detector,
    Pipeline,
    PipelineConfig,
    compliance,
    draw,
    load_yolo,
    video_frames,
)
from services.tracker import PersonTracker  # noqa: E402

OUTPUT_DIR = PROJECT_ROOT / "ai-model" / "outputs" / "video-detections"


def build_parser(description: str = "SafeVision AI - local PPE detection") -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=description)
    p.add_argument("--source", default="0", help="Webcam index (default 0) or path to a video file")
    p.add_argument("--model", default=str(weights.resolve("PPE_MODEL_PATH")), help="PPE (vest) weights")
    p.add_argument("--helmet-model", default=str(weights.resolve("HELMET_MODEL_PATH")), help="Helmet weights")
    p.add_argument("--person-model", default=str(weights.resolve("PERSON_MODEL_PATH")),
                   help="Person weights; a -pose model enables keypoint head/torso regions")
    p.add_argument("--conf", type=float, default=0.4, help="PPE confidence threshold (default 0.4)")
    p.add_argument("--person-conf", type=float, default=0.4, help="Person confidence threshold (default 0.4)")
    p.add_argument("--window", type=float, default=2.0, help="Seconds of violation before an alert (default 2)")
    p.add_argument("--clear", type=float, default=1.0, help="Seconds without violation that end it (default 1)")
    p.add_argument("--tracker", choices=["bytetrack", "botsort"], default="bytetrack")
    p.add_argument("--save", action="store_true", help=f"Save the annotated video under {OUTPUT_DIR}")
    p.add_argument("--no-show", action="store_true", help="Do not open a window (e.g. on a server)")
    return p


def load_detector(args) -> Detector:
    models = {}
    for path in (args.model, args.helmet_model, args.person_model):
        if path not in models:
            if not Path(path).is_file():
                sys.exit(f"[ERROR] weights not found: {path}")
            models[path] = load_yolo(path)  # .pt or .onnx
    return Detector(models[args.model], models[args.helmet_model], models[args.person_model],
                    ppe_conf=args.conf, person_conf=args.person_conf)


def frames(source: str):
    """(time_s, frame, fps): webcam time is wall-clock, a file uses its own timestamps."""
    cap = cv2.VideoCapture(int(source) if source.isdigit() else source)
    if not cap.isOpened():
        sys.exit(f"[ERROR] cannot open source {source!r}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    try:
        if source.isdigit():
            t0 = time.monotonic()
            while True:
                ok, frame = cap.read()
                if not ok:
                    return
                yield time.monotonic() - t0, frame, fps
        else:
            for t, frame in video_frames(cap):
                yield t, frame, fps
    finally:
        cap.release()


def _hud(img, result, fps: float, alerts: int) -> None:
    s = result.summary
    text = (f"FPS {fps:4.1f} | people {s['total_persons']} | no helmet {s['no_helmet']} | "
            f"no vest {s['no_vest']} | alerts {alerts}")
    cv2.rectangle(img, (0, 0), (img.shape[1], 26), (0, 0, 0), -1)
    cv2.putText(img, text, (8, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)


def describe(ep) -> str:
    label = TYPE_LABELS[ep.type][0]
    return f"{label} | person #{ep.track_id} | {ep.start_s:.1f}s-{ep.end_s:.1f}s | conf {ep.confidence:.2f}"


def run(args, on_open=None, on_close=None) -> int:
    """Run the shared pipeline on args.source. Callbacks get each Episode when it opens / ends."""
    detector = load_detector(args)
    print(f"[INFO] person model: {args.person_model} ({'pose keypoints' if detector.uses_pose else 'boxes only'})")
    print(f"[INFO] helmet model: {args.helmet_model}")
    print(f"[INFO] PPE model   : {args.model}")
    pipe = Pipeline(detector, PipelineConfig(window_s=args.window, clear_s=args.clear), PersonTracker(args.tracker))

    writer, alerts, observations, last, smoothed = None, 0, [], time.monotonic(), 0.0
    try:
        for t, frame, src_fps in frames(args.source):
            result = pipe.process(frame, t)
            observations += result.observations
            for ep in result.opened:
                alerts += 1
                print(f"[ALERT] {datetime.now():%H:%M:%S} {TYPE_LABELS[ep.type][0]} | person #{ep.track_id}")
                if on_open:
                    on_open(ep)
            for ep in result.closed:
                print(f"[EVENT] {describe(ep)}")
                if on_close:
                    on_close(ep)

            now = time.monotonic()
            smoothed = 0.9 * smoothed + 0.1 * (1.0 / max(now - last, 1e-6))
            last = now
            img = draw(frame, result)
            _hud(img, result, smoothed, alerts)

            if args.save:
                if writer is None:
                    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
                    out = OUTPUT_DIR / f"detections_{datetime.now():%Y%m%d_%H%M%S}.mp4"
                    writer = cv2.VideoWriter(str(out), cv2.VideoWriter_fourcc(*"mp4v"), src_fps,
                                             (img.shape[1], img.shape[0]))
                    print(f"[INFO] saving annotated video -> {out}")
                writer.write(img)
            if not args.no_show:
                cv2.imshow("SafeVision AI", img)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
                if cv2.getWindowProperty("SafeVision AI", cv2.WND_PROP_VISIBLE) < 1:
                    break
    except KeyboardInterrupt:
        pass
    finally:
        if writer is not None:
            writer.release()
        cv2.destroyAllWindows()

    closed, obs = pipe.finish()
    for ep in closed:
        print(f"[EVENT] {describe(ep)}")
        if on_close:
            on_close(ep)
    observations += obs
    print(f"\nAlerts: {alerts}   people tracked: {len({o.track_id for o in observations})}")
    for item, c in compliance(observations).items():
        rate = "n/a" if c["rate"] is None else f"{c['rate']:.0%}"
        print(f"{item:6} compliance {rate}  (compliant {c['compliant']}, violation {c['violation']}, "
              f"unknown {c['unknown']})")
    return 0


if __name__ == "__main__":
    sys.exit(run(build_parser().parse_args()))
