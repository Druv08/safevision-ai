"""
SafeVision AI - Trained model prediction test (Day 3).

This script loads the trained YOLOv8 weights (best.pt) and runs predictions on
the first 10 images from the test split. Output images (with drawn boxes) are
saved to a dedicated folder so we can visually verify the model is working.

It DOES NOT:
- train the model
- modify the dataset
- modify any code outside this script

It ONLY:
- loads best.pt
- predicts on 10 test images
- saves the annotated images
- prints per-image detections, with MVP classes highlighted
"""

import sys
from pathlib import Path


# --- Paths -------------------------------------------------------------------

# This file:  ai-model/inference/test_trained_model.py
# Project root = two parents up (folder containing ai-model/).
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent

MODEL_PATH = (
    PROJECT_ROOT
    / "ai-model" / "outputs" / "training-runs"
    / "safevision_yolov8n_v1" / "weights" / "best.pt"
)

TEST_IMAGES_DIR = (
    PROJECT_ROOT
    / "ai-model" / "datasets" / "raw" / "construction-safety-yolo"
    / "test" / "images"
)

OUTPUT_PROJECT = PROJECT_ROOT / "ai-model" / "outputs" / "predictions"
OUTPUT_RUN_NAME = "day3_test_predictions"

# Prediction settings
CONF_THRESHOLD = 0.25
NUM_TEST_IMAGES = 10
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp"}

# The 5 SafeVision MVP classes (names must match data.yaml exactly).
MVP_CLASS_NAMES = {"Hardhat", "NO-Hardhat", "NO-Safety Vest", "Person", "Safety Vest"}


def main() -> int:
    print("=" * 60)
    print("SafeVision AI - Trained model prediction test")
    print("=" * 60)
    print(f"Model path     : {MODEL_PATH}")
    print(f"Test images dir: {TEST_IMAGES_DIR}")
    print(f"Output folder  : {OUTPUT_PROJECT / OUTPUT_RUN_NAME}")
    print(f"Confidence     : {CONF_THRESHOLD}")
    print("=" * 60)

    # Safety checks before doing any heavy work.
    if not MODEL_PATH.is_file():
        print(f"\n[ERROR] Trained model not found at:\n  {MODEL_PATH}")
        return 1
    if not TEST_IMAGES_DIR.is_dir():
        print(f"\n[ERROR] Test images folder not found at:\n  {TEST_IMAGES_DIR}")
        return 1

    # Pick the first N test images (sorted for repeatability).
    all_images = sorted(
        p for p in TEST_IMAGES_DIR.iterdir()
        if p.is_file() and p.suffix.lower() in IMAGE_EXTS
    )
    selected = all_images[:NUM_TEST_IMAGES]
    if not selected:
        print("\n[ERROR] No images found in test folder.")
        return 1

    print(f"\nUsing {len(selected)} test images:")
    for p in selected:
        print(f"  - {p.name}")

    # Import ultralytics here so the path checks above can report errors first.
    try:
        from ultralytics import YOLO
    except ImportError:
        print("\n[ERROR] ultralytics is not installed. Install with: pip install ultralytics")
        return 1

    try:
        print("\nLoading trained model...")
        model = YOLO(str(MODEL_PATH))

        print("Running predictions...\n")
        results = model.predict(
            source=[str(p) for p in selected],
            conf=CONF_THRESHOLD,
            save=True,                       # save annotated images
            project=str(OUTPUT_PROJECT),
            name=OUTPUT_RUN_NAME,
            exist_ok=True,                   # overwrite the same folder if re-run
            verbose=False,
        )
    except Exception as exc:
        print(f"\n[ERROR] Prediction failed: {exc}")
        return 1

    # Map class id -> class name for nicer printing.
    id_to_name = model.names  # dict: {0: 'Barricade', 1: 'Dumpster', ...}

    # --- Per-image detection summary -----------------------------------------
    print("=" * 60)
    print("Per-image detections")
    print("=" * 60)

    overall_mvp_hits: dict[str, int] = {name: 0 for name in MVP_CLASS_NAMES}

    for r in results:
        img_name = Path(r.path).name
        if r.boxes is None or len(r.boxes) == 0:
            print(f"\n[{img_name}] no detections above conf={CONF_THRESHOLD}")
            continue

        # Each detection has a class id and a confidence.
        cls_ids = r.boxes.cls.tolist()
        confs = r.boxes.conf.tolist()

        print(f"\n[{img_name}] {len(cls_ids)} detection(s)")
        mvp_in_image = []
        for cid, conf in zip(cls_ids, confs):
            cid_int = int(cid)
            name = id_to_name.get(cid_int, f"id{cid_int}")
            is_mvp = name in MVP_CLASS_NAMES
            tag = "  [MVP]" if is_mvp else ""
            print(f"   - {name:18s} conf={conf:.3f}{tag}")
            if is_mvp:
                mvp_in_image.append(name)
                overall_mvp_hits[name] += 1

        if mvp_in_image:
            print(f"   MVP classes in this image: {sorted(set(mvp_in_image))}")

    # --- Final MVP summary ---------------------------------------------------
    print("\n" + "=" * 60)
    print("MVP class totals (across all 10 test images)")
    print("=" * 60)
    for name in sorted(MVP_CLASS_NAMES):
        print(f"  {name:18s} : {overall_mvp_hits[name]} detection(s)")

    out_dir = OUTPUT_PROJECT / OUTPUT_RUN_NAME
    print("\n" + "=" * 60)
    print("Done")
    print("=" * 60)
    print(f"Annotated images saved to: {out_dir}")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
