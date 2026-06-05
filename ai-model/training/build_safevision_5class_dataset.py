"""
SafeVision AI - Build a merged 5-class YOLO dataset.

What this script does:
  1. Reads two raw YOLOv8 datasets:
       - construction-safety-yolo  (17 classes)
       - ppe-vest-yolo             (2 classes: 'no vest', 'vest')
  2. Remaps their class IDs to a unified 5-class MVP schema:
       0 = person, 1 = helmet, 2 = no_helmet, 3 = vest, 4 = no_vest
  3. Copies only images whose labels contain at least one MVP class
     (after remapping). Labels are rewritten with the new IDs.
  4. Splits dataset 2's train into 90% train / 10% test (seed=42)
     because dataset 2 has no test split. Dataset 2's valid stays as valid.
  5. Adds filename prefixes (construction_<split>_, vest_<split>_) to
     avoid name collisions between the two sources.
  6. Writes data.yaml for the merged dataset.
  7. Prints a clean summary.

Safety:
  - Does NOT modify the raw datasets.
  - Does NOT open image files (only copies bytes).
  - Does NOT train YOLO.
  - Output folder is under ai-model/datasets/processed/ (gitignored).
"""

import random
import shutil
from collections import Counter
from pathlib import Path

# ---------------------------------------------------------------
# Paths
# ---------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
RAW_DIR = PROJECT_ROOT / "ai-model" / "datasets" / "raw"
SRC1 = RAW_DIR / "construction-safety-yolo"   # 17-class dataset
SRC2 = RAW_DIR / "ppe-vest-yolo"               # 2-class vest dataset

OUT_DIR = PROJECT_ROOT / "ai-model" / "datasets" / "processed" / "safevision-ppe-5class"
OUT_YAML = OUT_DIR / "data.yaml"

# Final unified class schema
FINAL_NAMES = {
    0: "person",
    1: "helmet",
    2: "no_helmet",
    3: "vest",
    4: "no_vest",
}

# Source-1 (construction): {old_id: new_id}.  Other classes are ignored.
SRC1_REMAP = {
    9:  0,  # Person        -> person
    4:  1,  # Hardhat        -> helmet
    6:  2,  # NO-Hardhat     -> no_helmet
    12: 3,  # Safety Vest    -> vest
    8:  4,  # NO-Safety Vest -> no_vest
}

# Source-2 (vest):  classes are ['no vest'=0, 'vest'=1]
SRC2_REMAP = {
    0: 4,   # no vest -> no_vest
    1: 3,   # vest    -> vest
}

# Splits in the FINAL dataset
FINAL_SPLITS = ("train", "valid", "test")

# Image extensions we expect from the raw datasets
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp"}

RANDOM_SEED = 42


# ---------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------
def ensure_output_tree() -> None:
    """Create the processed/safevision-ppe-5class/{split}/{images,labels} tree."""
    for split in FINAL_SPLITS:
        (OUT_DIR / split / "images").mkdir(parents=True, exist_ok=True)
        (OUT_DIR / split / "labels").mkdir(parents=True, exist_ok=True)


def find_image_for_label(images_dir: Path, label_stem: str) -> Path | None:
    """Given a label stem (filename without .txt), find its matching image file."""
    for ext in IMAGE_EXTS:
        candidate = images_dir / f"{label_stem}{ext}"
        if candidate.exists():
            return candidate
    return None


def remap_label_file(label_path: Path, remap: dict[int, int]) -> list[str]:
    """
    Read a YOLO label file and return new lines with remapped class IDs.
    Only lines whose class ID is in `remap` are kept. Other lines are dropped.
    Returns an empty list if no relevant labels remain.
    """
    new_lines: list[str] = []
    try:
        with open(label_path, "r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line:
                    continue
                parts = line.split()
                try:
                    old_id = int(parts[0])
                except (ValueError, IndexError):
                    continue
                if old_id not in remap:
                    continue
                new_id = remap[old_id]
                # Keep bbox coords unchanged; just swap the class ID
                new_lines.append(" ".join([str(new_id)] + parts[1:]))
    except OSError:
        return []
    return new_lines


def process_split(
    src_split_dir: Path,
    remap: dict[int, int],
    out_split: str,
    filename_prefix: str,
    label_files: list[Path] | None = None,
    counts: Counter | None = None,
    class_counter: Counter | None = None,
) -> None:
    """
    Process one source split: copy qualifying images + write remapped labels.

    Parameters
    ----------
    src_split_dir : Path
        Path to a split folder containing 'images/' and 'labels/'.
    remap : dict
        Old-class-id -> new-class-id mapping.
    out_split : str
        Target split in the processed dataset ('train', 'valid', or 'test').
    filename_prefix : str
        Prefix added to all copied file stems to avoid collisions.
    label_files : list[Path] | None
        Optional explicit list of label .txt files to process. If None,
        all .txt files in src_split_dir/labels are used.
    counts : Counter | None
        Accumulator for per-split image/label counts (in/out).
    class_counter : Counter | None
        Accumulator for per-final-class instance counts.
    """
    labels_dir = src_split_dir / "labels"
    images_dir = src_split_dir / "images"

    if counts is None:
        counts = Counter()
    if class_counter is None:
        class_counter = Counter()

    if not labels_dir.exists() or not images_dir.exists():
        print(f"  [warn] missing images/labels under {src_split_dir}")
        return

    files = label_files if label_files is not None else sorted(labels_dir.glob("*.txt"))
    counts[f"{out_split}_label_files_seen"] += len(files)

    out_images_dir = OUT_DIR / out_split / "images"
    out_labels_dir = OUT_DIR / out_split / "labels"

    for label_file in files:
        # 1) Remap labels (drops irrelevant classes)
        new_lines = remap_label_file(label_file, remap)
        if not new_lines:
            counts[f"{out_split}_skipped_no_mvp_labels"] += 1
            continue

        # 2) Find matching image
        image_path = find_image_for_label(images_dir, label_file.stem)
        if image_path is None:
            counts[f"{out_split}_skipped_no_image"] += 1
            continue

        # 3) Build prefixed output stem
        new_stem = f"{filename_prefix}{label_file.stem}"
        out_image = out_images_dir / f"{new_stem}{image_path.suffix.lower()}"
        out_label = out_labels_dir / f"{new_stem}.txt"

        # 4) Copy image bytes (do not open / decode)
        try:
            shutil.copy2(image_path, out_image)
        except OSError as exc:
            print(f"  [warn] failed to copy {image_path.name}: {exc}")
            counts[f"{out_split}_skipped_copy_error"] += 1
            continue

        # 5) Write remapped label file
        with open(out_label, "w", encoding="utf-8") as f:
            f.write("\n".join(new_lines) + "\n")

        counts[f"{out_split}_images_written"] += 1
        counts[f"{out_split}_labels_written"] += 1

        for line in new_lines:
            new_id = int(line.split()[0])
            class_counter[new_id] += 1


def write_data_yaml() -> None:
    """Write the merged data.yaml for YOLOv8."""
    # Build YAML manually so the key order is exactly what the user asked for.
    lines = [
        "train: train/images",
        "val: valid/images",
        "test: test/images",
        "",
        f"nc: {len(FINAL_NAMES)}",
        "",
        "names:",
    ]
    for cls_id, cls_name in FINAL_NAMES.items():
        lines.append(f"  {cls_id}: {cls_name}")
    OUT_YAML.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------
# Main
# ---------------------------------------------------------------
def main() -> None:
    print("=" * 78)
    print("SafeVision AI - Build merged 5-class dataset")
    print("=" * 78)
    print(f"Source 1 : {SRC1}")
    print(f"Source 2 : {SRC2}")
    print(f"Output   : {OUT_DIR}")

    if not SRC1.exists():
        print(f"[error] Source 1 not found: {SRC1}")
        return
    if not SRC2.exists():
        print(f"[error] Source 2 not found: {SRC2}")
        return

    ensure_output_tree()

    counts = Counter()
    class_counter = Counter()

    # -----------------------------------------------------------
    # Source 1 (construction): copy train -> train, valid -> valid, test -> test
    # -----------------------------------------------------------
    print("\n[1/2] Processing construction-safety-yolo ...")
    src1_splits = {"train": "train", "valid": "valid", "test": "test"}
    for src_split, out_split in src1_splits.items():
        src_split_dir = SRC1 / src_split
        prefix = f"construction_{src_split}_"
        print(f"   - {src_split} -> {out_split}  (prefix='{prefix}')")
        process_split(
            src_split_dir=src_split_dir,
            remap=SRC1_REMAP,
            out_split=out_split,
            filename_prefix=prefix,
            counts=counts,
            class_counter=class_counter,
        )

    # -----------------------------------------------------------
    # Source 2 (vest):
    #   - valid -> valid
    #   - train: 90/10 split into train/test (seed=42)
    # -----------------------------------------------------------
    print("\n[2/2] Processing ppe-vest-yolo ...")

    # 2a: valid -> valid
    src2_valid_dir = SRC2 / "valid"
    print("   - valid -> valid  (prefix='vest_valid_')")
    process_split(
        src_split_dir=src2_valid_dir,
        remap=SRC2_REMAP,
        out_split="valid",
        filename_prefix="vest_valid_",
        counts=counts,
        class_counter=class_counter,
    )

    # 2b: 90/10 split of train -> train + test
    src2_train_dir = SRC2 / "train"
    src2_train_labels = sorted((src2_train_dir / "labels").glob("*.txt"))
    rng = random.Random(RANDOM_SEED)
    shuffled = src2_train_labels.copy()
    rng.shuffle(shuffled)

    n = len(shuffled)
    n_test = int(round(n * 0.10))
    test_files = shuffled[:n_test]
    train_files = shuffled[n_test:]
    print(f"   - train (90/10 split, seed={RANDOM_SEED}): "
          f"{len(train_files)} -> train, {len(test_files)} -> test")

    process_split(
        src_split_dir=src2_train_dir,
        remap=SRC2_REMAP,
        out_split="train",
        filename_prefix="vest_train_",
        label_files=train_files,
        counts=counts,
        class_counter=class_counter,
    )
    process_split(
        src_split_dir=src2_train_dir,
        remap=SRC2_REMAP,
        out_split="test",
        filename_prefix="vest_train_",  # came from train originally
        label_files=test_files,
        counts=counts,
        class_counter=class_counter,
    )

    # -----------------------------------------------------------
    # Write data.yaml
    # -----------------------------------------------------------
    write_data_yaml()

    # -----------------------------------------------------------
    # Summary
    # -----------------------------------------------------------
    print("\n" + "=" * 78)
    print("SUMMARY")
    print("=" * 78)
    print(f"Processed dataset path: {OUT_DIR}")

    for split in FINAL_SPLITS:
        img_count = counts[f"{split}_images_written"]
        lbl_count = counts[f"{split}_labels_written"]
        skipped_nomvp = counts[f"{split}_skipped_no_mvp_labels"]
        skipped_noimg = counts[f"{split}_skipped_no_image"]
        skipped_copy  = counts[f"{split}_skipped_copy_error"]
        seen = counts[f"{split}_label_files_seen"]
        print(f"\n[{split}]")
        print(f"   label files seen          : {seen}")
        print(f"   images written            : {img_count}")
        print(f"   labels written            : {lbl_count}")
        print(f"   skipped (no MVP labels)   : {skipped_nomvp}")
        print(f"   skipped (image missing)   : {skipped_noimg}")
        print(f"   skipped (copy error)      : {skipped_copy}")

    print("\nClass instance counts (final IDs):")
    for cls_id, cls_name in FINAL_NAMES.items():
        print(f"   {cls_id} {cls_name:<10}: {class_counter[cls_id]}")

    print(f"\ndata.yaml written to: {OUT_YAML}")
    print("=" * 78)
    print("Done.")


if __name__ == "__main__":
    main()
