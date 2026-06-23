"""
SafeVision AI - Build the v4 dataset (v3 + extra construction-helmet data).

Plain-English overview
-----------------------
v3 is our current, working 5-class dataset:
    ai-model/datasets/processed/safevision-ppe-5class-v3/
    classes: 0=person, 1=helmet, 2=no_helmet, 3=vest, 4=no_vest

We downloaded ANOTHER helmet dataset ("Construction Helmet Detection", v2,
from Roboflow) to give the model many more helmet examples, because helmet
detection on the live webcam was weak (a domain-shift problem).

    raw/construction-helmet-detection-v2/
    classes: 0 = "construction helmet"   (helmet positives ONLY)

Two things make this dataset different from helmet-yolo:
  1. It has only ONE class (helmet). There is no head / no_helmet / person,
     so it adds helmet POSITIVES only -- it cannot teach "no_helmet".
  2. Its labels are SEGMENTATION POLYGONS, not detection boxes. Each line is
        <class> x1 y1 x2 y2 x3 y3 ...   (many points)
     but our model is a DETECTION model that needs
        <class> cx cy w h
     so we convert every polygon to its tight bounding box.

This script builds a brand-new v4 dataset in two passes:

  PASS 1 - Copy v3 into v4 UNCHANGED (remap=None, no polygon conversion).
           v3 is already final-schema detection boxes, so we copy bytes.

  PASS 2 - Add construction-helmet-detection-v2 with:
               class remap : 0 ("construction helmet") -> 1 (helmet)
               polygon -> bounding-box conversion for every label line
               filename prefix chd_train_ / chd_valid_ / chd_test_
           Only images that still have >=1 valid label are copied.

Safety guarantees
-----------------
  - Does NOT modify the raw construction-helmet dataset.
  - Does NOT modify the v3 processed dataset.
  - Does NOT delete anything (helmet-yolo etc. are left untouched).
  - Does NOT train anything (see train_safevision_v4.py for that).
  - Output lives under processed/ (gitignored).
"""

import shutil
from collections import Counter
from pathlib import Path

# ---------------------------------------------------------------
# Paths
# ---------------------------------------------------------------
# __file__ = ai-model/training/build_safevision_v4_helmet_dataset.py
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATASETS = PROJECT_ROOT / "ai-model" / "datasets"

# Source A: the existing, working v3 dataset (already final 5-class schema).
V3_DIR = DATASETS / "processed" / "safevision-ppe-5class-v3"

# Source B: the new raw construction-helmet dataset (1 class, polygon labels).
CHD_DIR = DATASETS / "raw" / "construction-helmet-detection-v2"

# Destination: the new combined v4 dataset.
OUT_DIR = DATASETS / "processed" / "safevision-ppe-5class-v4"
OUT_YAML = OUT_DIR / "data.yaml"

# Final unified class schema (unchanged from v3).
FINAL_NAMES = {
    0: "person",
    1: "helmet",
    2: "no_helmet",
    3: "vest",
    4: "no_vest",
}

# Construction-helmet remap: its only class (0 = construction helmet) becomes
# our helmet class (1). Anything else is unexpected and dropped.
CHD_REMAP = {
    0: 1,  # construction helmet -> helmet
}

FINAL_SPLITS = ("train", "valid", "test")
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp"}


# ---------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------
def ensure_output_tree() -> None:
    """Create v4/{train,valid,test}/{images,labels} if they don't exist yet."""
    for split in FINAL_SPLITS:
        (OUT_DIR / split / "images").mkdir(parents=True, exist_ok=True)
        (OUT_DIR / split / "labels").mkdir(parents=True, exist_ok=True)


def find_image_for_label(images_dir: Path, label_stem: str):
    """Find the image file that matches a label file (same name, image ext)."""
    for ext in IMAGE_EXTS:
        candidate = images_dir / f"{label_stem}{ext}"
        if candidate.exists():
            return candidate
    return None


def _clamp01(v: float) -> float:
    """Keep a normalized coordinate inside [0, 1]."""
    return 0.0 if v < 0.0 else (1.0 if v > 1.0 else v)


def coords_to_bbox_line(new_id: int, coords: list[float]):
    """Turn label coordinates into one detection line '<id> cx cy w h'.

    Handles BOTH input shapes:
      * already a box -> exactly 4 numbers (cx cy w h): kept (clamped).
      * a polygon     -> >=6 numbers (x1 y1 x2 y2 ...): converted to the
                         tight bounding box around all the points.

    Returns the formatted string, or None if the geometry is degenerate
    (zero width/height) or malformed.
    """
    n = len(coords)

    if n == 4:
        # Already a YOLO detection box.
        cx, cy, w, h = coords
    elif n >= 6 and n % 2 == 0:
        # Polygon: x's are even indices, y's are odd indices.
        xs = coords[0::2]
        ys = coords[1::2]
        xmin, xmax = min(xs), max(xs)
        ymin, ymax = min(ys), max(ys)
        w = xmax - xmin
        h = ymax - ymin
        cx = xmin + w / 2.0
        cy = ymin + h / 2.0
    else:
        return None  # 5 tokens, odd polygon, etc. -> can't interpret

    cx, cy = _clamp01(cx), _clamp01(cy)
    w, h = _clamp01(w), _clamp01(h)
    if w <= 0.0 or h <= 0.0:
        return None

    return f"{new_id} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}"


def read_label_lines(label_path: Path, remap, convert_polygons: bool):
    """Read a YOLO label file and return its output lines.

    remap=None             -> copy each line verbatim (used for v3).
    remap={old:new}         -> keep only known classes, swap the class id.
    convert_polygons=True   -> treat coords as polygons and convert to boxes
                               (used for the construction-helmet dataset).
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
                    out_lines.append(line)            # v3: verbatim
                    continue

                if old_id not in remap:
                    continue                          # unrelated class -> drop
                new_id = remap[old_id]

                if not convert_polygons:
                    out_lines.append(" ".join([str(new_id)] + parts[1:]))
                    continue

                # Polygon / box -> bounding-box detection line.
                try:
                    coords = [float(p) for p in parts[1:]]
                except ValueError:
                    continue
                bbox_line = coords_to_bbox_line(new_id, coords)
                if bbox_line is not None:
                    out_lines.append(bbox_line)
    except OSError:
        return []
    return out_lines


def process_split(
    src_split_dir: Path,
    out_split: str,
    remap,
    convert_polygons: bool,
    filename_prefix: str,
    counts: Counter,
    class_counter: Counter,
) -> None:
    """Copy one source split's images+labels into the v4 output split."""
    labels_dir = src_split_dir / "labels"
    images_dir = src_split_dir / "images"

    if not labels_dir.exists() or not images_dir.exists():
        print(f"  [warn] missing images/ or labels/ under {src_split_dir}")
        return

    label_files = sorted(labels_dir.glob("*.txt"))
    counts[f"{out_split}_label_files_seen"] += len(label_files)

    out_images_dir = OUT_DIR / out_split / "images"
    out_labels_dir = OUT_DIR / out_split / "labels"

    for label_file in label_files:
        new_lines = read_label_lines(label_file, remap, convert_polygons)
        if not new_lines:
            counts[f"{out_split}_skipped_no_useful_labels"] += 1
            continue

        image_path = find_image_for_label(images_dir, label_file.stem)
        if image_path is None:
            counts[f"{out_split}_skipped_no_image"] += 1
            continue

        new_stem = f"{filename_prefix}{label_file.stem}"
        out_image = out_images_dir / f"{new_stem}{image_path.suffix.lower()}"
        out_label = out_labels_dir / f"{new_stem}.txt"

        try:
            shutil.copy2(image_path, out_image)
        except OSError as exc:
            print(f"  [warn] failed to copy {image_path.name}: {exc}")
            counts[f"{out_split}_skipped_copy_error"] += 1
            continue

        with open(out_label, "w", encoding="utf-8") as f:
            f.write("\n".join(new_lines) + "\n")

        counts[f"{out_split}_images_written"] += 1
        counts[f"{out_split}_labels_written"] += 1
        for line in new_lines:
            class_counter[int(line.split()[0])] += 1


def write_data_yaml() -> None:
    """Write v4/data.yaml (same schema/format as v3)."""
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
    print("SafeVision AI - Build v4 dataset (v3 + construction-helmet)")
    print("=" * 78)
    print(f"v3 source   : {V3_DIR}")
    print(f"helmet src  : {CHD_DIR}")
    print(f"output (v4) : {OUT_DIR}")

    if not V3_DIR.exists():
        print(f"[error] v3 dataset not found: {V3_DIR}")
        return
    if not CHD_DIR.exists():
        print(f"[error] construction-helmet dataset not found: {CHD_DIR}")
        return

    ensure_output_tree()

    counts = Counter()
    class_counter = Counter()

    # PASS 1 - copy v3 into v4 unchanged.
    print("\n[1/2] Copying existing v3 dataset (unchanged) ...")
    for split in FINAL_SPLITS:
        print(f"   - {split} -> {split}")
        process_split(
            src_split_dir=V3_DIR / split,
            out_split=split,
            remap=None,
            convert_polygons=False,
            filename_prefix="",
            counts=counts,
            class_counter=class_counter,
        )

    # PASS 2 - add construction-helmet (remap 0->1, polygons -> boxes).
    print("\n[2/2] Adding construction-helmet-detection-v2 (remap + polygon->box) ...")
    for split in FINAL_SPLITS:
        prefix = f"chd_{split}_"
        print(f"   - {split} -> {split}  (prefix='{prefix}')")
        process_split(
            src_split_dir=CHD_DIR / split,
            out_split=split,
            remap=CHD_REMAP,
            convert_polygons=True,
            filename_prefix=prefix,
            counts=counts,
            class_counter=class_counter,
        )

    write_data_yaml()

    # Summary
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
    print("Done. Next: train on v4 (see train_safevision_v4.py).")


if __name__ == "__main__":
    main()
