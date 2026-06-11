"""
SafeVision AI - Build the v3 dataset (v2 + helmet-no-helmet).

Plain-English overview
-----------------------
We already have a working 5-class dataset called "v2":
    ai-model/datasets/processed/safevision-ppe-5class/
Its classes are already in the FINAL SafeVision schema:
    0 = person, 1 = helmet, 2 = no_helmet, 3 = vest, 4 = no_vest

We just downloaded a new helmet dataset ("helmet-yolo") whose classes are:
    0 = head, 1 = helmet, 2 = person
We want to fold this extra helmet/no-helmet data into a brand-new "v3"
dataset so the model sees more helmet examples.

This script does exactly this, in two passes:

  PASS 1 - Copy v2 into v3 UNCHANGED.
           v2 is already in the final schema, so we copy every image+label
           byte-for-byte (no remapping, no dropping). Files get a "v2_" style
           prefix is NOT added here on purpose - v2 filenames already have
           their own prefixes (construction_*, vest_*) so they will not
           collide with the helmet files.

  PASS 2 - Add helmet-yolo with class REMAPPING:
               helmet class 0 head   -> SafeVision class 2 no_helmet
               helmet class 1 helmet -> SafeVision class 1 helmet
               helmet class 2 person -> SafeVision class 0 person
           Any other (unexpected) class is ignored.
           Only images that still have >=1 useful label after remapping
           are copied. Helmet files get a prefix so they never collide:
               helmet_train_ / helmet_valid_ / helmet_test_

At the end it writes v3/data.yaml and prints a detailed summary.

Safety guarantees
-----------------
  - Does NOT modify the raw helmet dataset.
  - Does NOT modify the existing v2 processed dataset.
  - Does NOT open / decode image files (only copies raw bytes).
  - Does NOT train anything.
  - Output lives under processed/ (which is gitignored).
"""

import shutil
from collections import Counter
from pathlib import Path

# ---------------------------------------------------------------
# Paths
# ---------------------------------------------------------------
# __file__ = ai-model/training/build_safevision_v3_helmet_dataset.py
# .parent.parent.parent walks up to the repo root (the inner safevision-ai/).
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATASETS = PROJECT_ROOT / "ai-model" / "datasets"

# Source A: the existing, already-final v2 dataset.
V2_DIR = DATASETS / "processed" / "safevision-ppe-5class"

# Source B: the new raw helmet dataset (head / helmet / person).
HELMET_DIR = DATASETS / "raw" / "helmet-yolo"

# Destination: the new combined v3 dataset.
OUT_DIR = DATASETS / "processed" / "safevision-ppe-5class-v3"
OUT_YAML = OUT_DIR / "data.yaml"

# Final unified class schema (same as v2).
FINAL_NAMES = {
    0: "person",
    1: "helmet",
    2: "no_helmet",
    3: "vest",
    4: "no_vest",
}

# Helmet dataset remap: {old_helmet_id: new_safevision_id}.
# Anything NOT in this dict is treated as "unrelated" and dropped.
HELMET_REMAP = {
    0: 2,  # head   -> no_helmet
    1: 1,  # helmet -> helmet
    2: 0,  # person -> person
}

# The three splits we build in the final dataset.
FINAL_SPLITS = ("train", "valid", "test")

# Image extensions we expect (both datasets use .jpg, but we stay flexible).
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp"}


# ---------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------
def ensure_output_tree() -> None:
    """Create v3/{train,valid,test}/{images,labels} if they don't exist yet."""
    for split in FINAL_SPLITS:
        (OUT_DIR / split / "images").mkdir(parents=True, exist_ok=True)
        (OUT_DIR / split / "labels").mkdir(parents=True, exist_ok=True)


def find_image_for_label(images_dir: Path, label_stem: str) -> Path | None:
    """Find the image file that matches a label file (same name, image ext)."""
    for ext in IMAGE_EXTS:
        candidate = images_dir / f"{label_stem}{ext}"
        if candidate.exists():
            return candidate
    return None


def read_label_lines(label_path: Path, remap: dict[int, int] | None) -> list[str]:
    """
    Read a YOLO label file and return its output lines.

    If `remap` is None  -> copy every valid line UNCHANGED (used for v2).
    If `remap` is a dict -> keep only lines whose class is in remap, and
                            swap the class id to the remapped value (helmet).

    A "valid line" looks like: "<class_id> <cx> <cy> <w> <h>".
    Returns [] if nothing useful remains (e.g. empty or all-unrelated).
    """
    out_lines: list[str] = []
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
                    continue  # malformed line -> skip just this line

                if remap is None:
                    # v2: already final schema, keep the line exactly as-is.
                    out_lines.append(line)
                else:
                    # helmet: only keep classes we know how to map.
                    if old_id not in remap:
                        continue
                    new_id = remap[old_id]
                    out_lines.append(" ".join([str(new_id)] + parts[1:]))
    except OSError:
        return []
    return out_lines


def process_split(
    src_split_dir: Path,
    out_split: str,
    remap: dict[int, int] | None,
    filename_prefix: str,
    counts: Counter,
    class_counter: Counter,
) -> None:
    """
    Copy one source split's images+labels into the v3 output split.

    Parameters
    ----------
    src_split_dir : folder containing 'images/' and 'labels/'.
    out_split     : 'train' | 'valid' | 'test' (where it lands in v3).
    remap         : None to copy v2 unchanged, or helmet remap dict.
    filename_prefix : prefix added to each file stem to avoid collisions.
    counts        : accumulator for per-split image/label/skip counts.
    class_counter : accumulator for per-final-class instance counts.
    """
    labels_dir = src_split_dir / "labels"
    images_dir = src_split_dir / "images"

    if not labels_dir.exists() or not images_dir.exists():
        print(f"  [warn] missing images/ or labels/ under {src_split_dir}")
        return

    # Only real .txt label files (this naturally skips labels.cache, etc.).
    label_files = sorted(labels_dir.glob("*.txt"))
    counts[f"{out_split}_label_files_seen"] += len(label_files)

    out_images_dir = OUT_DIR / out_split / "images"
    out_labels_dir = OUT_DIR / out_split / "labels"

    for label_file in label_files:
        # 1) Build the output label lines (unchanged for v2, remapped for helmet).
        new_lines = read_label_lines(label_file, remap)
        if not new_lines:
            counts[f"{out_split}_skipped_no_useful_labels"] += 1
            continue

        # 2) Find the matching image; skip if it is missing.
        image_path = find_image_for_label(images_dir, label_file.stem)
        if image_path is None:
            counts[f"{out_split}_skipped_no_image"] += 1
            continue

        # 3) Prefixed output names so the two sources never collide.
        new_stem = f"{filename_prefix}{label_file.stem}"
        out_image = out_images_dir / f"{new_stem}{image_path.suffix.lower()}"
        out_label = out_labels_dir / f"{new_stem}.txt"

        # 4) Copy the image bytes (we never open/decode the picture).
        try:
            shutil.copy2(image_path, out_image)
        except OSError as exc:
            print(f"  [warn] failed to copy {image_path.name}: {exc}")
            counts[f"{out_split}_skipped_copy_error"] += 1
            continue

        # 5) Write the label file.
        with open(out_label, "w", encoding="utf-8") as f:
            f.write("\n".join(new_lines) + "\n")

        counts[f"{out_split}_images_written"] += 1
        counts[f"{out_split}_labels_written"] += 1

        # 6) Tally class instances for the summary.
        for line in new_lines:
            class_counter[int(line.split()[0])] += 1


def write_data_yaml() -> None:
    """Write v3/data.yaml in the exact format requested."""
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
    print("SafeVision AI - Build v3 dataset (v2 + helmet-no-helmet)")
    print("=" * 78)
    print(f"v2 source   : {V2_DIR}")
    print(f"helmet src  : {HELMET_DIR}")
    print(f"output (v3) : {OUT_DIR}")

    # Fail early and clearly if a source is missing.
    if not V2_DIR.exists():
        print(f"[error] v2 dataset not found: {V2_DIR}")
        return
    if not HELMET_DIR.exists():
        print(f"[error] helmet dataset not found: {HELMET_DIR}")
        return

    ensure_output_tree()

    counts = Counter()
    class_counter = Counter()

    # -----------------------------------------------------------
    # PASS 1 - copy v2 into v3 unchanged (remap=None).
    # v2 already uses the same train/valid/test split names.
    # -----------------------------------------------------------
    print("\n[1/2] Copying existing v2 dataset (unchanged) ...")
    for split in FINAL_SPLITS:
        src_split_dir = V2_DIR / split
        print(f"   - {split} -> {split}")
        process_split(
            src_split_dir=src_split_dir,
            out_split=split,
            remap=None,                 # None = copy labels verbatim
            filename_prefix="",         # v2 names already unique
            counts=counts,
            class_counter=class_counter,
        )

    # -----------------------------------------------------------
    # PASS 2 - add helmet-yolo with remapping + prefixes.
    # helmet-yolo already has train/valid/test, so we keep them as-is.
    # -----------------------------------------------------------
    print("\n[2/2] Adding helmet-yolo dataset (remapped) ...")
    for split in FINAL_SPLITS:
        src_split_dir = HELMET_DIR / split
        prefix = f"helmet_{split}_"
        print(f"   - {split} -> {split}  (prefix='{prefix}')")
        process_split(
            src_split_dir=src_split_dir,
            out_split=split,
            remap=HELMET_REMAP,
            filename_prefix=prefix,
            counts=counts,
            class_counter=class_counter,
        )

    # -----------------------------------------------------------
    # data.yaml
    # -----------------------------------------------------------
    write_data_yaml()

    # -----------------------------------------------------------
    # Summary
    # -----------------------------------------------------------
    print("\n" + "=" * 78)
    print("SUMMARY")
    print("=" * 78)
    print(f"Output path: {OUT_DIR}")

    total_skipped = 0
    total_errors = 0
    for split in FINAL_SPLITS:
        img_count = counts[f"{split}_images_written"]
        lbl_count = counts[f"{split}_labels_written"]
        seen = counts[f"{split}_label_files_seen"]
        skip_nolbl = counts[f"{split}_skipped_no_useful_labels"]
        skip_noimg = counts[f"{split}_skipped_no_image"]
        skip_copy = counts[f"{split}_skipped_copy_error"]
        total_skipped += skip_nolbl + skip_noimg
        total_errors += skip_copy
        print(f"\n[{split}]")
        print(f"   label files seen           : {seen}")
        print(f"   images written             : {img_count}")
        print(f"   labels written             : {lbl_count}")
        print(f"   skipped (no useful labels) : {skip_nolbl}")
        print(f"   skipped (image missing)    : {skip_noimg}")
        print(f"   errors  (copy failed)      : {skip_copy}")

    print("\nClass instance counts (final IDs):")
    for cls_id, cls_name in FINAL_NAMES.items():
        print(f"   {cls_id} {cls_name:<10}: {class_counter[cls_id]}")

    print(f"\nTotal images written : "
          f"{sum(counts[f'{s}_images_written'] for s in FINAL_SPLITS)}")
    print(f"Total skipped images : {total_skipped}")
    print(f"Total errors         : {total_errors}")
    print(f"\ndata.yaml written to : {OUT_YAML}")
    print("=" * 78)
    print("Done.")


if __name__ == "__main__":
    main()
