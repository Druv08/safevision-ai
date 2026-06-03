"""
SafeVision AI - Dataset verification script (Day 2).

This script does a SAFE check of the Roboflow YOLOv8 dataset placed at:
    ai-model/datasets/raw/construction-safety-yolo/

It DOES NOT:
- open any image
- train any model
- modify any file

It ONLY:
- reads data.yaml
- checks that expected folders exist
- counts image files and label files in each split
- peeks at the first 3 train labels (2 lines each)
- prints the class IDs of the important MVP classes
"""

from pathlib import Path

import yaml


# --- 1. Locate paths ---------------------------------------------------------

# This file lives at: ai-model/training/verify_dataset.py
# So the project root (the folder that contains "ai-model") is two parents up.
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent

DATASET_DIR = PROJECT_ROOT / "ai-model" / "datasets" / "raw" / "construction-safety-yolo"
DATA_YAML = DATASET_DIR / "data.yaml"

# Image extensions we accept when counting images.
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp"}

# The 5 SafeVision MVP classes we care about.
MVP_CLASS_NAMES = ["Hardhat", "NO-Hardhat", "NO-Safety Vest", "Person", "Safety Vest"]


def count_files(folder: Path, extensions: set | None = None) -> int:
    """Count files in a folder (non-recursive). Returns 0 if folder is missing."""
    if not folder.is_dir():
        return 0
    if extensions is None:
        return sum(1 for p in folder.iterdir() if p.is_file())
    return sum(1 for p in folder.iterdir() if p.is_file() and p.suffix.lower() in extensions)


def main() -> None:
    print("=" * 60)
    print("SafeVision AI - Dataset verification")
    print("=" * 60)

    # --- 2. Check data.yaml exists -------------------------------------------
    print(f"\nLooking for data.yaml at:\n  {DATA_YAML}")
    if not DATA_YAML.is_file():
        print("\n[FAIL] data.yaml not found.")
        return
    print("data.yaml found: Yes")

    # --- 3. Load data.yaml ---------------------------------------------------
    with DATA_YAML.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    train_path = data.get("train")
    val_path = data.get("val")
    test_path = data.get("test")
    nc = data.get("nc")
    names = data.get("names")

    print("\n--- data.yaml contents ---")
    print(f"train path : {train_path}")
    print(f"val path   : {val_path}")
    print(f"test path  : {test_path}")
    print(f"nc         : {nc}")
    print(f"names      : {names}")

    # --- 4. Confirm expected folders exist -----------------------------------
    expected_folders = {
        "train/images": DATASET_DIR / "train" / "images",
        "train/labels": DATASET_DIR / "train" / "labels",
        "valid/images": DATASET_DIR / "valid" / "images",
        "valid/labels": DATASET_DIR / "valid" / "labels",
        "test/images":  DATASET_DIR / "test"  / "images",
        "test/labels":  DATASET_DIR / "test"  / "labels",
    }

    print("\n--- Folder existence ---")
    all_folders_ok = True
    for label, path in expected_folders.items():
        exists = path.is_dir()
        print(f"{label:14s} : {'Yes' if exists else 'No'}")
        if not exists:
            all_folders_ok = False

    # --- 5. Count image and label files in each split ------------------------
    print("\n--- File counts ---")
    counts = {}
    for split in ("train", "valid", "test"):
        img_dir = DATASET_DIR / split / "images"
        lbl_dir = DATASET_DIR / split / "labels"
        img_count = count_files(img_dir, IMAGE_EXTS)
        lbl_count = count_files(lbl_dir, {".txt"})
        counts[split] = (img_count, lbl_count)
        print(f"{split:6s} -> images: {img_count:5d}   labels: {lbl_count:5d}")

    any_labels_found = any(lbl > 0 for _, lbl in counts.values())

    # --- 6. Peek at first 3 train labels (2 lines each) ----------------------
    print("\n--- First 3 train/labels samples (2 lines each) ---")
    train_lbl_dir = DATASET_DIR / "train" / "labels"
    if train_lbl_dir.is_dir():
        label_files = sorted(p for p in train_lbl_dir.iterdir() if p.suffix.lower() == ".txt")
        for lf in label_files[:3]:
            print(f"\n[{lf.name}]")
            with lf.open("r", encoding="utf-8") as f:
                for i, line in enumerate(f):
                    if i >= 2:
                        break
                    print(line.rstrip())

    # --- 7. Print important MVP class IDs ------------------------------------
    print("\n--- MVP class IDs (from data.yaml) ---")
    if isinstance(names, list):
        name_to_id = {n: i for i, n in enumerate(names)}
    elif isinstance(names, dict):
        # dict form: {id: name}
        name_to_id = {n: i for i, n in names.items()}
    else:
        name_to_id = {}

    for mvp_name in MVP_CLASS_NAMES:
        cid = name_to_id.get(mvp_name)
        if cid is None:
            print(f"  {mvp_name:18s} -> NOT FOUND")
        else:
            print(f"  {mvp_name:18s} -> id {cid}")

    # --- 8. Final verdict ----------------------------------------------------
    print("\n" + "=" * 60)
    if DATA_YAML.is_file() and all_folders_ok and names and any_labels_found:
        print("Dataset verification passed. Ready for training.")
    else:
        print("Dataset verification FAILED. See checks above.")
    print("=" * 60)


if __name__ == "__main__":
    main()
