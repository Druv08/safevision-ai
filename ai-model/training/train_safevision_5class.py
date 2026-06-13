"""
train_safevision_5class.py
--------------------------
Train YOLOv8n on the processed SafeVision 5-class dataset.

Final class order:
0 = person
1 = helmet
2 = no_helmet
3 = vest
4 = no_vest

Run modes:
  python ai-model/training/train_safevision_5class.py --smoke
  python ai-model/training/train_safevision_5class.py --fast
  python ai-model/training/train_safevision_5class.py
"""

from __future__ import annotations

import argparse
import sys
import traceback
from pathlib import Path


# --- Paths -------------------------------------------------------------------

# Project root = the folder that contains ai-model/
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent

DATA_YAML = PROJECT_ROOT / "ai-model" / "datasets" / "processed" / "safevision-ppe-5class" / "data.yaml"
OUTPUT_DIR = PROJECT_ROOT / "ai-model" / "outputs" / "training-runs"
BASE_MODEL = "yolov8n.pt"


# --- Training presets --------------------------------------------------------

IMG_SIZE = 640
BATCH_SIZE = 8

SMOKE_EPOCHS = 1
SMOKE_RUN_NAME = "safevision_yolov8n_5class_smoke"

FAST_EPOCHS = 10
FAST_RUN_NAME = "safevision_yolov8n_5class_fast"

NORMAL_EPOCHS = 30
NORMAL_RUN_NAME = "safevision_yolov8n_5class_v2"


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Train YOLOv8n on the SafeVision 5-class dataset.")
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Run a 1-epoch smoke test.",
    )
    parser.add_argument(
        "--fast",
        action="store_true",
        help="Run a faster 10-epoch training job.",
    )
    return parser.parse_args()


def resolve_mode(args: argparse.Namespace) -> tuple[str, int, str]:
    """Pick the run mode and training settings from CLI flags."""
    if args.smoke:
        return "SMOKE", SMOKE_EPOCHS, SMOKE_RUN_NAME
    if args.fast:
        return "FAST", FAST_EPOCHS, FAST_RUN_NAME
    return "NORMAL", NORMAL_EPOCHS, NORMAL_RUN_NAME


def print_banner(mode: str, epochs: int, run_name: str) -> None:
    """Print the selected settings before training starts."""
    print("=" * 72)
    print("SafeVision AI - YOLOv8n 5-class training")
    print("=" * 72)
    print(f"Dataset path   : {DATA_YAML}")
    print(f"Training mode  : {mode}")
    print(f"Epochs         : {epochs}")
    print(f"Image size     : {IMG_SIZE}")
    print(f"Batch size     : {BATCH_SIZE}")
    print(f"Output folder  : {OUTPUT_DIR / run_name}")
    print("Base model     : yolov8n.pt")
    print("Warning        : CPU training may take a long time because the dataset has 5987 train images.")
    print("=" * 72)


def main() -> int:
    """Train the model and print the saved artifact paths."""
    args = parse_args()
    mode, epochs, run_name = resolve_mode(args)
    fraction = 0.02 if args.smoke else 1.0

    print_banner(mode, epochs, run_name)
    if args.smoke:
        print(f"Smoke fraction: {fraction:.2%} of the processed dataset")

    # Make sure the processed dataset YAML exists before importing or training.
    if not DATA_YAML.is_file():
        print(f"\n[ERROR] Dataset YAML not found:\n  {DATA_YAML}")
        print("The trainer expects the processed 5-class dataset to already be built.")
        return 1

    try:
        from ultralytics import YOLO
    except ImportError:
        print("\n[ERROR] ultralytics is not installed in the current Python environment.")
        return 1

    try:
        # Load the small YOLOv8 base model so the 5-class head can be trained.
        model = YOLO(BASE_MODEL)

        print("\nStarting training...")
        results = model.train(
            data=str(DATA_YAML),
            epochs=epochs,
            imgsz=IMG_SIZE,
            batch=BATCH_SIZE,
            fraction=fraction,
            project=str(OUTPUT_DIR),
            name=run_name,
            exist_ok=True,
        )
    except Exception as exc:
        print(f"\n[ERROR] Training failed: {exc}")
        print(traceback.format_exc())
        return 1

    # Ultralytics saves the run folder under project/name.
    run_dir = OUTPUT_DIR / run_name
    results_dir = Path(getattr(results, "save_dir", run_dir))
    best_pt = results_dir / "weights" / "best.pt"
    last_pt = results_dir / "weights" / "last.pt"

    print("\n" + "=" * 72)
    print("Training completed")
    print("=" * 72)
    print(f"best.pt path    : {best_pt}")
    print(f"last.pt path    : {last_pt}")
    print(f"results folder  : {results_dir}")
    print("=" * 72)

    return 0


if __name__ == "__main__":
    sys.exit(main())