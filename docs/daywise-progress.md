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
