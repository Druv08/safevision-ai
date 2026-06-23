"""
SafeVision AI - Build the v5b (balanced) dataset = v3 + webcam (NO construction flood).

Why
---
v5 over-predicted helmet (false 'helmet' on a bare/headphoned head) because the
construction-helmet dataset added ~thousands of helmet POSITIVES with no
negatives, leaving a ~4:1 helmet:no_helmet imbalance. v5b drops that
construction data and keeps only:
    v3          (balanced helmet / no_helmet / vest / no_vest base)
    webcam-ppe  (your own domain frames: 243 helmet / 335 no_helmet + negatives)

To further fight the imbalance we OVERSAMPLE the webcam no_helmet frames
(duplicate them N times in train) so the model sees more "head without helmet".

Safety: copies only; modifies nothing; no training.
"""

import shutil
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATASETS = PROJECT_ROOT / "ai-model" / "datasets"

V3_DIR = DATASETS / "processed" / "safevision-ppe-5class-v3"
WEBCAM_DIR = DATASETS / "processed" / "webcam-ppe"
OUT_DIR = DATASETS / "processed" / "safevision-ppe-5class-v5b"

FINAL_NAMES = {0: "person", 1: "helmet", 2: "no_helmet", 3: "vest", 4: "no_vest"}
SPLITS = ("train", "valid", "test")
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp"}

# Duplicate each webcam no_helmet TRAIN frame this many times (1 = no oversample).
NO_HELMET_OVERSAMPLE = 3


def ensure_tree():
    for s in SPLITS:
        (OUT_DIR / s / "images").mkdir(parents=True, exist_ok=True)
        (OUT_DIR / s / "labels").mkdir(parents=True, exist_ok=True)


def find_image(images_dir, stem):
    for ext in IMAGE_EXTS:
        c = images_dir / f"{stem}{ext}"
        if c.exists():
            return c
    return None


def label_classes(label_file):
    out = []
    for line in label_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(int(line.split()[0]))
    return out


def copy_split(src_dir, split, prefix, counts, class_counter, oversample_no_helmet=False):
    labels_dir = src_dir / split / "labels"
    images_dir = src_dir / split / "images"
    if not labels_dir.exists() or not images_dir.exists():
        print(f"  [warn] missing under {src_dir / split}")
        return
    for label_file in sorted(labels_dir.glob("*.txt")):
        image_path = find_image(images_dir, label_file.stem)
        if image_path is None:
            counts[f"{split}_skipped_no_image"] += 1
            continue
        classes = label_classes(label_file)

        # How many copies to write?
        reps = 1
        if (oversample_no_helmet and split == "train"
                and classes and all(c == 2 for c in classes)):
            reps = NO_HELMET_OVERSAMPLE

        for r in range(reps):
            tag = f"{prefix}" if r == 0 else f"{prefix}dup{r}_"
            new_stem = f"{tag}{label_file.stem}"
            shutil.copy2(image_path,
                         OUT_DIR / split / "images" / f"{new_stem}{image_path.suffix.lower()}")
            shutil.copy2(label_file,
                         OUT_DIR / split / "labels" / f"{new_stem}.txt")
            counts[f"{split}_images_written"] += 1
            for c in classes:
                class_counter[c] += 1


def write_data_yaml():
    lines = ["train: train/images", "val: valid/images", "test: test/images",
             "", f"nc: {len(FINAL_NAMES)}", "", "names:"]
    for cid, cname in FINAL_NAMES.items():
        lines.append(f"  {cid}: {cname}")
    (OUT_DIR / "data.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    print("=" * 70)
    print("SafeVision AI - Build v5b BALANCED dataset (v3 + webcam, no construction)")
    print("=" * 70)
    print(f"v3 source     : {V3_DIR}")
    print(f"webcam source : {WEBCAM_DIR}  (no_helmet train oversample x{NO_HELMET_OVERSAMPLE})")
    print(f"output (v5b)  : {OUT_DIR}")
    if not V3_DIR.exists() or not WEBCAM_DIR.exists():
        print("[error] a source dataset is missing."); return

    ensure_tree()
    counts = Counter()
    class_counter = Counter()

    print("\n[1/2] Copying v3 ...")
    for s in SPLITS:
        copy_split(V3_DIR, s, "", counts, class_counter)

    print("[2/2] Copying webcam-ppe (oversampling no_helmet in train) ...")
    for s in SPLITS:
        copy_split(WEBCAM_DIR, s, "wc_", counts, class_counter,
                   oversample_no_helmet=True)

    write_data_yaml()

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    for s in SPLITS:
        print(f"  {s:6s}: {counts[f'{s}_images_written']} images")
    print("\nClass instance counts:")
    for cid, cname in FINAL_NAMES.items():
        print(f"   {cid} {cname:<10}: {class_counter[cid]}")
    print(f"\nTotal images: {sum(counts[f'{s}_images_written'] for s in SPLITS)}")
    print(f"data.yaml   : {OUT_DIR / 'data.yaml'}")
    print("=" * 70)


if __name__ == "__main__":
    main()
