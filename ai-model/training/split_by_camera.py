"""
Split a YOLO dataset into train / val / test by camera or source, so frames of
the same scene never end up on both sides of the split.

Random image-level splits leak: consecutive frames of one webcam session, or
the augmented copies Roboflow exports ("frame_12_jpg.rf.<hash>.jpg"), are
near-duplicates, so a model can score well on "test" images it has effectively
seen. Here every image gets a group key (its camera / session / source image)
and whole groups are assigned to one split.

Group key, in order of preference:
  --group-map map.csv   columns `image,group` (image = file name or stem)
  --group-regex REGEX   applied to the cleaned file stem; the named group
                        `group` (or the whole match) is the key
  default               the cleaned stem minus a trailing frame number, e.g.
                        webcam_s03_000417 -> webcam_s03, IMG_2041 -> IMG
"Cleaned" means the Roboflow suffix (_jpg.rf.<hash>) is removed first.

Check the printed group list: if the default lumps unrelated images together or
splits one scene into many groups, pass --group-regex or --group-map.

All existing splits of DATASET are pooled and re-split.

Usage:
    python ai-model/training/split_by_camera.py ai-model/datasets/processed/safevision-ppe-5class-v5d \\
        ai-model/datasets/processed/v5d-by-camera --test-frac 0.2 --val-frac 0.1 --seed 42

Writes OUT/{train,val,test}/{images,labels}, OUT/data.yaml and
OUT/split_manifest.json (which group went where, counts, seed).
"""

import argparse
import csv
import json
import os
import random
import re
import shutil
import sys
from collections import defaultdict
from pathlib import Path

import yaml

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
ROBOFLOW_SUFFIX = re.compile(r"(_(jpe?g|png|bmp|webp))?\.rf\.[0-9a-f]+$", re.IGNORECASE)
DEFAULT_REGEX = r"^(?P<group>.*?)[_\-. ]*\d+$"
SPLITS = ("train", "val", "test")


def clean_stem(name: str) -> str:
    return ROBOFLOW_SUFFIX.sub("", Path(name).stem)


def group_key(name: str, regex: str = DEFAULT_REGEX) -> str:
    stem = clean_stem(name)
    m = re.search(regex, stem)
    if not m:
        return stem
    key = m.groupdict().get("group", m.group(0))
    return key or stem


def assign_groups(sizes: dict[str, int], test_frac: float, val_frac: float, seed: int) -> dict[str, str]:
    """
    {group: split}. Groups are shuffled with `seed`; each goes to test, else val,
    while that split is under its target and the group would not overshoot it by
    more than 5 % of all images; everything else goes to train.
    """
    groups = sorted(sizes)
    random.Random(seed).shuffle(groups)
    total = sum(sizes.values())
    slack = 0.05 * total
    targets = [("test", test_frac * total), ("val", val_frac * total)]
    out, filled = {}, defaultdict(int)
    for g in groups:
        split = next(
            (s for s, target in targets if filled[s] < target and filled[s] + sizes[g] <= target + slack),
            "train",
        )
        out[g] = split
        filled[split] += sizes[g]
    return out


def find_pairs(root: Path) -> list[tuple[Path, Path | None]]:
    """(image, label) for every image under root/**/images/ (label may be missing = background)."""
    pairs = []
    for img in sorted(root.rglob("*")):
        if img.suffix.lower() in IMAGE_EXTS and img.parent.name == "images":
            label = img.parent.parent / "labels" / (img.stem + ".txt")
            pairs.append((img, label if label.is_file() else None))
    return pairs


def load_group_map(path: Path) -> dict[str, str]:
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    out = {}
    for r in rows:
        out[r["image"]] = r["group"]
        out[Path(r["image"]).stem] = r["group"]
    return out


def _place(src: Path, dst: Path, link: bool) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if link:
        try:
            os.link(src, dst)
            return
        except OSError:
            pass
    shutil.copy2(src, dst)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dataset", type=Path, help="YOLO dataset folder (with data.yaml)")
    ap.add_argument("out", type=Path, help="output folder (must not exist)")
    ap.add_argument("--test-frac", type=float, default=0.2)
    ap.add_argument("--val-frac", type=float, default=0.1)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--group-regex", default=DEFAULT_REGEX)
    ap.add_argument("--group-map", type=Path)
    ap.add_argument("--link", action="store_true", help="hard-link files instead of copying")
    ap.add_argument("--min-groups", type=int, default=10,
                    help="refuse to split with fewer groups than this (default 10)")
    args = ap.parse_args(argv)

    data_yaml = args.dataset / "data.yaml"
    if not data_yaml.is_file():
        sys.exit(f"[ERROR] {data_yaml} not found")
    if args.out.exists():
        sys.exit(f"[ERROR] {args.out} already exists")
    names = yaml.safe_load(data_yaml.read_text(encoding="utf-8"))["names"]

    pairs = find_pairs(args.dataset)
    if not pairs:
        sys.exit(f"[ERROR] no images under {args.dataset}/**/images/")
    gmap = load_group_map(args.group_map) if args.group_map else None
    missing = []
    group_of = {}
    for img, _ in pairs:
        if gmap is not None:
            g = gmap.get(img.name) or gmap.get(img.stem) or gmap.get(clean_stem(img.name))
            if g is None:
                missing.append(img.name)
                continue
        else:
            g = group_key(img.name, args.group_regex)
        group_of[img] = g
    if missing:
        sys.exit(f"[ERROR] {len(missing)} images are not in {args.group_map}, e.g. {missing[:3]}")

    sizes = defaultdict(int)
    for g in group_of.values():
        sizes[g] += 1
    if len(sizes) < args.min_groups:
        biggest = ", ".join(f"{g} ({n})" for g, n in sorted(sizes.items(), key=lambda kv: -kv[1])[:5])
        sys.exit(f"[ERROR] only {len(sizes)} groups ({biggest}). The file names do not identify cameras or "
                 "sessions; pass --group-regex or --group-map (or --min-groups to override).")
    split_of = assign_groups(dict(sizes), args.test_frac, args.val_frac, args.seed)

    counts = defaultdict(int)
    used_names = defaultdict(set)
    for img, label in pairs:
        split = split_of[group_of[img]]
        name = img.name
        if name in used_names[split]:  # same file name from two source splits
            name = f"{img.parent.parent.name}_{name}"
        used_names[split].add(name)
        _place(img, args.out / split / "images" / name, args.link)
        if label is not None:
            _place(label, args.out / split / "labels" / (Path(name).stem + ".txt"), args.link)
        counts[split] += 1

    # The whole point: no group may appear in two splits.
    by_split = {s: sorted(g for g, sp in split_of.items() if sp == s) for s in SPLITS}
    assert not (set(by_split["train"]) & set(by_split["test"]) or set(by_split["val"]) & set(by_split["test"]))

    (args.out / "data.yaml").write_text(
        yaml.safe_dump({"path": str(args.out.resolve()), "train": "train/images", "val": "val/images",
                        "test": "test/images", "names": names}, sort_keys=False),
        encoding="utf-8",
    )
    manifest = {
        "source": str(args.dataset.resolve()),
        "seed": args.seed,
        "group_regex": None if gmap else args.group_regex,
        "group_map": str(args.group_map) if gmap else None,
        "images": dict(counts),
        "groups": {s: len(by_split[s]) for s in SPLITS},
        "split_of_group": by_split,
    }
    (args.out / "split_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    total = sum(counts.values())
    print(f"{total} images, {len(sizes)} groups -> {args.out}")
    for s in SPLITS:
        print(f"  {s:5}: {counts[s]:6} images ({counts[s] / total:5.1%}) in {len(by_split[s])} groups")
    biggest = sorted(sizes.items(), key=lambda kv: -kv[1])[:10]
    print("Largest groups (check these are real cameras / sessions):")
    for g, n in biggest:
        print(f"  {n:6}  {g}  -> {split_of[g]}")
    singletons = sum(1 for n in sizes.values() if n == 1)
    if singletons > 0.5 * len(sizes):
        print(f"[WARN] {singletons} of {len(sizes)} groups have one image: the grouping may not reflect "
              "cameras; consider --group-regex or --group-map.")
    if min(len(by_split["test"]), len(by_split["val"]) if args.val_frac else 1) < 3:
        print("[WARN] fewer than 3 groups in a held-out split: results will depend heavily on those scenes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
