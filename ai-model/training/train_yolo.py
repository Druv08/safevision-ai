"""
SafeVision AI - YOLOv8 training script (Day 3).

This script trains a YOLOv8 model on the Roboflow "Construction Site Safety"
dataset. It supports two modes:

    python ai-model/training/train_yolo.py          -> normal training (30 epochs)
    python ai-model/training/train_yolo.py --smoke  -> quick smoke test (3 epochs)

The smoke test is for verifying that the training pipeline works end-to-end
without spending hours on a full run.

Notes for beginners:
- ultralytics.YOLO loads a pretrained model (yolov8n.pt = nano = smallest).
- `.train(...)` runs training and writes everything (weights, plots, csv)
  into <project>/<name>/.
- Inside that folder you'll find weights/best.pt and weights/last.pt.
"""

import argparse
import sys
from pathlib import Path


# --- Paths -------------------------------------------------------------------

# This file:  ai-model/training/train_yolo.py
# Project root = two parents up (the folder that contains ai-model/)
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent

DATA_YAML = PROJECT_ROOT / "ai-model" / "datasets" / "raw" / "construction-safety-yolo" / "data.yaml"
OUTPUT_DIR = PROJECT_ROOT / "ai-model" / "outputs" / "training-runs"
BASE_MODEL = "yolov8n.pt"  # ultralytics will auto-download if missing

# Training defaults
IMG_SIZE = 640
BATCH_SIZE = 8
NORMAL_EPOCHS = 30
NORMAL_RUN_NAME = "safevision_yolov8n_v1"
SMOKE_EPOCHS = 3
SMOKE_RUN_NAME = "safevision_yolov8n_smoke"


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Train YOLOv8 on SafeVision dataset.")
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Run a quick smoke test (3 epochs) instead of full training.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    # Pick training settings based on mode.
    if args.smoke:
        mode = "SMOKE TEST"
        epochs = SMOKE_EPOCHS
        run_name = SMOKE_RUN_NAME
    else:
        mode = "NORMAL"
        epochs = NORMAL_EPOCHS
        run_name = NORMAL_RUN_NAME

    print("=" * 60)
    print("SafeVision AI - YOLOv8 training")
    print("=" * 60)
    print(f"Dataset path   : {DATA_YAML}")
    print(f"Training mode  : {mode}")
    print(f"Epochs         : {epochs}")
    print(f"Image size     : {IMG_SIZE}")
    print(f"Batch size     : {BATCH_SIZE}")
    print(f"Base model     : {BASE_MODEL}")
    print(f"Output folder  : {OUTPUT_DIR / run_name}")
    print("=" * 60)

    # Safety check: make sure data.yaml exists before doing anything heavy.
    if not DATA_YAML.is_file():
        print(f"\n[ERROR] data.yaml not found at:\n  {DATA_YAML}")
        print("Please make sure the dataset is placed correctly.")
        return 1

    # Import ultralytics here so the script can at least show the path-check
    # error above even if the library isn't installed yet.
    try:
        from ultralytics import YOLO
    except ImportError:
        print("\n[ERROR] ultralytics package is not installed.")
        print("Install it with:  pip install ultralytics")
        return 1

    # Run training inside try/except so we surface errors clearly.
    try:
        print("\nLoading base model...")
        model = YOLO(BASE_MODEL)

        print("Starting training...\n")
        results = model.train(
            data=str(DATA_YAML),
            epochs=epochs,
            imgsz=IMG_SIZE,
            batch=BATCH_SIZE,
            project=str(OUTPUT_DIR),
            name=run_name,
            exist_ok=True,  # overwrite same run name if re-running
        )
    except Exception as exc:
        print(f"\n[ERROR] Training failed: {exc}")
        return 1

    # After training: figure out where things were saved.
    run_dir = OUTPUT_DIR / run_name
    best_pt = run_dir / "weights" / "best.pt"
    last_pt = run_dir / "weights" / "last.pt"

    print("\n" + "=" * 60)
    print("Training completed")
    print("=" * 60)
    print(f"Results folder : {run_dir}")
    print(f"best.pt        : {best_pt}  (exists: {best_pt.is_file()})")
    print(f"last.pt        : {last_pt}  (exists: {last_pt.is_file()})")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
