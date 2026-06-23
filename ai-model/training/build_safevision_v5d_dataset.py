"""
SafeVision AI - Build v5d = v3 + corrected webcam helmet labels (webcam-ppe-v5d).

v5d base is v3 ONLY (person/helmet/no_helmet/vest/no_vest). We deliberately do
NOT use v5b or v5c as the base: their webcam HELMET labels were pose-derived and
tracked the head (head=helmet bug). v5d adds webcam-ppe-v5d, whose helmet labels
are TIGHT yellow-hardhat-shell boxes and whose no_helmet labels are head boxes
(held helmet ignored). vest / no_vest come from v3 unchanged.

--oversample N : duplicate each webcam no_helmet TRAIN frame N times (default 1).

Safety: copies only; no construction flood; no training; no commit.
"""

import argparse
import shutil
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATASETS = PROJECT_ROOT / "ai-model" / "datasets"
V3_DIR = DATASETS / "processed" / "safevision-ppe-5class-v3"
WEBCAM_DIR = DATASETS / "processed" / "webcam-ppe-v5d"
OUT_DIR = DATASETS / "processed" / "safevision-ppe-5class-v5d"

FINAL_NAMES = {0: "person", 1: "helmet", 2: "no_helmet", 3: "vest", 4: "no_vest"}
SPLITS = ("train", "valid", "test")
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp"}


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--oversample", type=int, default=1,
                   help="Duplicate each webcam no_helmet TRAIN frame N times (default 1).")
    return p.parse_args()


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


def copy_split(src_dir, split, prefix, counts, cc, oversample=1):
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
        reps = 1
        if (oversample > 1 and split == "train"
                and classes and all(c == 2 for c in classes)):
            reps = oversample
        for r in range(reps):
            tag = prefix if r == 0 else f"{prefix}dup{r}_"
            new_stem = f"{tag}{label_file.stem}"
            shutil.copy2(image_path,
                         OUT_DIR / split / "images" / f"{new_stem}{image_path.suffix.lower()}")
            shutil.copy2(label_file,
                         OUT_DIR / split / "labels" / f"{new_stem}.txt")
            counts[f"{split}_images_written"] += 1
            for c in classes:
                cc[c] += 1


def write_data_yaml():
    lines = ["train: train/images", "val: valid/images", "test: test/images",
             "", f"nc: {len(FINAL_NAMES)}", "", "names:"]
    for cid, cname in FINAL_NAMES.items():
        lines.append(f"  {cid}: {cname}")
    (OUT_DIR / "data.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    args = parse_args()
    print("=" * 70)
    print(f"SafeVision AI - Build v5d (v3 + webcam-ppe-v5d, oversample x{args.oversample})")
    print("=" * 70)
    print(f"v3 base       : {V3_DIR}")
    print(f"webcam (v5d)  : {WEBCAM_DIR}")
    print(f"output (v5d)  : {OUT_DIR}")
    if not V3_DIR.exists():
        print(f"[ERROR] v3 base not found: {V3_DIR}"); return 1
    if not WEBCAM_DIR.exists():
        print(f"[ERROR] webcam-ppe-v5d not found (run prepare_v5d_helmet_labels.py): {WEBCAM_DIR}")
        return 1

    ensure_tree()
    counts = Counter()
    cc = Counter()

    print("[1/2] Copying v3 base ...")
    for s in SPLITS:
        copy_split(V3_DIR, s, "", counts, cc)
    print("[2/2] Copying webcam-ppe-v5d (corrected helmet labels) ...")
    for s in SPLITS:
        copy_split(WEBCAM_DIR, s, "wc5d_", counts, cc, oversample=args.oversample)

    write_data_yaml()

    helmet, nohelmet, vest, novest = cc[1], cc[2], cc[3], cc[4]
    total_imgs = sum(counts[f"{s}_images_written"] for s in SPLITS)
    skipped = sum(counts[f"{s}_skipped_no_image"] for s in SPLITS)
    print("\n" + "=" * 70)
    print("v5d DATASET SUMMARY")
    print("=" * 70)
    for s in SPLITS:
        print(f"  {s:6s}: {counts[f'{s}_images_written']} images "
              f"(skipped no-image: {counts[f'{s}_skipped_no_image']})")
    print("\nClass instance counts:")
    for cid, cname in FINAL_NAMES.items():
        print(f"   {cid} {cname:<10}: {cc[cid]}")
    print(f"\nhelmet count     : {helmet}")
    print(f"no_helmet count  : {nohelmet}")
    print(f"helmet:no_helmet : {helmet}:{nohelmet} ({helmet/max(nohelmet,1):.2f}:1)")
    print(f"vest count       : {vest}")
    print(f"no_vest count    : {novest}")
    print(f"vest:no_vest     : {vest}:{novest} ({vest/max(novest,1):.2f}:1)")
    print(f"\nTotal images     : {total_imgs}")
    print(f"Skipped frames   : {skipped}")
    print(f"data.yaml        : {OUT_DIR / 'data.yaml'}")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
