"""
SafeVision AI - Build the v5 dataset (v4 + auto-labeled WEBCAM frames).

v5 = everything we have:
    v4  = v3 (person/helmet/no_helmet/vest/no_vest) + construction-helmet positives
    +  webcam-ppe = your own webcam frames, auto-labeled by pose into
                    helmet / no_helmet (built by autolabel_webcam_pose.py)

Both sources are already in the final 5-class schema, so this is a pure copy
merge (no remapping, no conversion). Filenames are already unique between the
two sources (webcam files start with 'webcam_'), but we still prefix to be safe.

Safety: does not modify v4 or webcam-ppe; does not delete anything; no training.
"""

import shutil
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATASETS = PROJECT_ROOT / "ai-model" / "datasets"

V4_DIR = DATASETS / "processed" / "safevision-ppe-5class-v4"
WEBCAM_DIR = DATASETS / "processed" / "webcam-ppe"
OUT_DIR = DATASETS / "processed" / "safevision-ppe-5class-v5"

FINAL_NAMES = {0: "person", 1: "helmet", 2: "no_helmet", 3: "vest", 4: "no_vest"}
SPLITS = ("train", "valid", "test")
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp"}


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


def copy_split(src_dir, split, prefix, counts, class_counter):
    labels_dir = src_dir / split / "labels"
    images_dir = src_dir / split / "images"
    if not labels_dir.exists() or not images_dir.exists():
        print(f"  [warn] missing images/ or labels/ under {src_dir / split}")
        return
    for label_file in sorted(labels_dir.glob("*.txt")):
        image_path = find_image(images_dir, label_file.stem)
        if image_path is None:
            counts[f"{split}_skipped_no_image"] += 1
            continue
        new_stem = f"{prefix}{label_file.stem}"
        shutil.copy2(image_path,
                     OUT_DIR / split / "images" / f"{new_stem}{image_path.suffix.lower()}")
        shutil.copy2(label_file,
                     OUT_DIR / split / "labels" / f"{new_stem}.txt")
        counts[f"{split}_images_written"] += 1
        # tally classes
        for line in label_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                class_counter[int(line.split()[0])] += 1


def write_data_yaml():
    lines = ["train: train/images", "val: valid/images", "test: test/images",
             "", f"nc: {len(FINAL_NAMES)}", "", "names:"]
    for cid, cname in FINAL_NAMES.items():
        lines.append(f"  {cid}: {cname}")
    (OUT_DIR / "data.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    print("=" * 70)
    print("SafeVision AI - Build v5 dataset (v4 + webcam)")
    print("=" * 70)
    print(f"v4 source     : {V4_DIR}")
    print(f"webcam source : {WEBCAM_DIR}")
    print(f"output (v5)   : {OUT_DIR}")
    if not V4_DIR.exists():
        print(f"[error] v4 not found: {V4_DIR}"); return
    if not WEBCAM_DIR.exists():
        print(f"[error] webcam-ppe not found: {WEBCAM_DIR}"); return

    ensure_tree()
    counts = Counter()
    class_counter = Counter()

    print("\n[1/2] Copying v4 ...")
    for s in SPLITS:
        copy_split(V4_DIR, s, "", counts, class_counter)

    print("[2/2] Copying webcam-ppe ...")
    for s in SPLITS:
        copy_split(WEBCAM_DIR, s, "wc_", counts, class_counter)

    write_data_yaml()

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    for s in SPLITS:
        print(f"  {s:6s}: {counts[f'{s}_images_written']} images "
              f"(skipped no-image: {counts[f'{s}_skipped_no_image']})")
    print("\nClass instance counts:")
    for cid, cname in FINAL_NAMES.items():
        print(f"   {cid} {cname:<10}: {class_counter[cid]}")
    print(f"\nTotal images: {sum(counts[f'{s}_images_written'] for s in SPLITS)}")
    print(f"data.yaml   : {OUT_DIR / 'data.yaml'}")
    print("=" * 70)
    print("Next: train  ->  ai-model/training/train_safevision_v5.py --from-v3 --fast")


if __name__ == "__main__":
    main()
