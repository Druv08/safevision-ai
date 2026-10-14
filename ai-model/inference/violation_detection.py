"""
SafeVision AI - local PPE violation logging (screenshots + CSV).

Runs exactly what video_detection.py runs (the shared pipeline in
backend/services/pipeline.py) and also records every violation episode:

  * screenshot -> ai-model/outputs/violations/screenshots/, saved when the
                  alert is raised (annotated; the violating person in amber)
  * CSV row    -> ai-model/outputs/violations/violation_episodes.csv, written
                  when the episode ends, one row per person per missing item

CSV columns:
    violation_id, timestamp (alert time, local ISO), source, track_id,
    violation_type, severity, confidence, start_s, end_s, duration_s, screenshot_path

start_s / end_s are seconds from the start of the video (or of the webcam
session). backend/scripts/migrate_csv.py can import this file into Supabase.

Usage:
    python ai-model/inference/violation_detection.py                       # webcam
    python ai-model/inference/violation_detection.py --source clip.mp4 --no-show
    python ai-model/inference/violation_detection.py --window 3 --save

All detection options are the same as video_detection.py (see --help).
"""

import csv
import sys
import uuid
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from video_detection import PROJECT_ROOT, TYPE_LABELS, build_parser, run  # noqa: E402

VIOLATIONS_DIR = PROJECT_ROOT / "ai-model" / "outputs" / "violations"
SCREENSHOTS_DIR = VIOLATIONS_DIR / "screenshots"
CSV_PATH = VIOLATIONS_DIR / "violation_episodes.csv"
CSV_COLUMNS = [
    "violation_id", "timestamp", "source", "track_id", "violation_type", "severity",
    "confidence", "start_s", "end_s", "duration_s", "screenshot_path",
]


def main() -> int:
    args = build_parser("SafeVision AI - PPE violation logging").parse_args()
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    if not CSV_PATH.exists() or CSV_PATH.stat().st_size == 0:
        with CSV_PATH.open("w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(CSV_COLUMNS)

    pending = {}  # id(episode) -> (violation_id, alert wall time, screenshot path)

    def on_open(ep):
        vid = uuid.uuid4().hex[:12]
        now = datetime.now()
        shot = SCREENSHOTS_DIR / f"{now:%Y-%m-%d_%H-%M-%S}_{vid}_{ep.type}.jpg"
        if ep.snapshot:
            shot.write_bytes(ep.snapshot)
        pending[id(ep)] = (vid, now, shot if ep.snapshot else None)
        print(f"[SAVE] screenshot -> {shot.name}")

    def on_close(ep):
        vid, alerted_at, shot = pending.pop(id(ep))
        label, severity = TYPE_LABELS[ep.type]
        with CSV_PATH.open("a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow([
                vid, alerted_at.isoformat(timespec="seconds"), args.source, ep.track_id, label, severity,
                f"{ep.confidence:.3f}", f"{ep.start_s:.2f}", f"{ep.end_s:.2f}", f"{ep.end_s - ep.start_s:.2f}",
                str(shot.relative_to(PROJECT_ROOT)).replace("\\", "/") if shot else "",
            ])

    code = run(args, on_open, on_close)
    print(f"CSV log      : {CSV_PATH}")
    print(f"Screenshots  : {SCREENSHOTS_DIR}")
    return code


if __name__ == "__main__":
    sys.exit(main())
