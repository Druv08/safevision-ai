"""
SafeVision AI - v5c webcam prep: extract + pose-autolabel hard-negative clips.

Scope (confirmed with user):
  * HELMET hard negatives only -- NO vest labeling (no clip contains a vest).
  * Re-extract ALL 4 clips fresh (head-only labels: helmet / no_helmet).
  * Held helmet is NEVER labeled as `helmet`: we only ever label the worker's
    HEAD region, so a helmet held in the hand is simply not labeled (ignored).
  * Reuses the SAME pose geometry that worked for v5b (imported, not copied).

Clip -> scenario mapping (from visual inspection):
  WIN_20260617_18_53_46_Pro.mp4 -> helmet_worn                       (head=helmet)
  WIN_20260617_20_23_28_Pro.mp4 -> bare_head_no_helmet               (head=no_helmet)
  no_helmet.mp4                 -> bare_head_headphones_no_helmet     (head=no_helmet)
  no_helmet 2.mp4               -> bare_head_headphones_helmet_held   (head=no_helmet)

Outputs:
  raw frames     -> ai-model/datasets/raw/webcam-hard-negatives-v5c/<scenario>/
  labeled splits -> ai-model/datasets/processed/webcam-ppe-v5c/{train,valid,test}/

Does NOT train, commit, touch models, or use any construction data.
"""

import sys
from collections import Counter
from pathlib import Path

import cv2
from ultralytics import YOLO

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
# Reuse the proven v5b autolabel geometry.
from autolabel_webcam_pose import (  # noqa: E402
    best_person, head_box_from_kpts, to_yolo_line, split_for, POSE_CONF,
)

PROJECT_ROOT = SCRIPT_DIR.parent.parent
CAMERA_ROLL = Path("C:/Users/druvk/OneDrive/Pictures/Camera Roll")
RAW_OUT = PROJECT_ROOT / "ai-model" / "datasets" / "raw" / "webcam-hard-negatives-v5c"
PROC_OUT = PROJECT_ROOT / "ai-model" / "datasets" / "processed" / "webcam-ppe-v5c"
POSE_MODEL = "yolov8n-pose.pt"

CLASS_NAME = {1: "helmet", 2: "no_helmet"}
FINAL_NAMES = {0: "person", 1: "helmet", 2: "no_helmet", 3: "vest", 4: "no_vest"}
SPLITS = ("train", "valid", "test")

# clip file, scenario subfolder, head class, box style, prefix, allow empty-neg,
# target_frames (stride chosen to land near this). helmet_worn is sampled
# densely (~200) so v5c keeps worn-helmet strength; hard-negatives stay ~70.
CLIPS = [
    ("WIN_20260617_18_53_46_Pro.mp4", "helmet_worn",
     1, "helmet", "win1_", False, 200),
    ("WIN_20260617_20_23_28_Pro.mp4", "bare_head_no_helmet",
     2, "no_helmet", "win2_", True, 70),
    ("no_helmet.mp4", "bare_head_headphones_no_helmet",
     2, "no_helmet", "nh1_", False, 70),
    ("no_helmet 2.mp4", "bare_head_headphones_helmet_held",
     2, "no_helmet", "nh2_", False, 70),
]


def ensure_tree():
    for s in SPLITS:
        (PROC_OUT / s / "images").mkdir(parents=True, exist_ok=True)
        (PROC_OUT / s / "labels").mkdir(parents=True, exist_ok=True)


def write_data_yaml():
    lines = ["train: train/images", "val: valid/images", "test: test/images",
             "", f"nc: {len(FINAL_NAMES)}", "", "names:"]
    for cid, cname in FINAL_NAMES.items():
        lines.append(f"  {cid}: {cname}")
    (PROC_OUT / "data.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    ensure_tree()
    model = YOLO(POSE_MODEL)
    totals = Counter()
    per_clip = {}

    for clip_name, scenario, cls_id, style, prefix, allow_empty, target in CLIPS:
        clip_path = CAMERA_ROLL / clip_name
        if not clip_path.exists():
            print(f"[SKIP] missing clip: {clip_path}")
            totals["clips_skipped"] += 1
            continue

        raw_dir = RAW_OUT / scenario
        raw_dir.mkdir(parents=True, exist_ok=True)

        cap = cv2.VideoCapture(str(clip_path))
        n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
        stride = max(1, round(n / target))
        print(f"\n=== {clip_name} -> {scenario} ({CLASS_NAME[cls_id]}) ===")
        print(f"    frames={n} stride={stride} (~{n // stride} samples)")

        c = Counter()
        idx = 0
        sampled = 0
        i = 0
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if i % stride == 0:
                h, w = frame.shape[:2]
                stem = f"{prefix}{sampled:04d}"
                # save the raw (clean) frame for transparency / re-labeling
                cv2.imwrite(str(raw_dir / f"{stem}.jpg"), frame)

                res = model.predict(source=frame, conf=POSE_CONF, verbose=False)[0]
                person = best_person(res)
                box = None
                if person is not None:
                    box = head_box_from_kpts(person[0], person[1], person[2],
                                             style, w, h)

                split = split_for(sampled)
                out_img = PROC_OUT / split / "images" / f"webcam_{stem}.jpg"
                out_lbl = PROC_OUT / split / "labels" / f"webcam_{stem}.txt"

                if box is not None:
                    cv2.imwrite(str(out_img), frame)
                    out_lbl.write_text(to_yolo_line(cls_id, box, w, h) + "\n",
                                       encoding="utf-8")
                    c["labeled"] += 1
                    c[CLASS_NAME[cls_id]] += 1
                    totals[CLASS_NAME[cls_id]] += 1
                elif person is None and allow_empty:
                    cv2.imwrite(str(out_img), frame)
                    out_lbl.write_text("", encoding="utf-8")
                    c["empty_neg"] += 1
                    totals["empty_neg"] += 1
                else:
                    c["skipped_no_head"] += 1
                    totals["skipped_no_head"] += 1
                sampled += 1
            i += 1
        cap.release()
        per_clip[clip_name] = (scenario, c)

    write_data_yaml()

    print("\n" + "=" * 64)
    print("v5c WEBCAM PREP SUMMARY")
    print("=" * 64)
    for clip_name, (scenario, c) in per_clip.items():
        print(f"\n{clip_name}  ->  {scenario}")
        print(f"   labeled        : {c['labeled']}  "
              f"(helmet={c['helmet']}, no_helmet={c['no_helmet']})")
        print(f"   empty negatives: {c['empty_neg']}")
        print(f"   skipped(no head): {c['skipped_no_head']}")
    print("\nTOTALS (webcam-ppe-v5c, before merge):")
    print(f"   helmet         : {totals['helmet']}")
    print(f"   no_helmet      : {totals['no_helmet']}")
    print(f"   empty negatives: {totals['empty_neg']}")
    print(f"   skipped(no head): {totals['skipped_no_head']}")
    print(f"\nRaw frames : {RAW_OUT}")
    print(f"Labeled    : {PROC_OUT}")
    print("=" * 64)


if __name__ == "__main__":
    main()
