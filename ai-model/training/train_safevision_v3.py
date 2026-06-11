"""
SafeVision AI - YOLOv8 training script for the v3 dataset (v2 + helmet data).

Final classes (5):
    0 = person
    1 = helmet
    2 = no_helmet
    3 = vest
    4 = no_vest

What this script does
---------------------
Trains a YOLOv8-nano model on the merged v3 dataset. It is a thin, safe
wrapper around ultralytics' `model.train(...)`. You pick how long to train
with a single flag:

    python ai-model/training/train_safevision_v3.py --smoke   # 1 epoch  (pipeline test)
    python ai-model/training/train_safevision_v3.py --fast    # 10 epochs (quick look)
    python ai-model/training/train_safevision_v3.py           # 30 epochs (full run)
    python ai-model/training/train_safevision_v3.py --resume          # resume full run
    python ai-model/training/train_safevision_v3.py --fast --resume   # resume fast run

Output goes to: ai-model/outputs/training-runs/<run_name>/
    - weights/best.pt   -> best model by validation metric
    - weights/last.pt   -> latest checkpoint (used to resume)
    - results.csv       -> per-epoch metrics

Pause / resume
--------------
    - Pause: press Ctrl+C. YOLO keeps weights/last.pt after each epoch.
    - Resume: re-run the SAME mode with --resume. Do not delete the run
      folder or last.pt while paused.

Device
------
    - Uses GPU (CUDA) automatically if torch reports it is available.
    - Otherwise falls back to CPU. CPU training is correct but slow.
"""

import argparse
import sys
import time
from pathlib import Path


# --- Paths -------------------------------------------------------------------
# __file__ lives at ai-model/training/train_safevision_v3.py
# Two .parent hops -> ai-model, three -> repo root (inner safevision-ai/).
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent

# v3 dataset description file (built by build_safevision_v3_helmet_dataset.py).
DATA_YAML = (
    PROJECT_ROOT
    / "ai-model" / "datasets" / "processed"
    / "safevision-ppe-5class-v3" / "data.yaml"
)

# All runs land under this folder; each run gets its own subfolder by name.
OUTPUT_DIR = PROJECT_ROOT / "ai-model" / "outputs" / "training-runs"

# Base model. ultralytics auto-downloads this if it is not already present.
BASE_MODEL = "yolov8n.pt"

# Shared hyperparameters (same for every mode).
IMG_SIZE = 640
BATCH_SIZE = 8

# Per-mode settings: how many epochs + the run folder name.
MODES = {
    "smoke":  {"epochs": 1,  "name": "safevision_yolov8n_5class_v3_smoke"},
    "fast":   {"epochs": 10, "name": "safevision_yolov8n_5class_v3_fast"},
    "normal": {"epochs": 30, "name": "safevision_yolov8n_5class_v3"},
}


def parse_args() -> argparse.Namespace:
    """Read command-line flags. With no flag, default = normal (30 epochs)."""
    parser = argparse.ArgumentParser(
        description="Train YOLOv8n on the SafeVision v3 5-class dataset."
    )
    # --smoke and --fast are mutually exclusive: you can pick at most one.
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--smoke",
        action="store_true",
        help="Smoke test: 1 epoch, just to confirm the pipeline runs.",
    )
    group.add_argument(
        "--fast",
        action="store_true",
        help="Fast run: 10 epochs (quick quality check).",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume the selected mode from its last.pt checkpoint.",
    )
    return parser.parse_args()


def pick_mode(args: argparse.Namespace) -> str:
    """Translate the flags into a single mode key."""
    if args.smoke:
        return "smoke"
    if args.fast:
        return "fast"
    return "normal"


def pick_device() -> str:
    """
    Return 'cuda' if a GPU is available, else 'cpu'.

    We import torch lazily and guard against any error so this never crashes
    the script just because torch is missing or misconfigured.
    """
    try:
        import torch
        if torch.cuda.is_available():
            return "cuda"
    except Exception:
        pass
    return "cpu"


def main() -> int:
    args = parse_args()
    mode = pick_mode(args)
    epochs = MODES[mode]["epochs"]
    run_name = MODES[mode]["name"]
    run_dir = OUTPUT_DIR / run_name
    last_pt = run_dir / "weights" / "last.pt"
    device = pick_device()

    # --resume needs an existing checkpoint to continue from.
    if args.resume and not last_pt.is_file():
        print("=" * 70)
        print("[ERROR] --resume was passed but no checkpoint was found at:")
        print(f"  {last_pt}")
        print("Start a fresh run (drop --resume) or pick the right mode.")
        print("=" * 70)
        return 1

    # ---- Clear start summary -------------------------------------------------
    print("=" * 70)
    print("SafeVision AI - YOLOv8 training (v3, 5-class)")
    print("=" * 70)
    print(f"Dataset path   : {DATA_YAML}")
    print(f"Training mode  : {mode.upper()}{' (RESUME)' if args.resume else ''}")
    print(f"Epochs (target): {epochs}")
    print(f"Image size     : {IMG_SIZE}")
    print(f"Batch size     : {BATCH_SIZE}")
    print(f"Device         : {device}")
    print(f"Base model     : {BASE_MODEL if not args.resume else last_pt}")
    print(f"Output name    : {run_name}")
    print(f"Output folder  : {run_dir}")
    print("=" * 70)
    if device == "cpu":
        print("[WARNING] No GPU detected - training on CPU.")
        print("          The v3 train split has ~7,588 images, so a full")
        print("          30-epoch CPU run can take many hours. Use --smoke")
        print("          first to confirm everything works.")
        print("=" * 70)

    # Dataset must exist before we try to train.
    if not DATA_YAML.is_file():
        print(f"\n[ERROR] data.yaml not found at:\n  {DATA_YAML}")
        print("Build the v3 dataset first:")
        print("  python ai-model/training/build_safevision_v3_helmet_dataset.py")
        return 1

    # Import ultralytics lazily so the messages above still show on failure.
    try:
        from ultralytics import YOLO
    except ImportError:
        print("\n[ERROR] ultralytics package is not installed.")
        print("Install it with:  pip install ultralytics")
        return 1

    # ---- Train ---------------------------------------------------------------
    start = time.time()
    try:
        if args.resume:
            print(f"\nResuming from checkpoint: {last_pt}")
            model = YOLO(str(last_pt))
            print("Continuing training...\n")
            # On resume, ultralytics reuses the original run config
            # (epochs, imgsz, batch, device, etc.) saved with the run.
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
                device=device,
                project=str(OUTPUT_DIR),
                name=run_name,
                exist_ok=True,  # reuse the same run folder if re-running
            )
    except KeyboardInterrupt:
        print("\n[ABORT] Training interrupted by user.")
        print(f"        Checkpoint kept at: {last_pt}")
        print("        Resume later with:")
        if mode == "normal":
            print("          python ai-model/training/train_safevision_v3.py --resume")
        else:
            print(f"          python ai-model/training/train_safevision_v3.py --{mode} --resume")
        return 130
    except Exception as exc:
        print(f"\n[ERROR] Training failed: {exc}")
        return 1

    # ---- Done: report where the outputs are ---------------------------------
    elapsed = time.time() - start
    best_pt = run_dir / "weights" / "best.pt"
    results_csv = run_dir / "results.csv"

    print("\n" + "=" * 70)
    print("Training completed")
    print("=" * 70)
    print(f"Elapsed time   : {elapsed/60:.2f} minutes ({elapsed:.1f} s)")
    print(f"Run folder     : {run_dir}")
    print(f"best.pt        : {best_pt}  (exists: {best_pt.is_file()})")
    print(f"last.pt        : {last_pt}  (exists: {last_pt.is_file()})")
    if results_csv.is_file():
        print(f"results.csv    : {results_csv}")
    else:
        print("results.csv    : (not found)")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
