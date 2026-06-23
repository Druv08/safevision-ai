"""
SafeVision AI - v5e helmet STABILITY label prep (prepare + preview only).

Why v5e
-------
v5d fixed the false-positive problem (bare head / headphones / held helmet no
longer count as a worn helmet) using TIGHT yellow-hardhat-shell boxes. But the
worn-helmet training frames were almost all clean FRONT views, so live the
helmet drops out the moment the head tilts, turns, looks down/up, or moves.

v5e is a SMALL, TARGETED stability top-up. It adds worn-helmet frames at many
head angles + motion, plus a fresh round of negative checks, using the SAME
correct label definition as v5d:

  * helmet (class 1): a TIGHT box around the actual YELLOW HARDHAT SHELL only
    (HSV colour segmentation in the head ROI). No face / forehead / beard /
    headphones / neck / torso.
  * no_helmet (class 2): the bare / hair / headphone HEAD region (pose box).
  * held helmet: head -> no_helmet; the held yellow shell is NOT labelled.

Difference vs v5d's detector: v5d required the shell to reach the eye line
(front-view "worn" check). That gate over-rejects tilted / looking-down / side
frames -- exactly the footage v5e needs. Because every clip lives in a folder
that already declares whether the helmet is worn, v5e TRUSTS the folder: in a
helmet_worn_* folder, a yellow shell of sufficient area in the head ROI is a
worn helmet. The box stays tight to the shell.

Folder layout (drop a short clip *or* pre-extracted frames into each):
    ai-model/datasets/raw/webcam-helmet-stability-v5e/
        helmet_worn_front/
        helmet_worn_tilt_left_right/
        helmet_worn_look_down_up/
        helmet_worn_side_angles/
        helmet_worn_motion/
        no_helmet_headphones_check/
        helmet_held_not_worn_check/
        _label_preview/        (generated)

This script ONLY extracts frames, writes corrected labels, and renders preview
images. It does NOT build the merged dataset and does NOT train.

Run:
    python ai-model/training/prepare_v5e_helmet_labels.py
Then inspect:
    ai-model/datasets/raw/webcam-helmet-stability-v5e/_label_preview/
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
RAW_ROOT = PROJECT_ROOT / "ai-model" / "datasets" / "raw" / "webcam-helmet-stability-v5e"
PROC_OUT = PROJECT_ROOT / "ai-model" / "datasets" / "processed" / "webcam-ppe-v5e"
PREVIEW_DIR = RAW_ROOT / "_label_preview"
POSE_MODEL = "yolov8n-pose.pt"

CLASS_NAME = {1: "helmet", 2: "no_helmet"}
FINAL_NAMES = {0: "person", 1: "helmet", 2: "no_helmet", 3: "vest", 4: "no_vest"}
SPLITS = ("train", "valid", "test")
VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".m4v"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp"}

# Yellow hardhat HSV range (OpenCV H 0-180). S/V floor relaxed vs v5d (90 -> 75)
# so motion-blurred / shadowed / off-angle shell pixels still register.
YELLOW_LOW = np.array([18, 75, 75])
YELLOW_HIGH = np.array([38, 255, 255])
MIN_HELMET_AREA = 700   # px; reject tiny yellow specks

# subfolder, scenario tag, mode, head-class, prefix, target_frames, cap, allow_empty
FOLDERS = [
    ("helmet_worn_front",            "worn_front",   "helmet_color", 1, "wf_",  70, 90,  False),
    ("helmet_worn_tilt_left_right",  "worn_tilt",    "helmet_color", 1, "wt_",  70, 90,  False),
    ("helmet_worn_look_down_up",     "worn_updown",  "helmet_color", 1, "wu_",  70, 90,  False),
    ("helmet_worn_side_angles",      "worn_side",    "helmet_color", 1, "ws_",  70, 90,  False),
    ("helmet_worn_motion",           "worn_motion",  "helmet_color", 1, "wm_",  80, 100, False),
    ("no_helmet_headphones_check",   "no_helmet_hp", "no_helmet_head", 2, "hp_", 80, 100, True),
    ("helmet_held_not_worn_check",   "held_not_worn","no_helmet_head", 2, "hd_", 80, 100, True),
]


def ensure_tree():
    for s in SPLITS:
        (PROC_OUT / s / "images").mkdir(parents=True, exist_ok=True)
        (PROC_OUT / s / "labels").mkdir(parents=True, exist_ok=True)
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)


def head_points(kxy, kcf):
    return [(float(kxy[i][0]), float(kxy[i][1]))
            for i in (NOSE, LEYE, REYE, LEAR, REAR) if kcf[i] >= KP_CONF]


def head_roi(hpts, person_box, img_w, img_h):
    """Generous ROI around the head. Prefer head keypoints; fall back to the
    top of the pose person box when the face is turned away / looking down."""
    if hpts:
        xs = [x for x, _ in hpts]
        ys = [y for _, y in hpts]
        cx = (min(xs) + max(xs)) / 2.0
        ew = max(max(xs) - min(xs), 30.0)   # ~ear-to-ear width
        ey = float(np.mean(ys))
        rx1 = int(max(0, cx - 1.5 * ew));  rx2 = int(min(img_w, cx + 1.5 * ew))
        ry1 = int(max(0, ey - 2.8 * ew));  ry2 = int(min(img_h, ey + 0.8 * ew))
        return rx1, ry1, rx2, ry2
    if person_box is not None:
        px1, py1, px2, py2 = person_box
        pw = px2 - px1
        ph = py2 - py1
        # Top ~40% of the body, slightly widened, is where a worn hardhat sits.
        rx1 = int(max(0, px1 - 0.1 * pw)); rx2 = int(min(img_w, px2 + 0.1 * pw))
        ry1 = int(max(0, py1 - 0.05 * ph)); ry2 = int(min(img_h, py1 + 0.40 * ph))
        return rx1, ry1, rx2, ry2
    return None


def detect_yellow_helmet_v5e(frame, hpts, person_box, img_w, img_h):
    """Tight box around the yellow hardhat shell in the head ROI, or None.

    No eye-line "worn" gate: the caller only passes frames from helmet_worn_*
    folders, so a sufficiently large yellow blob in the head ROI IS a worn
    helmet. The box is the tight bounding rect of the largest yellow contour.
    """
    roi_box = head_roi(hpts, person_box, img_w, img_h)
    if roi_box is None:
        return None
    rx1, ry1, rx2, ry2 = roi_box
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
    return [float(rx1 + x), float(ry1 + y),
            float(rx1 + x + bw), float(ry1 + y + bh)]


def iter_source_frames(folder: Path):
    """Yield BGR frames from every video in `folder`; if there are none, yield
    its loose image frames. Lets you provide either clips or pre-extracted
    frames per subfolder."""
    videos = sorted(p for p in folder.iterdir()
                    if p.is_file() and p.suffix.lower() in VIDEO_EXTS)
    if videos:
        for v in videos:
            cap = cv2.VideoCapture(str(v))
            while True:
                ok, fr = cap.read()
                if not ok:
                    break
                yield fr
            cap.release()
        return
    images = sorted(p for p in folder.iterdir()
                    if p.is_file() and p.suffix.lower() in IMAGE_EXTS)
    for p in images:
        im = cv2.imread(str(p))
        if im is not None:
            yield im


def count_source_frames(folder: Path) -> int:
    videos = sorted(p for p in folder.iterdir()
                    if p.is_file() and p.suffix.lower() in VIDEO_EXTS)
    if videos:
        total = 0
        for v in videos:
            cap = cv2.VideoCapture(str(v))
            total += int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
            cap.release()
        return total
    return sum(1 for p in folder.iterdir()
               if p.is_file() and p.suffix.lower() in IMAGE_EXTS)


def main():
    if not RAW_ROOT.exists():
        print(f"[ERROR] raw root not found: {RAW_ROOT}")
        print("Create it and add the 7 subfolders with your clips/frames first.")
        return 1

    ensure_tree()
    model = YOLO(POSE_MODEL)
    totals = Counter()
    per_folder = {}
    written = {1: [], 2: []}     # (scenario, split, stem) for preview sampling

    for sub, scenario, mode, cls_id, prefix, target, cap, allow_empty in FOLDERS:
        folder = RAW_ROOT / sub
        if not folder.exists():
            print(f"[SKIP] missing folder: {folder}")
            totals["folders_skipped"] += 1
            continue
        n_src = count_source_frames(folder)
        if n_src == 0:
            print(f"[SKIP] no clips/frames in: {folder}")
            totals["folders_empty"] += 1
            continue

        stride = max(1, round(n_src / target))
        print(f"\n=== {sub} -> {scenario} [{mode}] (src frames={n_src}, stride={stride}) ===")

        c = Counter()
        kept = 0
        i = 0
        sampled = 0
        for frame in iter_source_frames(folder):
            if i % stride == 0 and kept < cap:
                h, w = frame.shape[:2]
                res = model.predict(source=frame, conf=POSE_CONF, verbose=False)[0]
                person = best_person(res)
                hpts = head_points(person[1], person[2]) if person else []
                person_box = person[0] if person else None

                box = None
                if mode == "helmet_color":
                    box = detect_yellow_helmet_v5e(frame, hpts, person_box, w, h)
                else:  # no_helmet_head
                    if person is not None:
                        box = head_box_from_kpts(person[0], person[1], person[2],
                                                 "no_helmet", w, h)

                stem = f"{prefix}{sampled:04d}"
                split = split_for(sampled)
                out_img = PROC_OUT / split / "images" / f"v5e_{stem}.jpg"
                out_lbl = PROC_OUT / split / "labels" / f"v5e_{stem}.txt"

                if box is not None:
                    cv2.imwrite(str(out_img), frame)
                    out_lbl.write_text(to_yolo_line(cls_id, box, w, h) + "\n",
                                       encoding="utf-8")
                    c["labeled"] += 1; c[CLASS_NAME[cls_id]] += 1
                    totals[CLASS_NAME[cls_id]] += 1; kept += 1
                    written[cls_id].append((scenario, split, f"v5e_{stem}"))
                elif mode == "no_helmet_head" and person is None and allow_empty:
                    # Frame with no detectable person -> empty negative (no PPE).
                    cv2.imwrite(str(out_img), frame)
                    out_lbl.write_text("", encoding="utf-8")
                    c["empty_neg"] += 1; totals["empty_neg"] += 1; kept += 1
                else:
                    c["skipped"] += 1
                sampled += 1
            i += 1
        per_folder[sub] = (scenario, c)

    # data.yaml for the webcam-ppe-v5e subset (full 5-class schema).
    lines = ["train: train/images", "val: valid/images", "test: test/images",
             "", f"nc: {len(FINAL_NAMES)}", "", "names:"]
    for cid, cname in FINAL_NAMES.items():
        lines.append(f"  {cid}: {cname}")
    (PROC_OUT / "data.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")

    # ---- Label previews: >=10 per requested category -----------------------
    def render(items, n_each, tag):
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

    worn_front = [t for t in written[1] if t[0] == "worn_front"]
    worn_other = [t for t in written[1] if t[0] != "worn_front"]
    nohelm_hp  = [t for t in written[2] if t[0] == "no_helmet_hp"]
    held       = [t for t in written[2] if t[0] == "held_not_worn"]
    render(worn_front, 10, "WORNFRONT")
    render(worn_other, 12, "WORNANGLE")
    render(nohelm_hp,  10, "NOHELMET")
    render(held,       10, "HELD")

    helmet_total = totals["helmet"]
    nohelmet_total = totals["no_helmet"]
    print("\n" + "=" * 64)
    print("v5e STABILITY LABEL PREP SUMMARY (preview only - NOT trained)")
    print("=" * 64)
    for sub, (scenario, c) in per_folder.items():
        print(f"\n{sub} -> {scenario}")
        print(f"   labeled={c['labeled']} (helmet={c['helmet']}, no_helmet={c['no_helmet']}) "
              f"empty_neg={c['empty_neg']} skipped={c['skipped']}")
    print("\nTOTALS:")
    print(f"   helmet labels    : {helmet_total}")
    print(f"   no_helmet labels : {nohelmet_total}")
    print(f"   empty negatives  : {totals['empty_neg']}")
    print(f"   folders skipped  : {totals['folders_skipped']}  empty: {totals['folders_empty']}")
    print(f"\nPreview images   : {PREVIEW_DIR}")
    print(f"Labeled subset   : {PROC_OUT}")
    print("\nNEXT: visually check the preview folder. If the helmet boxes are")
    print("tight to the yellow shell at every angle and no bare/headphone/held")
    print("head is boxed as helmet, build v5e:")
    print("   python ai-model/training/build_safevision_v5e_dataset.py --oversample 5")
    print("=" * 64)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
