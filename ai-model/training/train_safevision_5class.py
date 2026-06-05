"""
SafeVision AI - YOLOv8 training script for the merged 5-class dataset.

Classes (final):
    0 = person
    1 = helmet
    2 = no_helmet
    3 = vest
    4 = no_vest

Modes:
    python ai-model/training/train_safevision_5class.py            # normal (30 epochs)
    python ai-model/training/train_safevision_5class.py --smoke    # smoke test (1 epoch)
    python ai-model/training/train_safevision_5class.py --fast     # fast run (10 epochs)
    python ai-model/training/train_safevision_5class.py --resume   # resume normal run from last.pt
    python ai-model/training/train_safevision_5class.py --fast --resume   # resume the fast run

Output goes to: ai-model/outputs/training-runs/<run_name>/

Pause/resume:
    - To pause: press Ctrl+C in the training terminal.
      YOLO keeps the latest checkpoint at <run_dir>/weights/last.pt
      after each completed epoch.
    - To resume: re-run the same mode with --resume.
      Training continues from last.pt until the original epoch count
      is reached. Do NOT delete the run folder or last.pt while paused.
"""

import argparse
import sys
import time
from pathlib import Path


# --- Paths -------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent

DATA_YAML = (
    PROJECT_ROOT
    / "ai-model" / "datasets" / "processed"
    / "safevision-ppe-5class" / "data.yaml"
)
OUTPUT_DIR = PROJECT_ROOT / "ai-model" / "outputs" / "training-runs"
BASE_MODEL = "yolov8n.pt"  # ultralytics auto-downloads if missing

# Shared training hyperparameters
IMG_SIZE = 640
BATCH_SIZE = 8

# Per-mode settings
MODES = {
    "smoke":  {"epochs": 1,  "name": "safevision_yolov8n_5class_smoke"},
    "fast":   {"epochs": 10, "name": "safevision_yolov8n_5class_fast"},
    "normal": {"epochs": 30, "name": "safevision_yolov8n_5class_v2"},
}


def parse_args() -> argparse.Namespace:
    """Parse CLI flags. Default = normal mode."""
    parser = argparse.ArgumentParser(
        description="Train YOLOv8n on SafeVision 5-class PPE dataset."
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--smoke",
        action="store_true",
        help="Smoke test: 1 epoch, just to verify the pipeline runs.",
    )
    group.add_argument(
        "--fast",
        action="store_true",
        help="Fast run: 10 epochs (compromise between smoke and full).",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume the selected mode from its last.pt checkpoint.",
    )
    return parser.parse_args()


def pick_mode(args: argparse.Namespace) -> str:
    if args.smoke:
        return "smoke"
    if args.fast:
        return "fast"
    return "normal"


def main() -> int:
    args = parse_args()
    mode = pick_mode(args)
    epochs = MODES[mode]["epochs"]
    run_name = MODES[mode]["name"]
    run_dir = OUTPUT_DIR / run_name
    last_pt = run_dir / "weights" / "last.pt"

    # Resume mode requires a prior last.pt to exist.
    if args.resume and not last_pt.is_file():
        print("=" * 70)
        print("[ERROR] --resume was passed but no checkpoint was found at:")
        print(f"  {last_pt}")
        print("Either start a fresh run (drop --resume) or pick the right mode.")
        print("=" * 70)
        return 1

    print("=" * 70)
    print("SafeVision AI - YOLOv8 training (5-class)")
    print("=" * 70)
    print(f"Dataset path   : {DATA_YAML}")
    print(f"Training mode  : {mode.upper()}{' (RESUME)' if args.resume else ''}")
    print(f"Epochs (target): {epochs}")
    print(f"Image size     : {IMG_SIZE}")
    print(f"Batch size     : {BATCH_SIZE}")
    print(f"Base model     : {BASE_MODEL if not args.resume else last_pt}")
    print(f"Output folder  : {run_dir}")
    print("=" * 70)
    print("[WARNING] This dataset has ~5,987 training images.")
    print("[WARNING] CPU training will be SLOW (estimate: ~1-2 min/epoch smoke,")
    print("          and many hours for the full 30-epoch run on CPU).")
    print("=" * 70)

    # Safety check: dataset YAML must exist
    if not DATA_YAML.is_file():
        print(f"\n[ERROR] data.yaml not found at:\n  {DATA_YAML}")
        print("Run the dataset builder first:")
        print("  python ai-model/training/build_safevision_5class_dataset.py")
        return 1

    # Import ultralytics lazily so path-check errors still display cleanly
    try:
        from ultralytics import YOLO
    except ImportError:
        print("\n[ERROR] ultralytics package is not installed.")
        print("Install it with:  pip install ultralytics")
        return 1

    # Run training inside try/except so failures surface clearly
    start = time.time()
    try:
        if args.resume:
            print(f"\nResuming from checkpoint: {last_pt}")
            model = YOLO(str(last_pt))
            print("Continuing training...\n")
            # When resume=True, ultralytics re-uses the original training
            # config stored alongside the run (epochs, imgsz, batch, etc.).
            model.train(resume=True)
        else:
            print("\nLoading base model...")
            model = YOLO(BASE_MODEL)

            print("Starting training...\n")
            model.train(
                data=str(DATA_YAML),
                epochs=epochs,
                imgsz=IMG_SIZE,
                batch=BATCH_SIZE,
                project=str(OUTPUT_DIR),
                name=run_name,
                exist_ok=True,  # overwrite same run name if re-running
            )
    except KeyboardInterrupt:
        print("\n[ABORT] Training interrupted by user.")
        print(f"        Checkpoint kept at: {last_pt}")
        print("        Resume later with:")
        if mode == "normal":
            print("          python ai-model/training/train_safevision_5class.py --resume")
        else:
            print(f"          python ai-model/training/train_safevision_5class.py --{mode} --resume")
        return 130
    except Exception as exc:
        print(f"\n[ERROR] Training failed: {exc}")
        return 1

    elapsed = time.time() - start
    best_pt = run_dir / "weights" / "best.pt"

    print("\n" + "=" * 70)
    print("Training completed")
    print("=" * 70)
    print(f"Elapsed time   : {elapsed/60:.2f} minutes ({elapsed:.1f} s)")
    print(f"Results folder : {run_dir}")
    print(f"best.pt        : {best_pt}  (exists: {best_pt.is_file()})")
    print(f"last.pt        : {last_pt}  (exists: {last_pt.is_file()})")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
