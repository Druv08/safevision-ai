"""
SafeVision AI - Auto-label webcam frames into helmet / no_helmet using POSE.

Why
---
We extracted webcam frames from two clips:
    raw-frames/            -> helmet WORN  (every frame is a helmet)
    raw-frames-nohelmet/   -> bare head    (no helmet) + a few empty-room frames

Because each clip is single-class, we don't need a human to draw boxes. The
YOLOv8 POSE model works fine on this webcam domain (it detects the person and
body keypoints), so we use the head keypoints (nose / eyes / ears) to place a
box on the head region and tag it with the clip's class:
    helmet clip     -> class 1 (helmet)
    no_helmet clip  -> class 2 (no_helmet)
Empty-room frames (no person at all) in the no_helmet clip become empty label
files = useful hard negatives.

Boxes are approximate (derived from keypoints), which is fine for a fine-tune
whose goal is "detect the helmet/head at all" in this domain.

Two modes
---------
    --preview     : draw boxes on a few frames per clip into a preview folder
                    (sanity check; does NOT build the dataset).
    (default)     : process every frame, write a processed dataset:
                    processed/webcam-ppe/{train,valid,test}/{images,labels}
                    (final 5-class schema, ready to merge into v5).

Run:
    python ai-model/training/autolabel_webcam_pose.py --preview
    python ai-model/training/autolabel_webcam_pose.py
"""

import argparse
import shutil
from collections import Counter
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
RAW = PROJECT_ROOT / "ai-model" / "datasets" / "raw" / "webcam-capture"
OUT_DIR = PROJECT_ROOT / "ai-model" / "datasets" / "processed" / "webcam-ppe"
PREVIEW_DIR = RAW / "_autolabel_preview"
POSE_MODEL = "yolov8n-pose.pt"

# Clip -> (frames_dir, final_class_id, box_style, allow_empty_negatives)
CLIPS = [
    {"dir": RAW / "raw-frames",          "cls": 1, "style": "helmet",    "allow_empty": False},
    {"dir": RAW / "raw-frames-nohelmet", "cls": 2, "style": "no_helmet", "allow_empty": True},
]

CLASS_NAME = {1: "helmet", 2: "no_helmet"}

# Pose settings
POSE_CONF = 0.45          # person-box confidence gate
KP_CONF = 0.30            # per-keypoint visibility threshold
MIN_HEAD_KPTS = 2         # need >=2 of nose/eyes/ears to localize the head

# COCO keypoint indices
NOSE, LEYE, REYE, LEAR, REAR, LSHO, RSHO = 0, 1, 2, 3, 4, 5, 6

# Box geometry (multiples of the estimated head WIDTH). Helmet sits higher and
# a touch wider than a bare head, so it gets a taller/wider box.
GEO = {
    # helmet = the hat object: top of helmet down to ~the brim (eye line).
    "helmet":    {"w_mult": 1.15, "top": 0.95, "bot": 0.12},
    # no_helmet = the bare head: hairline/crown down to ~the mouth.
    "no_helmet": {"w_mult": 1.05, "top": 0.85, "bot": 0.72},
}

# Train/valid/test split ratio (deterministic by frame index).
SPLIT = {"train": 0.8, "valid": 0.1, "test": 0.1}
FINAL_NAMES = {0: "person", 1: "helmet", 2: "no_helmet", 3: "vest", 4: "no_vest"}


def parse_args():
    p = argparse.ArgumentParser(description="Auto-label webcam frames via pose.")
    p.add_argument("--preview", action="store_true",
                   help="Draw boxes on a few frames per clip (no dataset build).")
    p.add_argument("--preview-n", type=int, default=8,
                   help="How many preview frames per clip (default 8).")
    return p.parse_args()


def best_person(result):
    """Return (box, kpts_xy, kpts_conf) for the highest-confidence person, or None."""
    if result.boxes is None or len(result.boxes) == 0 or result.keypoints is None:
        return None
    confs = result.boxes.conf.cpu().numpy()
    boxes = result.boxes.xyxy.cpu().numpy()
    kxy = result.keypoints.xy.cpu().numpy()
    kcf = result.keypoints.conf
    if kcf is None:
        return None
    kcf = kcf.cpu().numpy()
    order = np.argsort(-confs)
    for i in order:
        if confs[i] < POSE_CONF:
            continue
        return boxes[i], kxy[i], kcf[i]
    return None


def head_box_from_kpts(box, kxy, kcf, style, img_w, img_h):
    """Estimate a head/helmet box [x1,y1,x2,y2] from head keypoints. None if not localizable."""
    vis = {i: (float(kxy[i][0]), float(kxy[i][1]))
           for i in (NOSE, LEYE, REYE, LEAR, REAR) if kcf[i] >= KP_CONF}
    if len(vis) < MIN_HEAD_KPTS:
        return None

    xs = [p[0] for p in vis.values()]
    ys = [p[1] for p in vis.values()]
    cx = (min(xs) + max(xs)) / 2.0

    # Head width: prefer ear-to-ear, else eye-distance scaled up, else kpt span.
    if LEAR in vis and REAR in vis:
        head_w = abs(vis[LEAR][0] - vis[REAR][0])
    elif LEYE in vis and REYE in vis:
        head_w = abs(vis[LEYE][0] - vis[REYE][0]) * 1.7
    else:
        head_w = max(max(xs) - min(xs), 1.0)

    # Backstop with shoulder width if head_w looks too small.
    if kcf[LSHO] >= KP_CONF and kcf[RSHO] >= KP_CONF:
        sho_w = abs(float(kxy[LSHO][0]) - float(kxy[RSHO][0]))
        head_w = max(head_w, 0.42 * sho_w)
    head_w = max(head_w, 0.04 * img_w)  # never absurdly tiny

    # Vertical anchor = eye line (fallback to nose / kpt mean).
    eye_ys = [vis[i][1] for i in (LEYE, REYE) if i in vis]
    eye_y = float(np.mean(eye_ys)) if eye_ys else (vis.get(NOSE, (0, np.mean(ys)))[1])

    g = GEO[style]
    bw = head_w * g["w_mult"]
    x1 = cx - bw / 2.0
    x2 = cx + bw / 2.0
    y1 = eye_y - g["top"] * head_w
    y2 = eye_y + g["bot"] * head_w

    # Clamp to frame.
    x1 = max(0.0, min(x1, img_w - 1)); x2 = max(0.0, min(x2, img_w - 1))
    y1 = max(0.0, min(y1, img_h - 1)); y2 = max(0.0, min(y2, img_h - 1))
    if x2 - x1 < 4 or y2 - y1 < 4:
        return None
    return [x1, y1, x2, y2]


def to_yolo_line(cls_id, box, img_w, img_h):
    x1, y1, x2, y2 = box
    cx = (x1 + x2) / 2.0 / img_w
    cy = (y1 + y2) / 2.0 / img_h
    w = (x2 - x1) / img_w
    h = (y2 - y1) / img_h
    return f"{cls_id} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}"


def split_for(index):
    """Deterministic split by index: every 10th -> valid/test, rest train."""
    r = index % 10
    if r == 8:
        return "valid"
    if r == 9:
        return "test"
    return "train"


def ensure_tree():
    for s in SPLIT:
        (OUT_DIR / s / "images").mkdir(parents=True, exist_ok=True)
        (OUT_DIR / s / "labels").mkdir(parents=True, exist_ok=True)


def write_data_yaml():
    lines = ["train: train/images", "val: valid/images", "test: test/images",
             "", f"nc: {len(FINAL_NAMES)}", "", "names:"]
    for cid, cname in FINAL_NAMES.items():
        lines.append(f"  {cid}: {cname}")
    (OUT_DIR / "data.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    args = parse_args()
    model = YOLO(POSE_MODEL)

    if args.preview:
        PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
        print(f"[PREVIEW] writing samples to {PREVIEW_DIR}")
    else:
        ensure_tree()

    totals = Counter()

    for clip in CLIPS:
        frames = sorted(clip["dir"].glob("*.jpg"))
        if not frames:
            print(f"[warn] no frames in {clip['dir']}")
            continue
        style, cls_id = clip["style"], clip["cls"]
        print(f"\n=== {clip['dir'].name}  ->  {CLASS_NAME[cls_id]}  "
              f"({len(frames)} frames) ===")

        # Preview: spread N samples across the clip.
        if args.preview:
            step = max(1, len(frames) // args.preview_n)
            frames_to_do = frames[::step][:args.preview_n]
        else:
            frames_to_do = frames

        for idx, fpath in enumerate(frames_to_do):
            img = cv2.imread(str(fpath))
            if img is None:
                continue
            h, w = img.shape[:2]
            res = model.predict(source=img, conf=POSE_CONF, verbose=False)[0]
            person = best_person(res)

            box = None
            if person is not None:
                box = head_box_from_kpts(person[0], person[1], person[2],
                                         style, w, h)

            if args.preview:
                vis = img.copy()
                if box is not None:
                    x1, y1, x2, y2 = (int(v) for v in box)
                    color = (0, 200, 0) if cls_id == 1 else (0, 0, 255)
                    cv2.rectangle(vis, (x1, y1), (x2, y2), color, 3)
                    cv2.putText(vis, CLASS_NAME[cls_id], (x1, max(20, y1 - 8)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
                else:
                    note = "EMPTY/neg" if (person is None and clip["allow_empty"]) else "SKIP (no head)"
                    cv2.putText(vis, note, (20, 40),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 255), 2)
                cv2.imwrite(str(PREVIEW_DIR / f"{style}_{fpath.stem}.jpg"), vis)
                continue

            # ---- dataset build mode ----
            split = split_for(idx)
            out_img = OUT_DIR / split / "images" / f"webcam_{style}_{fpath.stem}.jpg"
            out_lbl = OUT_DIR / split / "labels" / f"webcam_{style}_{fpath.stem}.txt"

            if box is not None:
                shutil.copy2(fpath, out_img)
                out_lbl.write_text(to_yolo_line(cls_id, box, w, h) + "\n",
                                   encoding="utf-8")
                totals[f"{style}_labeled"] += 1
                totals[f"{split}_imgs"] += 1
            elif person is None and clip["allow_empty"]:
                # empty-room frame -> hard negative (image + empty label)
                shutil.copy2(fpath, out_img)
                out_lbl.write_text("", encoding="utf-8")
                totals[f"{style}_empty_neg"] += 1
                totals[f"{split}_imgs"] += 1
            else:
                totals[f"{style}_skipped"] += 1

    if args.preview:
        print(f"\nPreview done. Open: {PREVIEW_DIR}")
        return

    write_data_yaml()
    print("\n" + "=" * 60)
    print("AUTO-LABEL SUMMARY")
    print("=" * 60)
    for k in sorted(totals):
        print(f"  {k:22s}: {totals[k]}")
    print(f"\nOutput dataset: {OUT_DIR}")
    print("Next: merge into v5 (build_safevision_v5_dataset.py), then train.")
    print("=" * 60)


if __name__ == "__main__":
    main()
