"""
SafeVision AI - v5d helmet-label CORRECTION workflow (prepare + preview only).

Why v5d
-------
v5c taught the model "head/hair/headphones = helmet" because the pose-derived
helmet box was anchored to the eye line and sized by head width -> it tracked
the HEAD, not the hardhat. v5d fixes the helmet label definition:

  * helmet (class 1): a TIGHT box around the actual YELLOW HARDHAT SHELL, found
    by HSV colour segmentation, and ONLY when that shell sits on the head
    (overlaps the head region = worn). No face / forehead / beard / headphones.
  * no_helmet (class 2): the bare / hair / headphone HEAD region (pose box).
  * held helmet: head -> no_helmet; the held yellow shell is NOT labelled
    (ignored for PPE compliance).
  * headphones: bare head + headphones -> no_helmet (never helmet).

This script ONLY extracts frames, writes corrected labels, and renders preview
images. It does NOT build the merged dataset and does NOT train.

Run:
    python ai-model/training/prepare_v5d_helmet_labels.py
Then inspect:  ai-model/datasets/raw/webcam-hard-negatives-v5d/_label_preview/
"""

import sys
import random
from collections import Counter
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from autolabel_webcam_pose import (  # noqa: E402  reuse proven pose helpers
    best_person, head_box_from_kpts, to_yolo_line, split_for,
    POSE_CONF, KP_CONF, NOSE, LEYE, REYE, LEAR, REAR,
)

PROJECT_ROOT = SCRIPT_DIR.parent.parent
CAMERA_ROLL = Path("C:/Users/druvk/OneDrive/Pictures/Camera Roll")
RAW_OUT = PROJECT_ROOT / "ai-model" / "datasets" / "raw" / "webcam-hard-negatives-v5d"
PROC_OUT = PROJECT_ROOT / "ai-model" / "datasets" / "processed" / "webcam-ppe-v5d"
PREVIEW_DIR = RAW_OUT / "_label_preview"
POSE_MODEL = "yolov8n-pose.pt"

CLASS_NAME = {1: "helmet", 2: "no_helmet"}
FINAL_NAMES = {0: "person", 1: "helmet", 2: "no_helmet", 3: "vest", 4: "no_vest"}
SPLITS = ("train", "valid", "test")

# Yellow hardhat HSV range (OpenCV H 0-180). Tuned on the worn-helmet frames.
YELLOW_LOW = np.array([18, 90, 90])
YELLOW_HIGH = np.array([38, 255, 255])
MIN_HELMET_AREA = 800   # px; reject tiny yellow specks

# clip, scenario, mode, head-class, prefix, allow_empty, target_frames, cap
CLIPS = [
    ("WIN_20260617_18_53_46_Pro.mp4", "helmet_worn",
     "helmet_color", 1, "h_", False, 150, 150),
    ("WIN_20260617_20_23_28_Pro.mp4", "bare_head_no_helmet",
     "no_helmet_head", 2, "bare_", True, 70, 70),
    ("no_helmet.mp4", "bare_head_headphones_no_helmet",
     "no_helmet_head", 2, "hp_", False, 70, 70),
    ("no_helmet 2.mp4", "held_helmet_not_worn",
     "no_helmet_head", 2, "held_", False, 80, 80),
]


def ensure_tree():
    for s in SPLITS:
        (PROC_OUT / s / "images").mkdir(parents=True, exist_ok=True)
        (PROC_OUT / s / "labels").mkdir(parents=True, exist_ok=True)
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)


def head_points(kxy, kcf):
    return [(float(kxy[i][0]), float(kxy[i][1]))
            for i in (NOSE, LEYE, REYE, LEAR, REAR) if kcf[i] >= KP_CONF]


def detect_yellow_helmet(frame, hpts, img_w, img_h):
    """Tight box around the yellow hardhat shell on the head. None if not worn.

    Searches a generous ROI around the head keypoints, finds the largest
    yellow blob, and accepts it only if it overlaps the head region (= worn,
    not held off to the side).
    """
    if not hpts:
        return None
    xs = [x for x, _ in hpts]
    ys = [y for _, y in hpts]
    cx = (min(xs) + max(xs)) / 2.0
    ew = max(max(xs) - min(xs), 30.0)   # ~ear-to-ear
    ey = float(np.mean(ys))

    rx1 = int(max(0, cx - 1.4 * ew));  rx2 = int(min(img_w, cx + 1.4 * ew))
    ry1 = int(max(0, ey - 2.6 * ew));  ry2 = int(min(img_h, ey + 0.6 * ew))
    roi = frame[ry1:ry2, rx1:rx2]
    if roi.size == 0:
        return None

    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, YELLOW_LOW, YELLOW_HIGH)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        return None
    c = max(cnts, key=cv2.contourArea)
    if cv2.contourArea(c) < MIN_HELMET_AREA:
        return None
    x, y, bw, bh = cv2.boundingRect(c)
    hx1, hy1, hx2, hy2 = rx1 + x, ry1 + y, rx1 + x + bw, ry1 + y + bh

    # Worn check: helmet shell must reach down to ~the eye line (sits ON head).
    if hy2 < ey - 0.3 * ew:
        return None       # shell floating well above head -> being raised/held
    return [float(hx1), float(hy1), float(hx2), float(hy2)]


def main():
    ensure_tree()
    model = YOLO(POSE_MODEL)
    totals = Counter()
    per_clip = {}
    written = {1: [], 2: []}   # (split, stem) for preview sampling, by class

    for clip_name, scenario, mode, cls_id, prefix, allow_empty, target, cap in CLIPS:
        clip_path = CAMERA_ROLL / clip_name
        if not clip_path.exists():
            print(f"[SKIP] missing clip: {clip_path}"); totals["clips_skipped"] += 1
            continue
        raw_dir = RAW_OUT / scenario
        raw_dir.mkdir(parents=True, exist_ok=True)

        cap_v = cv2.VideoCapture(str(clip_path))
        n = int(cap_v.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
        stride = max(1, round(n / target))
        print(f"\n=== {clip_name} -> {scenario} [{mode}] (frames={n}, stride={stride}) ===")

        c = Counter()
        kept = 0
        i = 0
        sampled = 0
        while True:
            ok, frame = cap_v.read()
            if not ok:
                break
            if i % stride == 0 and kept < cap:
                h, w = frame.shape[:2]
                res = model.predict(source=frame, conf=POSE_CONF, verbose=False)[0]
                person = best_person(res)
                hpts = head_points(person[1], person[2]) if person else []

                box = None
                if mode == "helmet_color":
                    box = detect_yellow_helmet(frame, hpts, w, h)
                else:  # no_helmet_head
                    if person is not None:
                        box = head_box_from_kpts(person[0], person[1], person[2],
                                                 "no_helmet", w, h)

                stem = f"{prefix}{sampled:04d}"
                cv2.imwrite(str(raw_dir / f"{stem}.jpg"), frame)
                split = split_for(sampled)
                out_img = PROC_OUT / split / "images" / f"v5d_{stem}.jpg"
                out_lbl = PROC_OUT / split / "labels" / f"v5d_{stem}.txt"

                if box is not None:
                    cv2.imwrite(str(out_img), frame)
                    out_lbl.write_text(to_yolo_line(cls_id, box, w, h) + "\n",
                                       encoding="utf-8")
                    c["labeled"] += 1; c[CLASS_NAME[cls_id]] += 1
                    totals[CLASS_NAME[cls_id]] += 1; kept += 1
                    written[cls_id].append((scenario, split, f"v5d_{stem}"))
                elif mode == "no_helmet_head" and person is None and allow_empty:
                    cv2.imwrite(str(out_img), frame)
                    out_lbl.write_text("", encoding="utf-8")
                    c["empty_neg"] += 1; totals["empty_neg"] += 1; kept += 1
                else:
                    c["skipped"] += 1
                sampled += 1
            i += 1
        cap_v.release()
        per_clip[clip_name] = (scenario, c)

    # data.yaml for the webcam-ppe-v5d subset
    lines = ["train: train/images", "val: valid/images", "test: test/images",
             "", f"nc: {len(FINAL_NAMES)}", "", "names:"]
    for cid, cname in FINAL_NAMES.items():
        lines.append(f"  {cid}: {cname}")
    (PROC_OUT / "data.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")

    # ---- Label previews: ~20 frames across the 3 categories ----------------
    def render(items, n_each, color, tag):
        random.seed(42)
        picks = random.sample(items, min(n_each, len(items)))
        for scenario, split, stem in picks:
            img_p = PROC_OUT / split / "images" / f"{stem}.jpg"
            lbl_p = PROC_OUT / split / "labels" / f"{stem}.txt"
            im = cv2.imread(str(img_p))
            if im is None:
                continue
            hh, ww = im.shape[:2]
            for line in lbl_p.read_text().splitlines():
                if not line.strip():
                    continue
                cid, cx, cy, bw, bh = line.split()
                cx, cy, bw, bh = map(float, (cx, cy, bw, bh))
                x1 = int((cx - bw / 2) * ww); y1 = int((cy - bh / 2) * hh)
                x2 = int((cx + bw / 2) * ww); y2 = int((cy + bh / 2) * hh)
                col = (0, 200, 0) if cid == "1" else (0, 0, 255)
                cv2.rectangle(im, (x1, y1), (x2, y2), col, 3)
                cv2.putText(im, CLASS_NAME[int(cid)], (x1, max(18, y1 - 6)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, col, 2)
            cv2.imwrite(str(PREVIEW_DIR / f"{tag}_{scenario}_{stem}.jpg"), im)

    helmet_items = written[1]
    held_items = [t for t in written[2] if t[0] == "held_helmet_not_worn"]
    nohelm_items = [t for t in written[2] if t[0] != "held_helmet_not_worn"]
    render(helmet_items, 8, (0, 200, 0), "HELMET")
    render(nohelm_items, 7, (0, 0, 255), "NOHELMET")
    render(held_items, 5, (0, 0, 255), "HELD")

    print("\n" + "=" * 64)
    print("v5d LABEL PREP SUMMARY (preview only - NOT trained)")
    print("=" * 64)
    for clip_name, (scenario, c) in per_clip.items():
        print(f"\n{clip_name} -> {scenario}")
        print(f"   labeled={c['labeled']} (helmet={c['helmet']}, no_helmet={c['no_helmet']}) "
              f"empty_neg={c['empty_neg']} skipped={c['skipped']}")
    print("\nTOTALS:")
    print(f"   helmet labels    : {totals['helmet']}")
    print(f"   no_helmet labels : {totals['no_helmet']}")
    print(f"   empty negatives  : {totals['empty_neg']}")
    print(f"\nPreview images   : {PREVIEW_DIR}")
    print(f"Labeled subset   : {PROC_OUT}")
    print("=" * 64)


if __name__ == "__main__":
    main()
