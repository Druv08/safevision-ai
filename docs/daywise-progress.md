# Day-wise Progress

## Day 1 — Project Setup

### Completed
- [x] Created GitHub repository `safevision-ai` and cloned locally
- [x] Created base folder structure (`ai-model/`, `backend/`, `frontend/`, `docs/`)
- [x] Added `backend/requirements.txt` with core dependencies
- [x] Created FastAPI starter (`backend/main.py`) with `/` and `/health` routes
- [x] Added `backend/.env.example` for Supabase config
- [x] Added YOLO sanity test script (`ai-model/inference/test_yolo.py`)
- [x] Added OpenCV webcam test script (`ai-model/inference/test_opencv.py`)
- [x] Wrote initial docs: `architecture.md`, `project-notes.md`, `research-log.md`
- [x] Updated root `README.md` with setup + run instructions

### Issues Faced
- _None yet — fill in here as we run the test scripts and backend._

### Next Day Plan (Day 2)
- Find a suitable PPE detection dataset (Roboflow / Kaggle / open sources)
- Understand the YOLO dataset format (`images/`, `labels/`, `data.yaml`)
- Finalize the class list: `person`, `helmet`, `vest`, `no_helmet`, `no_vest`
- Prepare `data.yaml` for training
- Decide on train/val/test split

---

## Day 4 — Train and Test 5-Class SafeVision Model

### Completed
- [x] Acquired second PPE dataset (Roboflow `vest-no-vest v1`, 7,205 labels)
- [x] Built merged 5-class processed dataset at `ai-model/datasets/processed/safevision-ppe-5class/`
  - 5,987 train / 740 valid / 672 test images
  - Class instance counts: person=69, helmet=436, no_helmet=108, vest=7,989, no_vest=7,717
- [x] Wrote dataset builder (`ai-model/training/build_safevision_5class_dataset.py`) with class remap + 90/10 train→test split for source 2 (seed=42)
- [x] Wrote 5-class training script (`ai-model/training/train_safevision_5class.py`) with `--smoke`, `--fast`, `--resume` modes
- [x] Verified pipeline with smoke run (1 epoch → vest mAP50 already 0.80)
- [x] Completed full 30-epoch training on CPU (`safevision_yolov8n_5class_v2`)
- [x] Wrote v2 inference test (`ai-model/inference/test_safevision_5class_model.py`)
- [x] Ran inference on 20 processed-test images at conf=0.25

### v2 Final Metrics (best.pt, valid split)
| Metric    | Value |
|-----------|-------|
| Precision | 0.590 |
| Recall    | 0.512 |
| mAP50     | 0.481 |
| mAP50-95  | 0.280 |

Per-class mAP50: person 0.007 · helmet 0.450 · no_helmet 0.180 · **vest 0.948** · **no_vest 0.820**

### v2 Inference (20 test images, conf=0.25)
person 0 · helmet 16 · no_helmet 0 · vest 16 · no_vest 18 (total 50 detections)

### Issues Faced
- First training run had no `test/` split in `ppe-vest-yolo` — handled by 90/10 split from `train/` (seed=42)
- Same-terminal polling killed an earlier run via Ctrl+C; added `--resume` flag to recover from `last.pt` checkpoint
- Helmet mAP regressed vs v1 (0.72 → 0.45) because merged set is now vest-heavy; trade-off accepted for MVP

### Next Day Plan (Day 5)
- Integrate `safevision_yolov8n_5class_v2/weights/best.pt` into FastAPI backend
- Add `/predict` endpoint accepting an uploaded image
- Return JSON with detections (class, conf, bbox) + optional annotated image

---

## Day 5 — Local Video & Webcam Detection Pipeline

### Completed
- [x] Wrote local inference script `ai-model/inference/video_detection.py` (OpenCV + Ultralytics)
  - Supports `--source 0` (webcam, default) or a video file path
  - `--conf` flag (default 0.25), `--save` flag, `--model` flag
  - On-frame HUD: smoothed FPS + live per-class counts
  - Color-coded boxes: green for `vest`/`helmet`, red for `no_vest`/`no_helmet`
  - Press `q` (or close window) to quit cleanly; final per-class totals printed
  - `try/except/finally` ensures `cap.release()` + `writer.release()` always run
- [x] Created folders: `ai-model/test-videos/` (with `.gitkeep`) and `ai-model/outputs/video-detections/`
- [x] Updated `.gitignore` to exclude `*.mp4`, `*.avi`, `*.mov`, `*.mkv`, `ai-model/test-videos/*`, `ai-model/outputs/video-detections/`
- [x] Webcam test at `--conf 0.25` (6,861 frames, ~25.8 FPS smoothed) — `vest` + `no_vest` detected live, no errors
- [x] Video file test on a 2560×1524 screen recording at `--conf 0.4 --save` — annotated MP4 saved successfully

### Performance
| Run                | Resolution  | Frames | Avg FPS |
|--------------------|-------------|-------:|--------:|
| Webcam @ conf 0.25 | 640×480     |  6,861 |  ~25.8  |
| Video  @ conf 0.40 | 2560×1524   |    812 |   13.5  |

### Detection counts (per-frame rate at conf 0.25 vs 0.40)
| Class     | Webcam 0.25 | Video 0.40 |
|-----------|------------:|-----------:|
| person    | 0           | 0          |
| helmet    | 0           | 0          |
| no_helmet | 0           | 0          |
| vest      | 321         | 433        |
| no_vest   | 6,823       | 268        |

`no_vest` per-frame rate dropped from **~0.99 → ~0.33** when threshold was raised — confirming that `--conf 0.4` is a much cleaner default for live deployment.

### Issues Faced
- `person`, `helmet`, `no_helmet` did not fire in webcam/screen-recording footage — matches the v2 training weakness (data-starved classes), not a pipeline bug
- At `--conf 0.25`, `no_vest` was overactive on plain desk backgrounds — fixed by raising threshold to 0.4

### Next Day Plan (Day 6)
- Begin backend integration: `/predict` endpoint serving `best.pt`
- Decide whether to train a v3 with class-balanced sampling to fix the `person`/`helmet` weakness, or move forward with v2 + post-processing rules

### Day 5 Cleanup — Dual-Model Worker Detection
- Refactored `video_detection.py` to load **two YOLO models** in parallel:
  - **SafeVision PPE model** (`safevision_yolov8n_5class_v2/weights/best.pt`) — used for `vest` / `no_vest` / `helmet` / `no_helmet` only.
  - **COCO YOLOv8n** (`yolov8n.pt`) — used **only** for worker/person detection (`classes=[0]`).
- New CLI flag: `--person-conf` (default `0.4`).
- Overlay row `human` removed; `workers` is now driven by the COCO detector — NOT by `vest + no_vest`.
- Fixed the issue where holding a loose vest in front of the camera was being counted as a worker. With the new logic: vest visible + no person in frame → `workers: 0`, `vest: 1`.
- COCO person boxes drawn in cyan-blue with label `worker` (visually distinct from green/red PPE boxes).
- Performance: FPS dropped from ~25 (single-model) to ~16 (dual-model) on CPU at 640×480 — still well within MVP target.
- Webcam test: 794 frames, 16.4 FPS, dual-model loaded cleanly, no errors. Workers counted only when a real person was visible.

---

## Day 6 — Local Violation Detection (Screenshots + CSV Log)

### Completed
- [x] Created `ai-model/inference/violation_detection.py` — local PPE violation pipeline (no backend yet).
  - Dual-model reuse: SafeVision PPE v2 (`best.pt`) for PPE, COCO `yolov8n.pt` for workers (Day 5 setup, pose model intentionally NOT used here).
  - Worker boxes use the same size + aspect-ratio sanity filter as Day 5 (`--person-conf` default `0.7`).
  - Violation rules (frame-level):
    - `no_vest` present → **Safety Vest Missing** (Medium)
    - `no_helmet` present → **Helmet Missing** (High) — *experimental, weaker class*
    - both present in same frame → **Multiple PPE Missing** (Critical)
  - **Duplicate PPE box filter**: `calculate_iou()` + `filter_duplicate_boxes(iou_threshold=0.5)` collapse same-class overlapping boxes (e.g. three `no_vest` boxes on one chest → one). Different classes are never merged.
  - **Active-state counting**: a continuous violation is counted **once**, not once per cooldown. New CLI flag `--clear-after` (default 2.0 s): a violation type only re-fires after it has been absent for >`clear_after` seconds. Cooldown (`--cooldown`, default 5 s) is retained as a secondary safety net.
  - Evidence:
    - Screenshots (annotated frames, HUD + boxes baked in) → `ai-model/outputs/violations/screenshots/<prefix>_YYYYMMDD_HHMMSS_frame<N>.jpg`
    - CSV log → `ai-model/outputs/violations/violations_log.csv` with columns `violation_id, timestamp, source, frame_number, violation_type, severity, confidence, worker_detected, screenshot_path`
  - HUD row `violations:` = cumulative **saved events**, not raw detections.
  - `--save-video` saves the annotated MP4 to `ai-model/outputs/video-detections/` (Day 5 folder).
- [x] Updated `.gitignore` with explicit `ai-model/outputs/violations/`, `*.jpg`, `*.jpeg`, `*.png`, `*.csv` rules so screenshots and the CSV log never get committed.

### Behavioural checks (verified live)

| Scenario | Expected | Observed |
|---|---|---|
| Stand without vest, sit still for ~140 s | violations = 1 | **1** (frame 226 → 2354 gap, zero new events) |
| Cover chest / leave frame > 2 s, then return | violations += 1 | yes |
| Helmet violations | rare due to weak class | 0 across all runs |

### Performance

| Run | Resolution | Frames | Avg FPS | Events saved | Dup filter (removed / raw) |
|---|---|---:|---:|---:|---:|
| Webcam (active-state on) | 640×480 | 2,811 | 15.16 | 5 | 212 / 2,725 (7.8%) |
| Video file (`--save-video`) | 2,560×1,524 | 812 | 10.68 | 5 | 2 / 701 (0.3%) |

### Video file test details
- Input: `ai-model/test-videos/screen_recording_20260605_1222.mp4` (2560×1524, ~27 s of source time).
- Output: `safevision_violations_20260608_013801.mp4` (80.2 MB).
- 5 Safety Vest Missing screenshots written (608–629 KB each, annotated).
- 5 new CSV rows: confidences 0.78 / 0.58 / 0.62 / 0.49 / 0.65; `worker_detected` mixed (yes/no).
- No errors.

### Issues Faced / Notes
- The first naïve run inflated the violations count by re-saving every cooldown tick (~20 events for one continuous sit). Fixed by adding the active-state + `clear-after` gate.
- The PPE model occasionally emitted 2–3 overlapping `no_vest` boxes on a single chest. Fixed by per-class IoU NMS (raw vs kept ratio surfaced in the summary).
- Several saved CSV rows for the video had `worker_detected = no` because the COCO person filter (`--person-conf 0.7`, 3% min area, AR 0.2–1.2) is intentionally strict. The vest-violation detection is independent and still fires correctly. Worker-side strict filtering will be improved later (likely by swapping in the pose model used in `video_detection.py`).
- `helmet` / `no_helmet` remains the weakest pair in v2 — `Helmet Missing` and `Multiple PPE Missing` counts should still be treated as experimental until a v3 retrain.

### Next Day Plan (Day 7)
- Start the backend integration: FastAPI `/predict` endpoint serving `best.pt` for single-image inference.
- Decide whether the violation pipeline should also be exposed as an HTTP endpoint that returns the latest events + screenshot URLs.
- Tighten worker-side filtering in `violation_detection.py` (pose model option, mirroring `video_detection.py`).



## Day 6.5 - Worker-Matched Violation Filtering

**Goal:** Stop saving violations when a no_vest / no_helmet box is not on a real worker.

### Problem observed on the Day 6 video run
On `screen_recording_20260605_1222.mp4` the Day 6 pipeline saved 5 `Safety Vest Missing` events. Two of those CSV rows had `worker_detected=no` - i.e. the PPE model fired on something vest-shaped (clothing on a chair, a poster, etc.) but the COCO person detector did not return a worker box. Those should not be counted as worker violations.

### Code changes (`ai-model/inference/violation_detection.py`)
- New helper `calculate_overlap_ratio(inner_box, outer_box)`: returns `intersection_area / area(inner_box)`. **Not IoU** - a small `no_vest` chest box has naturally low IoU with a full-body worker box, but its *overlap ratio inside the worker box* is what we care about.
- New helper `ppe_matches_worker(ppe_box, worker_boxes, overlap_threshold=0.3)`: `True` if any worker box's overlap ratio is at least the threshold.
- `draw_worker_boxes()` now returns `(n_workers, worker_boxes)` instead of just the count, so the main loop can use the boxes for matching.
- New CLI flag: `--worker-overlap` (default `0.3` = 30%).
- Main-loop gate order: **worker-match -> active-state -> cooldown**. `last_seen_violation_time` is refreshed even when the worker-match gate suppresses a save, so `--clear-after` does not mis-trip mid-violation.
- `Multiple PPE Missing` now requires **both** `no_vest` and `no_helmet` to be individually matched to any worker.
- Final summary now reports `Worker-match gate` threshold, `Unmatched no_vest` and `Unmatched no_helmet` skip counts.
- Startup banner now prints the worker-overlap threshold.

### Verified video run
Same source (`screen_recording_20260605_1222.mp4`, 2560x1524, 812 frames):

| Metric | Day 6 | Day 6.5 |
|---|---|---|
| Frames | 812 | 812 |
| FPS | 10.68 | 9.54 |
| Violations saved | 5 | **4** |
| `worker_detected=no` saves | 2 | **0** |
| Unmatched `no_vest` skipped | n/a | **72** |
| Errors | none | none |

All 4 new CSV rows have `worker_detected=yes`. Annotated MP4 still written to `ai-model/outputs/video-detections/`.

### Tomorrow
- Webcam re-run with the new gate (long sit + walk-out-of-frame to exercise unmatched counter on live input).
- Begin Day 7 backend: FastAPI `/predict` for single-image PPE inference; decide whether to also expose the violation pipeline as a streaming endpoint.

---
