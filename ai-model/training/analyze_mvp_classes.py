from collections import Counter
from pathlib import Path

import yaml

# ---------------------------------------------------------------
# Paths (PROJECT_ROOT = .../safevision-ai/safevision-ai)
# ---------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATASET_DIR = PROJECT_ROOT / "ai-model" / "datasets" / "raw" / "construction-safety-yolo"
DATA_YAML = DATASET_DIR / "data.yaml"

LABEL_DIRS = {
    "train": DATASET_DIR / "train" / "labels",
    "valid": DATASET_DIR / "valid" / "labels",
    "test":  DATASET_DIR / "test"  / "labels",
}
TEST_IMAGES_DIR = DATASET_DIR / "test" / "images"

MODEL_PATH = (
    PROJECT_ROOT
    / "ai-model" / "outputs" / "training-runs"
    / "safevision_yolov8n_v1" / "weights" / "best.pt"
)

PRED_OUTPUT_ROOT = PROJECT_ROOT / "ai-model" / "outputs" / "predictions"

# MVP classes we actually care about for the safety MVP
MVP_CLASSES = {
    4:  "Hardhat",
    6:  "NO-Hardhat",
    8:  "NO-Safety Vest",
    9:  "Person",
    12: "Safety Vest",
}

# Image extensions to consider when picking test images
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp"}


# ---------------------------------------------------------------
# Step 1 - Load data.yaml
# ---------------------------------------------------------------
def load_class_names():
    """Read data.yaml and return its class-name list (or empty list)."""
    if not DATA_YAML.exists():
        print(f"[warn] data.yaml not found at {DATA_YAML}")
        return []
    with open(DATA_YAML, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("names", [])


# ---------------------------------------------------------------
# Step 2 + 3 - Count MVP class instances in label files
# ---------------------------------------------------------------
def count_classes_in_split(label_dir: Path) -> Counter:
    """
    Walk every .txt label file in a split and count class-id occurrences.
    Each line in a YOLO label file looks like:
        <class_id> <x> <y> <w> <h>
    """
    counter = Counter()
    if not label_dir.exists():
        print(f"[warn] Label folder missing: {label_dir}")
        return counter

    for label_file in label_dir.glob("*.txt"):
        try:
            with open(label_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    parts = line.split()
                    try:
                        class_id = int(parts[0])
                    except (ValueError, IndexError):
                        continue
                    counter[class_id] += 1
        except OSError:
            # Skip unreadable files instead of crashing
            continue
    return counter


def print_mvp_distribution(split_counts: dict[str, Counter]) -> None:
    """Pretty-print the MVP class distribution across all splits."""
    print()
    print("=" * 78)
    print("MVP class distribution in dataset")
    print("=" * 78)
    header = f"{'Class name':<18}{'ID':>4}{'Train':>10}{'Valid':>10}{'Test':>10}{'Total':>10}"
    print(header)
    print("-" * 78)

    grand_total = 0
    for cls_id, cls_name in MVP_CLASSES.items():
        train_c = split_counts["train"].get(cls_id, 0)
        valid_c = split_counts["valid"].get(cls_id, 0)
        test_c  = split_counts["test"].get(cls_id, 0)
        total_c = train_c + valid_c + test_c
        grand_total += total_c
        print(f"{cls_name:<18}{cls_id:>4}{train_c:>10}{valid_c:>10}{test_c:>10}{total_c:>10}")

    print("-" * 78)
    print(f"{'MVP grand total':<22}{'':>10}{'':>10}{'':>10}{grand_total:>10}")


# ---------------------------------------------------------------
# Step 5-9 - Run predictions at multiple confidence thresholds
# ---------------------------------------------------------------
def get_first_n_test_images(n: int = 10) -> list[Path]:
    """Return the first N test images, sorted for repeatability."""
    if not TEST_IMAGES_DIR.exists():
        print(f"[warn] Test image folder missing: {TEST_IMAGES_DIR}")
        return []
    images = sorted(
        p for p in TEST_IMAGES_DIR.iterdir()
        if p.suffix.lower() in IMAGE_EXTS
    )
    return images[:n]


def run_predictions_at_threshold(model, images: list[Path], conf: float) -> Counter:
    """
    Run YOLOv8 prediction at a given confidence, save annotated images
    to a dedicated folder, and return per-MVP-class detection counts.
    """
    folder_name = f"conf_{int(conf * 1000):03d}"  # 0.25 -> conf_250 ... but spec says conf_025
    # Use the names the user asked for: conf_025, conf_015, conf_010
    pretty_names = {0.25: "conf_025", 0.15: "conf_015", 0.10: "conf_010"}
    save_name = pretty_names.get(conf, folder_name)

    print(f"\n--- Running predictions at conf={conf} (saving to {save_name}) ---")

    results = model.predict(
        source=[str(p) for p in images],
        conf=conf,
        save=True,
        project=str(PRED_OUTPUT_ROOT),
        name=save_name,
        exist_ok=True,
        verbose=False,
    )

    # Count MVP-class detections across all images at this threshold
    counts = Counter()
    for r in results:
        if r.boxes is None or len(r.boxes) == 0:
            continue
        for cls_tensor in r.boxes.cls.tolist():
            cls_id = int(cls_tensor)
            if cls_id in MVP_CLASSES:
                counts[cls_id] += 1
    return counts


def print_threshold_results(threshold_counts: dict[float, Counter]) -> None:
    """Pretty-print MVP detection counts across confidence thresholds."""
    print()
    print("=" * 78)
    print("MVP detections vs confidence threshold (first 10 test images)")
    print("=" * 78)

    thresholds = sorted(threshold_counts.keys(), reverse=True)
    header = f"{'Class name':<18}{'ID':>4}" + "".join(f"{f'conf={t}':>12}" for t in thresholds)
    print(header)
    print("-" * 78)

    for cls_id, cls_name in MVP_CLASSES.items():
        row = f"{cls_name:<18}{cls_id:>4}"
        for t in thresholds:
            row += f"{threshold_counts[t].get(cls_id, 0):>12}"
        print(row)

    print("-" * 78)
    totals_row = f"{'TOTAL (MVP only)':<22}"
    for t in thresholds:
        totals_row += f"{sum(threshold_counts[t].get(c, 0) for c in MVP_CLASSES):>12}"
    print(totals_row)


# ---------------------------------------------------------------
# Main
# ---------------------------------------------------------------
def main():
    print("=" * 78)
    print("SafeVision AI - MVP class analysis")
    print("=" * 78)
    print(f"Project root : {PROJECT_ROOT}")
    print(f"Dataset dir  : {DATASET_DIR}")
    print(f"Model path   : {MODEL_PATH}")

    # --- Dataset class names ---
    class_names = load_class_names()
    if class_names:
        print(f"\nLoaded {len(class_names)} class names from data.yaml")

    # --- Count MVP classes in each split ---
    split_counts = {
        split: count_classes_in_split(label_dir)
        for split, label_dir in LABEL_DIRS.items()
    }
    print_mvp_distribution(split_counts)

    # --- Pick test images for inference experiment ---
    test_images = get_first_n_test_images(10)
    if not test_images:
        print("\n[error] No test images found - skipping prediction experiment.")
        return
    print(f"\nUsing {len(test_images)} test images for the confidence experiment.")

    # --- Load trained model ---
    if not MODEL_PATH.exists():
        print(f"\n[error] Trained model not found at {MODEL_PATH}")
        return

    try:
        from ultralytics import YOLO
    except ImportError as exc:
        print(f"\n[error] ultralytics not installed: {exc}")
        return

    print("\nLoading trained model...")
    model = YOLO(str(MODEL_PATH))

    # --- Run predictions at three confidence thresholds ---
    threshold_counts: dict[float, Counter] = {}
    for conf in (0.25, 0.15, 0.10):
        try:
            threshold_counts[conf] = run_predictions_at_threshold(model, test_images, conf)
        except Exception as exc:
            print(f"[error] Prediction failed at conf={conf}: {exc}")
            threshold_counts[conf] = Counter()

    # --- Show summary table ---
    print_threshold_results(threshold_counts)

    print("\n" + "=" * 78)
    print("Done. Annotated images saved under:")
    print(f"  {PRED_OUTPUT_ROOT / 'conf_025'}")
    print(f"  {PRED_OUTPUT_ROOT / 'conf_015'}")
    print(f"  {PRED_OUTPUT_ROOT / 'conf_010'}")
    print("=" * 78)


if __name__ == "__main__":
    main()