"""
SafeVision AI - evaluation. Method: docs/evaluation-protocol.md.

1. Detector metrics on a held-out split (made with split_by_camera.py):

    python ai-model/training/evaluate.py detector \\
        --weights ai-model/outputs/training-runs/<run>/weights/best.pt \\
        --data ai-model/datasets/processed/<split>/data.yaml --split test --out metrics.json

   Per-class precision, recall, mAP50 and mAP50-95, plus instance counts.

2. Event metrics on a labelled video, running the same pipeline as the backend
   (association, tracking, time window):

    python ai-model/training/evaluate.py video --video site.mp4 --labels site_events.csv --out events.json

   site_events.csv has one row per ground-truth episode (one person missing
   one item, continuously):
       type,start_s,end_s
       no_helmet,12.0,31.5
       no_vest,40.2,44.0

   Reports event precision and recall, duplicate alerts per episode and
   time-to-alert. Weights default to the backend's (backend/weights.py);
   override with --ppe-model / --helmet-model / --person-model.
"""

import argparse
import csv
import json
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "backend"))


# ---------------------------------------------------------------------------
# Detector metrics
# ---------------------------------------------------------------------------
def metrics_to_dict(m) -> dict:
    """Ultralytics DetMetrics -> plain dict (overall + per class)."""
    mp, mr, map50, map5095 = (float(v) for v in m.mean_results())
    per_class = {}
    for i, c in enumerate(m.ap_class_index):
        p, r, ap50, ap = (float(v) for v in m.class_result(i))
        per_class[m.names[int(c)]] = {
            "instances": int(m.nt_per_class[int(c)]) if m.nt_per_class is not None else None,
            "precision": round(p, 4), "recall": round(r, 4),
            "mAP50": round(ap50, 4), "mAP50-95": round(ap, 4),
        }
    return {
        "precision": round(mp, 4), "recall": round(mr, 4),
        "mAP50": round(map50, 4), "mAP50-95": round(map5095, 4),
        "per_class": per_class,
    }


def evaluate_detector(weights: str, data: str, split: str = "test", imgsz: int = 640) -> dict:
    from ultralytics import YOLO

    m = YOLO(weights).val(data=data, split=split, imgsz=imgsz, plots=False, verbose=False)
    return {"weights": str(weights), "data": str(data), "split": split, **metrics_to_dict(m)}


def print_detector(result: dict) -> None:
    print(f"\n{result['split']} split of {result['data']}")
    print(f"{'class':16}{'inst':>7}{'P':>8}{'R':>8}{'mAP50':>8}{'mAP50-95':>10}")
    for name, c in result["per_class"].items():
        print(f"{name:16}{c['instances'] or '':>7}{c['precision']:8.3f}{c['recall']:8.3f}"
              f"{c['mAP50']:8.3f}{c['mAP50-95']:10.3f}")
    print(f"{'all':16}{'':>7}{result['precision']:8.3f}{result['recall']:8.3f}"
          f"{result['mAP50']:8.3f}{result['mAP50-95']:10.3f}")


# ---------------------------------------------------------------------------
# Event metrics
# ---------------------------------------------------------------------------
@dataclass
class GTEpisode:
    type: str
    start_s: float
    end_s: float
    first_alert_s: float | None = None
    alerts: int = 0


def load_labels(path: Path) -> list[GTEpisode]:
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    out = []
    for r in rows:
        if r["type"] not in ("no_helmet", "no_vest"):
            raise ValueError(f"{path}: unknown type {r['type']!r} (use no_helmet / no_vest)")
        start, end = float(r["start_s"]), float(r["end_s"])
        if end < start:
            raise ValueError(f"{path}: end_s < start_s in {r}")
        out.append(GTEpisode(r["type"], start, end))
    return out


def score_events(alerts: list[tuple[str, float]], gt: list[GTEpisode], window_s: float,
                 tolerance_s: float = 1.0) -> dict:
    """
    Match alerts (type, alert time) to ground-truth episodes.

    An alert matches an episode of the same type if its time is within
    [start - tolerance, end + tolerance]. The first alert on an episode is a
    true positive; further alerts on an already-alerted episode are duplicates;
    alerts matching no episode are false positives. Simultaneous episodes of the
    same type are filled earliest-start first (time-only matching).
    """
    for g in gt:
        g.first_alert_s, g.alerts = None, 0
    fp = dup = 0
    for vtype, t in sorted(alerts, key=lambda a: a[1]):
        cands = [g for g in gt if g.type == vtype and g.start_s - tolerance_s <= t <= g.end_s + tolerance_s]
        if not cands:
            fp += 1
            continue
        fresh = [g for g in cands if g.first_alert_s is None]
        g = min(fresh, key=lambda g: g.start_s) if fresh else min(cands, key=lambda g: abs(g.start_s - t))
        g.alerts += 1
        if fresh:
            g.first_alert_s = t
        else:
            dup += 1

    tp = sum(g.first_alert_s is not None for g in gt)
    alertable = [g for g in gt if g.end_s - g.start_s >= window_s]
    delays = [g.first_alert_s - g.start_s for g in gt if g.first_alert_s is not None]

    def ratio(a, b):
        return round(a / b, 4) if b else None

    return {
        "ground_truth_episodes": len(gt),
        "alertable_episodes": len(alertable),  # long enough to satisfy the window
        "alerts": len(alerts),
        "true_positives": tp,
        "false_positives": fp,
        "duplicate_alerts": dup,
        "precision": ratio(tp, len(alerts)),  # duplicates count against precision
        "precision_ignoring_duplicates": ratio(tp + dup, len(alerts)),
        "recall": ratio(tp, len(gt)),
        "recall_alertable": ratio(sum(g.first_alert_s is not None for g in alertable), len(alertable)),
        "duplicates_per_detected_episode": ratio(dup, tp),
        "time_to_alert_s": {
            "mean": round(statistics.mean(delays), 2) if delays else None,
            "median": round(statistics.median(delays), 2) if delays else None,
            "max": round(max(delays), 2) if delays else None,
        },
    }


def evaluate_video(args) -> dict:
    import weights as default_weights
    from services.pipeline import Detector, Pipeline, PipelineConfig, load_yolo, run_video
    from services.tracker import PersonTracker

    paths = {
        "ppe": args.ppe_model or str(default_weights.resolve("PPE_MODEL_PATH")),
        "helmet": args.helmet_model or str(default_weights.resolve("HELMET_MODEL_PATH")),
        "person": args.person_model or str(default_weights.resolve("PERSON_MODEL_PATH")),
    }
    loaded = {}
    for p in paths.values():
        if p not in loaded:
            loaded[p] = load_yolo(p)  # .pt or .onnx
    detector = Detector(loaded[paths["ppe"]], loaded[paths["helmet"]], loaded[paths["person"]],
                        ppe_conf=args.conf, person_conf=args.person_conf)
    cfg = PipelineConfig(window_s=args.window, clear_s=args.clear)
    run = run_video(args.video, Pipeline(detector, cfg, PersonTracker(args.tracker)))

    gt = load_labels(args.labels)
    scores = {"overall": score_events([(e.type, e.alert_s) for e in run.episodes], gt, args.window, args.tolerance)}
    for vtype in ("no_helmet", "no_vest"):
        scores[vtype] = score_events(
            [(e.type, e.alert_s) for e in run.episodes if e.type == vtype],
            [g for g in gt if g.type == vtype], args.window, args.tolerance,
        )
    return {
        "video": str(args.video), "labels": str(args.labels), "weights": paths, "pose": detector.uses_pose,
        "config": {"window_s": args.window, "clear_s": args.clear, "tolerance_s": args.tolerance,
                   "tracker": args.tracker, "ppe_conf": args.conf, "person_conf": args.person_conf},
        "frames": run.frames, "duration_s": round(run.duration_s, 2),
        "scores": scores,
        "alerts": [{"type": e.type, "track_id": e.track_id, "start_s": round(e.start_s, 2),
                    "alert_s": round(e.alert_s, 2), "end_s": round(e.end_s, 2),
                    "confidence": round(e.confidence, 3)} for e in run.episodes],
        "ground_truth": [{"type": g.type, "start_s": g.start_s, "end_s": g.end_s,
                          "first_alert_s": g.first_alert_s, "alerts": g.alerts} for g in gt],
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("detector", help="per-class P/R/mAP on a held-out split")
    d.add_argument("--weights", required=True)
    d.add_argument("--data", required=True, help="data.yaml (from split_by_camera.py)")
    d.add_argument("--split", default="test")
    d.add_argument("--imgsz", type=int, default=640)
    d.add_argument("--out", type=Path)

    v = sub.add_parser("video", help="event precision / recall on a labelled video")
    v.add_argument("--video", type=Path, required=True)
    v.add_argument("--labels", type=Path, required=True, help="CSV: type,start_s,end_s")
    v.add_argument("--ppe-model")
    v.add_argument("--helmet-model")
    v.add_argument("--person-model")
    v.add_argument("--conf", type=float, default=0.4)
    v.add_argument("--person-conf", type=float, default=0.4)
    v.add_argument("--window", type=float, default=2.0)
    v.add_argument("--clear", type=float, default=1.0)
    v.add_argument("--tolerance", type=float, default=1.0, help="label timing slack in seconds")
    v.add_argument("--tracker", choices=["bytetrack", "botsort"], default="bytetrack")
    v.add_argument("--out", type=Path)
    args = ap.parse_args(argv)

    if args.cmd == "detector":
        result = evaluate_detector(args.weights, args.data, args.split, args.imgsz)
        print_detector(result)
    else:
        result = evaluate_video(args)
        print(json.dumps(result["scores"], indent=2))
    if args.out:
        args.out.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
