"""
Import a legacy violations CSV and its screenshots into Supabase.

Handles both formats that older versions wrote (they may be mixed in one file):
  * backend:  8 columns, no header
      violation_id,timestamp,source,frame_number,violation_type,severity,confidence,screenshot_path
  * CLI:      9 columns with a header (adds worker_detected before screenshot_path)

Re-running is safe: rows already imported (matched by legacy id in `note`) are skipped.

Usage, from backend/:
    python -m scripts.migrate_csv ../ai-model/outputs/violations/violations_log.csv
    python -m scripts.migrate_csv log.csv --screenshots-dir ../ai-model/outputs/violations/screenshots --dry-run
"""

import argparse
import csv
import logging
import sys
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

from config import PROJECT_ROOT
from services import storage_service
from services.violations_service import create_violation
from supabase_client import get_supabase

log = logging.getLogger("migrate_csv")

BACKEND_COLUMNS = [
    "violation_id", "timestamp", "source", "frame_number",
    "violation_type", "severity", "confidence", "screenshot_path",
]
CLI_COLUMNS = BACKEND_COLUMNS[:7] + ["worker_detected", "screenshot_path"]

LABEL_TO_TYPES = {
    "Helmet Missing": ["no_helmet"],
    "Safety Vest Missing": ["no_vest"],
    "Multiple PPE Missing": ["no_helmet", "no_vest"],
}
NOTE_PREFIX = "migrated from CSV, legacy id "
MODEL_VERSION = "legacy-csv"


def read_rows(csv_path: Path):
    """Yield one dict per data row, whichever format the row is in."""
    with csv_path.open(newline="", encoding="utf-8") as f:
        for line_no, cells in enumerate(csv.reader(f), start=1):
            if not cells or cells[0] == "violation_id":  # blank line or a header row
                continue
            if len(cells) == len(CLI_COLUMNS):
                yield line_no, dict(zip(CLI_COLUMNS, cells, strict=True))
            elif len(cells) == len(BACKEND_COLUMNS):
                yield line_no, dict(zip(BACKEND_COLUMNS, cells, strict=True))
            else:
                log.warning("line %d: %d columns, expected 8 or 9; skipped", line_no, len(cells))


def parse_timestamp(value: str) -> datetime:
    """Backend wrote 2026-06-06_23-39-07, the CLI wrote ISO. Both are local time."""
    try:
        dt = datetime.strptime(value, "%Y-%m-%d_%H-%M-%S")
    except ValueError:
        dt = datetime.fromisoformat(value)
    return dt if dt.tzinfo else dt.astimezone()


def source_kind(source: str) -> str:
    ext = Path(source).suffix.lower()
    if ext in (".jpg", ".jpeg", ".png"):
        return "image"
    if ext in (".mp4", ".avi", ".mov", ".mkv", ".webm"):
        return "video"
    return "camera"  # webcam index ("0") or stream description


def find_screenshot(recorded: str, csv_path: Path, screenshots_dir: Path | None) -> Path | None:
    if not recorded:
        return None
    name = Path(recorded.replace("\\", "/")).name
    candidates = [screenshots_dir / name] if screenshots_dir else []
    candidates += [Path(recorded), PROJECT_ROOT / recorded, csv_path.parent / "screenshots" / name]
    return next((p for p in candidates if p.is_file()), None)


def jpeg_bytes(path: Path) -> bytes:
    data = path.read_bytes()
    if data.startswith(b"\xff\xd8\xff"):
        return data
    frame = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if frame is None:
        raise ValueError(f"{path} is not a readable image")
    return cv2.imencode(".jpg", frame)[1].tobytes()


def already_imported() -> set[str]:
    res = get_supabase().table("violations").select("note").like("note", f"{NOTE_PREFIX}%").execute()
    return {r["note"] for r in res.data}


def migrate(csv_path: Path, screenshots_dir: Path | None = None, dry_run: bool = False) -> dict:
    stats = {"imported": 0, "skipped_existing": 0, "skipped_invalid": 0, "missing_screenshot": 0}
    done = set() if dry_run else already_imported()

    for line_no, row in read_rows(csv_path):
        try:
            vtypes = LABEL_TO_TYPES[row["violation_type"]]
            created_at = parse_timestamp(row["timestamp"])
            confidence = float(row["confidence"])
        except (KeyError, ValueError) as e:
            log.warning("line %d: invalid row (%s); skipped", line_no, e)
            stats["skipped_invalid"] += 1
            continue

        shot = find_screenshot(row["screenshot_path"], csv_path, screenshots_dir)
        if shot is None:
            log.warning("line %d: screenshot not found (%s)", line_no, row["screenshot_path"])
            stats["missing_screenshot"] += 1

        for vtype in vtypes:
            note = f"{NOTE_PREFIX}{row['violation_id']}" + (f" ({vtype})" if len(vtypes) > 1 else "")
            if note in done:
                stats["skipped_existing"] += 1
                continue
            if dry_run:
                stats["imported"] += 1
                continue
            # Each row gets its own object, so deleting one never breaks another.
            key = storage_service.upload_screenshot(jpeg_bytes(shot)) if shot else None
            create_violation(vtype, confidence, source_kind(row["source"]), key, MODEL_VERSION, created_at, note)
            done.add(note)
            stats["imported"] += 1

    return stats


def main(argv=None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("csv_path", type=Path)
    parser.add_argument("--screenshots-dir", type=Path, help="look up screenshots here by file name first")
    parser.add_argument("--dry-run", action="store_true", help="parse and report without writing to Supabase")
    args = parser.parse_args(argv)

    if not args.csv_path.is_file():
        log.error("%s not found", args.csv_path)
        return 1
    stats = migrate(args.csv_path, args.screenshots_dir, args.dry_run)
    log.info("Done%s: %s", " (dry run)" if args.dry_run else "", stats)
    return 0


if __name__ == "__main__":
    sys.exit(main())
