"""
SafeVision AI - YOLOv8 training script for the v4 dataset (v3 + extra helmets).

Final classes (5, unchanged):
    0 = person   1 = helmet   2 = no_helmet   3 = vest   4 = no_vest

What this script does
---------------------
Trains a YOLOv8-nano model on the merged v4 dataset (built by
build_safevision_v4_helmet_dataset.py). It is a thin wrapper around
ultralytics' `model.train(...)`.

Pick how long to train:
    python ai-model/training/train_safevision_v4.py --smoke   # 1 epoch  (pipeline test)
    python ai-model/training/train_safevision_v4.py --fast    # 10 epochs (quick look)
    python ai-model/training/train_safevision_v4.py           # 30 epochs (full run)

Pick the starting weights:
    (default)        start from yolov8n.pt  -> clean full retrain (like v3)
    --from-v3        start from the working v3 best.pt -> FINE-TUNE.
                     Recommended here: it begins from weights that already
                     detect vest/helmet well, so fewer epochs are needed to
                     fold in the extra helmet data. Pair with --fast.

Resume an interrupted run:
    python ai-model/training/train_safevision_v4.py --resume
    python ai-model/training/train_safevision_v4.py --fast --resume

Output goes to: ai-model/outputs/training-runs/<run_name>/
    weights/best.pt, weights/last.pt, results.csv

Device: uses CUDA GPU automatically if available, else CPU (slow).
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
    / "safevision-ppe-5class-v4" / "data.yaml"
)

OUTPUT_DIR = PROJECT_ROOT / "ai-model" / "outputs" / "training-runs"

# Default base model (clean retrain). ultralytics auto-downloads it if absent.
BASE_MODEL = "yolov8n.pt"

# The working v3 weights, used when --from-v3 is passed (fine-tune).
V3_BEST = OUTPUT_DIR / "safevision_yolov8n_5class_v3" / "weights" / "best.pt"

IMG_SIZE = 640
BATCH_SIZE = 8

MODES = {
    "smoke":  {"epochs": 1,  "name": "safevision_yolov8n_5class_v4_smoke"},
    "fast":   {"epochs": 10, "name": "safevision_yolov8n_5class_v4_fast"},
    "normal": {"epochs": 30, "name": "safevision_yolov8n_5class_v4"},
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Train YOLOv8n on the SafeVision v4 5-class dataset."
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--smoke", action="store_true",
                       help="Smoke test: 1 epoch, just to confirm the pipeline runs.")
    group.add_argument("--fast", action="store_true",
                       help="Fast run: 10 epochs (quick quality check).")
    parser.add_argument("--from-v3", action="store_true",
                        help="Fine-tune starting from the working v3 best.pt "
                             "instead of yolov8n.pt (faster; recommended).")
    parser.add_argument("--resume", action="store_true",
                        help="Resume the selected mode from its last.pt checkpoint.")
    return parser.parse_args()


def pick_mode(args: argparse.Namespace) -> str:
    if args.smoke:
        return "smoke"
    if args.fast:
        return "fast"
    return "normal"


def pick_device() -> str:
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

    # Choose starting weights.
    if args.from_v3:
        if not V3_BEST.is_file():
            print(f"[ERROR] --from-v3 set but v3 weights not found:\n  {V3_BEST}")
            return 1
        base_model = str(V3_BEST)
    else:
        base_model = BASE_MODEL

    if args.resume and not last_pt.is_file():
        print("=" * 70)
        print("[ERROR] --resume was passed but no checkpoint was found at:")
        print(f"  {last_pt}")
        print("Start a fresh run (drop --resume) or pick the right mode.")
        print("=" * 70)
        return 1

    print("=" * 70)
    print("SafeVision AI - YOLOv8 training (v4, 5-class: v3 + extra helmets)")
    print("=" * 70)
    print(f"Dataset path   : {DATA_YAML}")
    print(f"Training mode  : {mode.upper()}{' (RESUME)' if args.resume else ''}")
    print(f"Epochs (target): {epochs}")
    print(f"Image size     : {IMG_SIZE}")
    print(f"Batch size     : {BATCH_SIZE}")
    print(f"Device         : {device}")
    print(f"Base model     : {base_model if not args.resume else last_pt}")
    print(f"Fine-tune v3   : {args.from_v3}")
    print(f"Output name    : {run_name}")
    print(f"Output folder  : {run_dir}")
    print("=" * 70)
    if device == "cpu":
        print("[WARNING] No GPU detected - training on CPU.")
        print("          The v4 train split has ~10,000 images, so a full")
        print("          30-epoch CPU run can take many hours. Use --smoke first.")
        print("=" * 70)

    if not DATA_YAML.is_file():
        print(f"\n[ERROR] data.yaml not found at:\n  {DATA_YAML}")
        print("Build the v4 dataset first:")
        print("  python ai-model/training/build_safevision_v4_helmet_dataset.py")
        return 1

    try:
        from ultralytics import YOLO
    except ImportError:
        print("\n[ERROR] ultralytics package is not installed.")
        print("Install it with:  pip install ultralytics")
        return 1

    start = time.time()
    try:
        if args.resume:
            print(f"\nResuming from checkpoint: {last_pt}")
            model = YOLO(str(last_pt))
            print("Continuing training...\n")
            model.train(resume=True)
        else:
            print(f"\nLoading base model: {base_model}")
            model = YOLO(base_model)
            print("Starting training...\n")
            model.train(
                data=str(DATA_YAML),
                epochs=epochs,
                imgsz=IMG_SIZE,
                batch=BATCH_SIZE,
                device=device,
                project=str(OUTPUT_DIR),
                name=run_name,
                exist_ok=True,
            )
    except KeyboardInterrupt:
        print("\n[ABORT] Training interrupted by user.")
        print(f"        Checkpoint kept at: {last_pt}")
        print("        Resume later with:")
        if mode == "normal":
            print("          python ai-model/training/train_safevision_v4.py --resume")
        else:
            print(f"          python ai-model/training/train_safevision_v4.py --{mode} --resume")
        return 130
    except Exception as exc:
        print(f"\n[ERROR] Training failed: {exc}")
        return 1

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
    print(f"results.csv    : {results_csv if results_csv.is_file() else '(not found)'}")
    print("=" * 70)
    print("Point the demo at the new weights with --model, e.g.:")
    print(f"  --model \"{best_pt}\"")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
