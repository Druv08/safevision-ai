"""
SafeVision AI - YOLOv8 training for the v5 dataset (v4 + your webcam frames).

Final classes (5): 0 person  1 helmet  2 no_helmet  3 vest  4 no_vest

v5 adds your own webcam helmet / no_helmet frames (auto-labeled by pose) on top
of v4, so the model finally sees the close-up indoor domain it failed on.

Pick duration:
    python ai-model/training/train_safevision_v5.py --smoke   # 1 epoch
    python ai-model/training/train_safevision_v5.py --fast    # 10 epochs
    python ai-model/training/train_safevision_v5.py           # 30 epochs

Pick start weights:
    (default)   yolov8n.pt  -> clean retrain
    --from-v3   start from the working v3 best.pt -> FINE-TUNE (recommended;
                pair with --fast for the quickest path to a working webcam model)

Resume:
    python ai-model/training/train_safevision_v5.py --fast --resume

Output: ai-model/outputs/training-runs/<run_name>/weights/best.pt
Then run the demo with:  --model "<...>/best.pt"
"""

import argparse
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent

PROCESSED = PROJECT_ROOT / "ai-model" / "datasets" / "processed"
OUTPUT_DIR = PROJECT_ROOT / "ai-model" / "outputs" / "training-runs"
BASE_MODEL = "yolov8n.pt"
V3_BEST = OUTPUT_DIR / "safevision_yolov8n_5class_v3" / "weights" / "best.pt"
V5B_BEST = OUTPUT_DIR / "safevision_yolov8n_5class_v5b" / "weights" / "best.pt"

IMG_SIZE = 640
BATCH_SIZE = 8
# Run names are suffixed per mode; the dataset tag ("" or "b") is inserted by
# build_modes() so the balanced (v5b) runs never overwrite the v5 runs.
EPOCHS = {"smoke": 1, "fast": 10, "normal": 30}


def build_modes(balanced: bool, v5c: bool):
    if v5c:
        tag, data_dir = "v5c", "safevision-ppe-5class-v5c"
    elif balanced:
        tag, data_dir = "v5b", "safevision-ppe-5class-v5b"
    else:
        tag, data_dir = "v5", "safevision-ppe-5class-v5"
    data_yaml = PROCESSED / data_dir / "data.yaml"
    modes = {
        "smoke":  {"epochs": 1,  "name": f"safevision_yolov8n_5class_{tag}_smoke"},
        "fast":   {"epochs": 10, "name": f"safevision_yolov8n_5class_{tag}_fast"},
        "normal": {"epochs": 30, "name": f"safevision_yolov8n_5class_{tag}"},
    }
    return data_yaml, modes


def parse_args():
    p = argparse.ArgumentParser(description="Train YOLOv8n on the SafeVision v5 dataset.")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--smoke", action="store_true", help="1 epoch pipeline test.")
    g.add_argument("--fast", action="store_true", help="10 epochs quick run.")
    p.add_argument("--from-v3", action="store_true",
                   help="Fine-tune from v3 best.pt instead of yolov8n.pt.")
    p.add_argument("--from-v5b", action="store_true",
                   help="Fine-tune from the v5b best.pt (recommended for v5c: "
                        "v5b already learned the webcam helmet setup, v5c is a "
                        "surgical hard-negative correction on top).")
    p.add_argument("--balanced", action="store_true",
                   help="Train on the balanced v5b dataset (v3 + webcam, no "
                        "construction flood, no_helmet oversampled). Writes to "
                        "*_v5b run folders.")
    p.add_argument("--v5c", action="store_true",
                   help="Train on the v5c dataset (v5b recipe + headphones / "
                        "held-helmet hard negatives). Writes to *_v5c folders.")
    p.add_argument("--resume", action="store_true", help="Resume from last.pt.")
    return p.parse_args()


def pick_mode(a):
    return "smoke" if a.smoke else ("fast" if a.fast else "normal")


def pick_device():
    try:
        import torch
        if torch.cuda.is_available():
            return "cuda"
    except Exception:
        pass
    return "cpu"


def main():
    args = parse_args()
    mode = pick_mode(args)
    DATA_YAML, MODES = build_modes(args.balanced, args.v5c)
    epochs = MODES[mode]["epochs"]
    run_name = MODES[mode]["name"]
    run_dir = OUTPUT_DIR / run_name
    last_pt = run_dir / "weights" / "last.pt"
    device = pick_device()

    if args.from_v5b:
        if not V5B_BEST.is_file():
            print(f"[ERROR] --from-v5b set but v5b weights not found:\n  {V5B_BEST}")
            return 1
        base_model = str(V5B_BEST)
    elif args.from_v3:
        if not V3_BEST.is_file():
            print(f"[ERROR] --from-v3 set but v3 weights not found:\n  {V3_BEST}")
            return 1
        base_model = str(V3_BEST)
    else:
        base_model = BASE_MODEL

    if args.resume and not last_pt.is_file():
        print(f"[ERROR] --resume but no checkpoint at:\n  {last_pt}")
        return 1

    print("=" * 70)
    print("SafeVision AI - YOLOv8 training (v5: v4 + webcam)")
    print("=" * 70)
    print(f"Dataset path   : {DATA_YAML}")
    print(f"Training mode  : {mode.upper()}{' (RESUME)' if args.resume else ''}")
    print(f"Epochs (target): {epochs}")
    print(f"Image size     : {IMG_SIZE}   Batch: {BATCH_SIZE}   Device: {device}")
    print(f"Base model     : {base_model if not args.resume else last_pt}")
    print(f"Output folder  : {run_dir}")
    print("=" * 70)
    if device == "cpu":
        print("[WARNING] No GPU detected - CPU training on ~10k images is slow.")
        print("          Use --smoke first to confirm the pipeline.")
        print("=" * 70)

    if not DATA_YAML.is_file():
        print(f"\n[ERROR] data.yaml not found:\n  {DATA_YAML}")
        print("Build v5 first: python ai-model/training/build_safevision_v5_dataset.py")
        return 1

    try:
        from ultralytics import YOLO
    except ImportError:
        print("\n[ERROR] ultralytics not installed.  pip install ultralytics")
        return 1

    start = time.time()
    try:
        if args.resume:
            print(f"\nResuming from: {last_pt}\n")
            YOLO(str(last_pt)).train(resume=True)
        else:
            print(f"\nLoading base model: {base_model}\nStarting training...\n")
            YOLO(base_model).train(
                data=str(DATA_YAML), epochs=epochs, imgsz=IMG_SIZE,
                batch=BATCH_SIZE, device=device, project=str(OUTPUT_DIR),
                name=run_name, exist_ok=True,
            )
    except KeyboardInterrupt:
        print("\n[ABORT] Interrupted. Resume with:")
        flag = "" if mode == "normal" else f"--{mode} "
        print(f"  python ai-model/training/train_safevision_v5.py {flag}--resume")
        return 130
    except Exception as exc:
        print(f"\n[ERROR] Training failed: {exc}")
        return 1

    best_pt = run_dir / "weights" / "best.pt"
    print("\n" + "=" * 70)
    print(f"Done in {(time.time()-start)/60:.1f} min")
    print(f"best.pt : {best_pt}  (exists: {best_pt.is_file()})")
    print("Run the demo on the new model:")
    print(f'  .\\venv\\Scripts\\python.exe ai-model\\inference\\video_detection.py --conf 0.4 --pose-conf 0.6 --model "{best_pt}"')
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
