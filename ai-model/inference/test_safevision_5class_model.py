"""
SafeVision AI - Inference test for the v2 5-class trained model.

What this script does:
  1. Loads the trained 5-class YOLOv8n model (best.pt from v2 run).
  2. Picks the first 20 images from the processed-test split.
  3. Runs prediction at confidence >= 0.25.
  4. Saves annotated images to ai-model/outputs/predictions/day4_v2_predictions/.
  5. Prints per-image detections and overall per-class totals.

Class IDs in the v2 model:
    0 = person
    1 = helmet
    2 = no_helmet
    3 = vest
    4 = no_vest

Safety:
  - Does NOT train.
  - Does NOT modify any dataset file.
  - Output folder is inside ai-model/outputs/ which is gitignored.
"""

from collections import Counter
from pathlib import Path

# ---------------------------------------------------------------
# Paths (PROJECT_ROOT = .../safevision-ai/safevision-ai)
# ---------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

MODEL_PATH = (
    PROJECT_ROOT
    / "ai-model" / "outputs" / "training-runs"
    / "safevision_yolov8n_5class_v2" / "weights" / "best.pt"
)

TEST_IMAGES_DIR = (
    PROJECT_ROOT
    / "ai-model" / "datasets" / "processed"
    / "safevision-ppe-5class" / "test" / "images"
)

PRED_OUTPUT_ROOT = PROJECT_ROOT / "ai-model" / "outputs" / "predictions"
RUN_NAME = "day4_v2_predictions"

# Detection settings
CONF_THRESHOLD = 0.25
NUM_IMAGES = 20

# The full 5-class set — every class is "MVP" for the v2 model.
MVP_CLASSES = {
    0: "person",
    1: "helmet",
    2: "no_helmet",
    3: "vest",
    4: "no_vest",
}

# Image extensions accepted in the test folder.
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp"}


def pick_test_images(n: int) -> list[Path]:
    """Return the first N test images, sorted for repeatability."""
    if not TEST_IMAGES_DIR.exists():
        return []
    images = sorted(
        p for p in TEST_IMAGES_DIR.iterdir()
        if p.suffix.lower() in IMAGE_EXTS
    )
    return images[:n]


def main() -> int:
    print("=" * 70)
    print("SafeVision AI - v2 (5-class) trained model inference test")
    print("=" * 70)
    print(f"Model path     : {MODEL_PATH}")
    print(f"Test images dir: {TEST_IMAGES_DIR}")
    print(f"Output folder  : {PRED_OUTPUT_ROOT / RUN_NAME}")
    print(f"Confidence     : {CONF_THRESHOLD}")
    print(f"Num images     : {NUM_IMAGES}")
    print("=" * 70)

    # Safety: model file must exist
    if not MODEL_PATH.is_file():
        print(f"\n[ERROR] Model not found at {MODEL_PATH}")
        return 1

    # Pick test images
    test_images = pick_test_images(NUM_IMAGES)
    if not test_images:
        print(f"\n[ERROR] No test images found in {TEST_IMAGES_DIR}")
        return 1

    print(f"\nUsing {len(test_images)} test images.")

    # Import ultralytics lazily so the path checks above can still run cleanly.
    try:
        from ultralytics import YOLO
    except ImportError as exc:
        print(f"\n[ERROR] ultralytics not installed: {exc}")
        return 1

    print("\nLoading trained model...")
    model = YOLO(str(MODEL_PATH))

    # Map class IDs to names (use the model's own names if available).
    model_names = getattr(model, "names", MVP_CLASSES) or MVP_CLASSES

    print("Running predictions...")
    results = model.predict(
        source=[str(p) for p in test_images],
        conf=CONF_THRESHOLD,
        save=True,
        project=str(PRED_OUTPUT_ROOT),
        name=RUN_NAME,
        exist_ok=True,
        verbose=False,
    )

    print(f"\nAnnotated images saved to: {PRED_OUTPUT_ROOT / RUN_NAME}")

    # ---------------------------------------------------------------
    # Per-image detections
    # ---------------------------------------------------------------
    print("\n" + "=" * 70)
    print("Per-image detections")
    print("=" * 70)

    overall_counts = Counter()

    for i, r in enumerate(results):
        boxes = r.boxes
        if boxes is None or len(boxes) == 0:
            print(f"\n[image{i}.jpg] 0 detections")
            continue

        n_det = len(boxes)
        print(f"\n[image{i}.jpg] {n_det} detection(s)")

        per_image_mvp = set()
        for cls_t, conf_t in zip(boxes.cls.tolist(), boxes.conf.tolist()):
            cls_id = int(cls_t)
            conf = float(conf_t)
            cls_name = model_names.get(cls_id, f"id{cls_id}")
            tag = "  [MVP]" if cls_id in MVP_CLASSES else ""
            print(f"   - {cls_name:<10} conf={conf:.3f}{tag}")
            overall_counts[cls_id] += 1
            if cls_id in MVP_CLASSES:
                per_image_mvp.add(MVP_CLASSES[cls_id])

        if per_image_mvp:
            print(f"   MVP classes in this image: {sorted(per_image_mvp)}")

    # ---------------------------------------------------------------
    # Overall totals
    # ---------------------------------------------------------------
    print("\n" + "=" * 70)
    print(f"Detection totals across {len(test_images)} test images (conf>={CONF_THRESHOLD})")
    print("=" * 70)
    grand_total = 0
    for cls_id, cls_name in MVP_CLASSES.items():
        count = overall_counts.get(cls_id, 0)
        grand_total += count
        print(f"  {cls_id} {cls_name:<10}: {count} detection(s)")
    print("-" * 70)
    print(f"  TOTAL                 : {grand_total} detection(s)")

    print("\n" + "=" * 70)
    print("Done")
    print(f"Annotated images saved to: {PRED_OUTPUT_ROOT / RUN_NAME}")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
