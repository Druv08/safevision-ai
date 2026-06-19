"""
build_safevision_5class_dataset.py
----------------------------------
Rebuild the processed SafeVision 5-class dataset from the two raw YOLO datasets.

Final class order:
0 = person
1 = helmet
2 = no_helmet
3 = vest
4 = no_vest

The script copies only the useful labels, remaps them to the final IDs, and
preserves the train/valid/test split layout.
"""

from __future__ import annotations

import shutil
import sys
import traceback
from dataclasses import dataclass
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent

RAW_DATASETS = {
    "construction-safety-yolo": PROJECT_ROOT / "ai-model" / "datasets" / "raw" / "construction-safety-yolo",
    "vest-no-vest": PROJECT_ROOT / "ai-model" / "datasets" / "raw" / "vest-no-vest",
}

OUTPUT_ROOT = PROJECT_ROOT / "ai-model" / "datasets" / "processed" / "safevision-ppe-5class"

TARGET_CLASS_NAMES = ["person", "helmet", "no_helmet", "vest", "no_vest"]

CONSTRUCTION_CLASS_MAP = {
    4: 1,
    6: 2,
    8: 4,
    9: 0,
    12: 3,
}

VEST_CLASS_MAP = {
    0: 4,
    1: 3,
}

TARGET_SPLITS = ("train", "valid", "test")
IMAGE_SUFFIXES = (".jpg", ".jpeg", ".png", ".bmp", ".webp")


@dataclass
class BuildStats:
    copied_images: int = 0
    copied_labels: int = 0
    skipped_missing_images: int = 0
    skipped_empty_labels: int = 0


def ensure_output_tree() -> None:
    """Create the YOLO split folders for the processed dataset."""
    for split in TARGET_SPLITS:
        (OUTPUT_ROOT / split / "images").mkdir(parents=True, exist_ok=True)
        (OUTPUT_ROOT / split / "labels").mkdir(parents=True, exist_ok=True)


def clean_output_root() -> None:
    """Remove any previous processed dataset so the build is reproducible."""
    if OUTPUT_ROOT.exists():
        shutil.rmtree(OUTPUT_ROOT)
    ensure_output_tree()


def find_image(label_path: Path) -> Path | None:
    """Find the image file that matches a YOLO label file."""
    image_dir = label_path.parent.parent / "images"
    for suffix in IMAGE_SUFFIXES:
        candidate = image_dir / f"{label_path.stem}{suffix}"
        if candidate.is_file():
            return candidate
    return None


def remap_labels(label_path: Path, class_map: dict[int, int]) -> list[str]:
    """Keep only target classes and rewrite class IDs to the final 5-class map."""
    remapped: list[str] = []

    for raw_line in label_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue

        parts = line.split()
        if len(parts) < 5:
            continue

        try:
            source_class_id = int(parts[0])
        except ValueError:
            continue

        target_class_id = class_map.get(source_class_id)
        if target_class_id is None:
            continue

        remapped.append(f"{target_class_id} {' '.join(parts[1:5])}")

    return remapped


def copy_sample(
    *,
    sample_prefix: str,
    split: str,
    label_path: Path,
    class_map: dict[int, int],
    stats: BuildStats,
) -> None:
    """Copy one image/label pair if it contains at least one target label."""
    image_path = find_image(label_path)
    if image_path is None:
        stats.skipped_missing_images += 1
        return

    remapped_lines = remap_labels(label_path, class_map)
    if not remapped_lines:
        stats.skipped_empty_labels += 1
        return

    # Keep the generated filename short so Windows path limits are not hit.
    new_stem = sample_prefix
    target_image_path = OUTPUT_ROOT / split / "images" / f"{new_stem}{image_path.suffix.lower()}"
    target_label_path = OUTPUT_ROOT / split / "labels" / f"{new_stem}.txt"

    target_image_path.parent.mkdir(parents=True, exist_ok=True)
    target_label_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        shutil.copy2(image_path, target_image_path)
    except Exception:
        print(f"[DEBUG] copy2 failed for source: {image_path}")
        print(f"[DEBUG] copy2 failed for destination: {target_image_path}")
        raise
    target_label_path.write_text("\n".join(remapped_lines) + "\n", encoding="utf-8")

    stats.copied_images += 1
    stats.copied_labels += 1


def process_split(dataset_root: Path, source_name: str, split: str, class_map: dict[int, int], stats: BuildStats) -> None:
    """Process one split from one raw dataset."""
    split_dir = dataset_root / split
    labels_dir = split_dir / "labels"

    if not split_dir.is_dir() or not labels_dir.is_dir():
        print(f"  {split:<5} skipped (missing split)")
        return

    for index, label_path in enumerate(sorted(labels_dir.glob("*.txt")), start=1):
        sample_prefix = f"{source_name[:3]}_{split[:3]}_{index:06d}"
        copy_sample(
            sample_prefix=sample_prefix,
            split=split,
            label_path=label_path,
            class_map=class_map,
            stats=stats,
        )


def write_data_yaml() -> None:
    """Write a YOLO data.yaml that resolves correctly from the project root."""
    data_yaml = OUTPUT_ROOT / "data.yaml"
    content = (
        "path: ai-model/datasets/processed/safevision-ppe-5class\n"
        "train: train/images\n"
        "val: valid/images\n"
        "test: test/images\n\n"
        "nc: 5\n"
        "names: [\"person\", \"helmet\", \"no_helmet\", \"vest\", \"no_vest\"]\n"
    )
    data_yaml.write_text(content, encoding="utf-8")


def verify_sources() -> None:
    """Fail fast if the expected raw dataset folders are missing."""
    missing = [root for root in RAW_DATASETS.values() if not root.is_dir()]
    if missing:
        print("[ERROR] Missing raw dataset folder(s):")
        for root in missing:
            print(f"  - {root}")
        raise SystemExit(1)


def main() -> int:
    print("=" * 72)
    print("SafeVision AI - 5-class dataset builder")
    print("=" * 72)
    print(f"Output dataset : {OUTPUT_ROOT}")
    print(f"Final classes  : {', '.join(TARGET_CLASS_NAMES)}")
    for name, root in RAW_DATASETS.items():
        print(f"Source         : {name} -> {root}")
    print("=" * 72)

    try:
        verify_sources()
        clean_output_root()

        stats = BuildStats()
        for source_name, dataset_root in RAW_DATASETS.items():
            class_map = CONSTRUCTION_CLASS_MAP if source_name == "construction-safety-yolo" else VEST_CLASS_MAP
            print(f"\nProcessing source dataset: {source_name}")
            for split in TARGET_SPLITS:
                before_images = stats.copied_images
                process_split(dataset_root, source_name, split, class_map, stats)
                copied_delta = stats.copied_images - before_images
                if (dataset_root / split / "labels").is_dir():
                    print(f"  {split:<5} copied={copied_delta}")

        write_data_yaml()

        print("\n" + "=" * 72)
        print("Dataset build complete")
        print("=" * 72)
        print(f"Processed dataset : {OUTPUT_ROOT}")
        print(f"Copied images     : {stats.copied_images}")
        print(f"Copied labels     : {stats.copied_labels}")
        print(f"Missing images    : {stats.skipped_missing_images}")
        print(f"Empty labels      : {stats.skipped_empty_labels}")
        print(f"data.yaml         : {OUTPUT_ROOT / 'data.yaml'}")
        print("=" * 72)
        return 0
    except Exception as exc:
        print(f"\n[ERROR] Dataset build failed: {exc}")
        print(traceback.format_exc())
        return 1


if __name__ == "__main__":
    sys.exit(main())